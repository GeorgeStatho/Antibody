"""The Pub/Sub push endpoint every agent in the fleet is served behind.

Acknowledgement is the whole subtlety here, so it is stated in one place. Cloud
Monitoring re-notifies and Pub/Sub redelivers, which means the difference between
"this will never parse" and "try me again" decides whether a bad alert disappears
quietly or storms the fleet forever.

  permanent failure  -> 204, acknowledged, never redelivered
  duplicate delivery -> 204, acknowledged, the first verdict stands
  transient failure  -> 500, redelivered, with the subscription's dead-letter topic
                        as the backstop against an endless loop
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request, Response

from agents.common import tracing
from agents.common.alert import Alert, AlertParser
from agents.common.errors import IncidentAlreadyHandled, MalformedAlert

logger = logging.getLogger(__name__)

ACKNOWLEDGED = 204
RETRY_REQUESTED = 500

TRANSIENT_STATUS_CODES = frozenset({429, 500, 502, 503, 504})


class RetryPolicy:
    """Decides whether a failure is worth another delivery."""

    def is_transient(self, error: Exception) -> bool:
        return self._is_retryable_api_error(error) or self._is_unrecognised(error)

    def _is_retryable_api_error(self, error: Exception) -> bool:
        code = getattr(error, "code", None)
        return code in TRANSIENT_STATUS_CODES

    def _is_unrecognised(self, error: Exception) -> bool:
        """An error nobody classified gets one more chance.

        A genuine bug would loop, which is what the dead-letter topic exists to
        stop. Silently acknowledging an unrecognised failure would instead drop a
        real incident, and that is the worse trade.
        """
        return not isinstance(error, (MalformedAlert, IncidentAlreadyHandled))


class PushEndpoint:
    """Turns one push request into one acknowledgement decision."""

    def __init__(self, service, parser: AlertParser | None = None,
                 retry_policy: RetryPolicy | None = None) -> None:
        self._service = service
        self._parser = parser or AlertParser()
        self._retry_policy = retry_policy or RetryPolicy()

    async def receive(self, body: dict) -> Response:
        try:
            alert = self._parse(body)
        except MalformedAlert as error:
            logger.warning("Unparseable alert acknowledged and dropped: %s", error)
            return Response(status_code=ACKNOWLEDGED)

        return await self._triage(alert)

    def _parse(self, body: dict) -> Alert:
        with tracing.span("triage.parse_alert"):
            return self._parser.parse(body)

    async def _triage(self, alert: Alert) -> Response:
        with tracing.span("triage.handle", **{tracing.INCIDENT_ID: alert.incident_id}) as current:
            try:
                verdict = await self._service.handle(alert)
            except IncidentAlreadyHandled:
                logger.info("Duplicate delivery of %s acknowledged", alert.incident_id)
                return Response(status_code=ACKNOWLEDGED)
            except Exception as error:  # noqa: BLE001 - classified, then re-raised or acked
                return self._on_failure(alert, error)

            current.set_attribute(tracing.SEVERITY, verdict.severity.value)
            current.set_attribute(tracing.SYMPTOM_FINGERPRINT, verdict.symptom_fingerprint)
            return Response(status_code=ACKNOWLEDGED)

    def _on_failure(self, alert: Alert, error: Exception) -> Response:
        if self._retry_policy.is_transient(error):
            logger.exception("Transient failure on %s; requesting redelivery", alert.incident_id)
            return Response(status_code=RETRY_REQUESTED)

        logger.exception("Permanent failure on %s; acknowledged", alert.incident_id)
        return Response(status_code=ACKNOWLEDGED)


def create_app(service, agent_name: str) -> FastAPI:
    """Builds the HTTP surface around an already-wired agent service."""
    app = FastAPI(title=f"antibody-{agent_name}")
    endpoint = PushEndpoint(service)

    @app.get("/healthz")
    def healthz():
        return {"status": "ok", "agent": agent_name}

    @app.post("/")
    async def receive_push(request: Request) -> Response:
        return await endpoint.receive(await request.json())

    return app
