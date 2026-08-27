"""The alert ingest boundary.

Everything upstream of this module is attacker-reachable. Everything downstream
receives an Alert whose trusted and untrusted regions have already been separated.

Alert is a data structure, not an object with behaviour: it holds parsed fields and
answers questions about them, and does no work that could fail. The parsing lives
in AlertParser, which is the only thing here that can reject an input.
"""

from __future__ import annotations

import base64
import binascii
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from agents.common.errors import MalformedAlert
from agents.common.values import MetricReading, TrustedFacts, UntrustedText

OPEN = "open"
CLOSED = "closed"

__all__ = ["Alert", "AlertParser", "MalformedAlert", "utc_now"]


def utc_now() -> str:
    return _to_rfc3339(datetime.now(tz=timezone.utc))


def _to_rfc3339(moment: datetime) -> str:
    return moment.isoformat().replace("+00:00", "Z")


def _from_rfc3339(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


@dataclass(frozen=True)
class Alert:
    """One Cloud Monitoring incident with its trust boundary already drawn."""

    incident_id: str
    state: str
    service: str
    reading: MetricReading
    summary: UntrustedText
    documentation: UntrustedText
    started_at: str | None = None
    ended_at: str | None = None
    metric_type: str | None = None
    condition_name: str | None = None
    policy_name: str | None = None
    message_id: str | None = None
    raw: dict = field(default_factory=dict, repr=False)

    @property
    def is_resolved(self) -> bool:
        return self.state == CLOSED

    def seconds_open(self, until: str | None = None) -> float | None:
        if self.started_at is None:
            return None
        try:
            start = _from_rfc3339(self.started_at)
            end = _from_rfc3339(until) if until else datetime.now(tz=timezone.utc)
        except ValueError:
            return None
        return (end - start).total_seconds()

    def opened_within(self, window: timedelta, until: str | None = None) -> bool:
        elapsed = self.seconds_open(until)
        return elapsed is not None and elapsed < window.total_seconds()

    def untrusted_text(self) -> UntrustedText:
        """Exactly what Model Armor scans and the only text a model may see."""
        joined = "\n".join(
            part.content for part in (self.summary, self.documentation) if part.content
        )
        return UntrustedText(joined.strip())

    def trusted_facts(self) -> TrustedFacts:
        return TrustedFacts(
            {
                "service": self.service,
                "metric_type": self.metric_type,
                "condition_name": self.condition_name,
                "state": self.state,
                "observed_value": self.reading.observed,
                "threshold_value": self.reading.threshold,
                "seconds_open": self.seconds_open(),
            }
        )


class AlertParser:
    """Turns a Pub/Sub push body into an Alert.

    Field paths follow the documented Cloud Monitoring notification shape. They have
    never been checked against a captured payload — see infra/fixtures/README.md.
    Where a real notification disagrees with this parser, the notification is right.
    """

    def parse(self, push_body: dict) -> Alert:
        return self._to_alert(self._decode(push_body))

    def _decode(self, push_body: dict) -> dict:
        message = push_body.get("message")
        if not isinstance(message, dict):
            raise MalformedAlert("push body has no message object")

        encoded = message.get("data")
        if not encoded:
            raise MalformedAlert("push message carries no data")

        payload = self._decode_json(encoded)
        payload["_message_id"] = message.get("messageId") or message.get("message_id")
        return payload

    def _decode_json(self, encoded: str) -> dict:
        try:
            decoded = base64.b64decode(encoded, validate=True)
        except (binascii.Error, ValueError) as error:
            raise MalformedAlert(f"data is not valid base64: {error}") from error

        try:
            payload = json.loads(decoded)
        except json.JSONDecodeError as error:
            raise MalformedAlert(f"data is not valid JSON: {error}") from error

        if isinstance(payload, dict):
            return payload
        raise MalformedAlert("notification payload is not a JSON object")

    def _to_alert(self, payload: dict) -> Alert:
        incident = payload.get("incident")
        if not isinstance(incident, dict):
            raise MalformedAlert("notification has no incident object")

        incident_id = _first(incident, "incident_id", "incidentId")
        if not incident_id:
            raise MalformedAlert("incident has no incident_id, so it cannot be deduplicated")

        documentation = _nested(incident, "documentation", "content")
        return Alert(
            incident_id=str(incident_id),
            state=self._state_of(incident),
            service=self._service_of(incident),
            reading=self._reading_of(incident),
            summary=UntrustedText(str(incident.get("summary") or "")),
            documentation=UntrustedText(str(documentation or "")),
            started_at=_as_timestamp(_first(incident, "started_at", "startedAt")),
            ended_at=_as_timestamp(_first(incident, "ended_at", "endedAt")),
            metric_type=_nested(incident, "metric", "type"),
            condition_name=incident.get("condition_name")
            or _nested(incident, "condition", "displayName"),
            policy_name=_first(incident, "policy_name", "policyName"),
            message_id=payload.get("_message_id"),
            raw=payload,
        )

    def _state_of(self, incident: dict) -> str:
        state = str(incident.get("state") or OPEN).lower()
        return state if state in (OPEN, CLOSED) else OPEN

    def _service_of(self, incident: dict) -> str:
        labels = _nested(incident, "resource", "labels") or {}
        return str(
            labels.get("service_name")
            or labels.get("service")
            or incident.get("resource_display_name")
            or "unknown"
        )

    def _reading_of(self, incident: dict) -> MetricReading:
        threshold = _first(incident, "threshold_value") or _nested(
            incident, "condition", "conditionThreshold", "thresholdValue"
        )
        return MetricReading(
            observed=_as_float(_first(incident, "observed_value", "observedValue")),
            threshold=_as_float(threshold),
        )


def _first(source: dict, *keys: str) -> Any:
    for key in keys:
        value = source.get(key)
        if value is not None:
            return value
    return None


def _nested(source: Any, *path: str) -> Any:
    for key in path:
        if not isinstance(source, dict):
            return None
        source = source.get(key)
    return source


def _as_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_timestamp(value: Any) -> str | None:
    if isinstance(value, (int, float)):
        return _to_rfc3339(datetime.fromtimestamp(value, tz=timezone.utc))
    if isinstance(value, str) and value:
        return value
    return None
