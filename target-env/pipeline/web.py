"""The HTTP shape every target service shares.

Each service is a Pub/Sub push endpoint plus the healthcheck the Response agent
probes after a rollback. Acknowledgement follows the same rule as the fleet: a
message that will never succeed is acknowledged so it cannot loop, and anything
else is left for redelivery.
"""

from __future__ import annotations

from fastapi import FastAPI, Request, Response

from pipeline.messaging import MalformedMessage, PushDecoder

ACKNOWLEDGED = 204
RETRY_REQUESTED = 500


class PushRoute:
    """Turns one push request into one acknowledgement decision."""

    def __init__(self, handler, logger, decoder: PushDecoder | None = None) -> None:
        self._handler = handler
        self._logger = logger
        self._decoder = decoder or PushDecoder()

    def receive(self, body: dict) -> Response:
        try:
            message = self._decoder.decode(body)
        except MalformedMessage as error:
            self._logger.error("message_undecodable", error_class=type(error).__name__)
            return Response(status_code=ACKNOWLEDGED)

        return self._deliver(message)

    def _deliver(self, message) -> Response:
        try:
            self._handler.handle(message)
        except Exception as error:  # noqa: BLE001 - redelivery is the safe direction
            self._logger.error(
                "handler_failed",
                error_class=type(error).__name__,
                trace=message.trace,
                message_id=message.message_id,
            )
            return Response(status_code=RETRY_REQUESTED)
        return Response(status_code=ACKNOWLEDGED)


def create_app(service_name: str, handler, logger) -> FastAPI:
    app = FastAPI(title=service_name)
    route = PushRoute(handler, logger)

    @app.get("/healthz")
    def healthz():
        return {"status": "ok", "service": service_name}

    @app.post("/")
    async def receive(request: Request) -> Response:
        return route.receive(await request.json())

    return app
