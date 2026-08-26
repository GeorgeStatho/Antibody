"""Pub/Sub push envelope -> a normalised, trust-tagged alert.

This module is the trust boundary. Everything upstream of it is attacker-reachable;
everything downstream gets to assume its input has been separated into fields that
Cloud Monitoring generated (trusted) and fields that may carry text an attacker put
in a log line (untrusted).

The split is not cosmetic. `untrusted_text()` is exactly what Model Armor scans and
exactly what may reach a prompt; nothing else in the parsed alert is ever handed to
a model as free text.

CAVEAT — the field paths below were written against the DOCUMENTED Monitoring
notification shape, not a captured one. `infra/fixtures/*.json` are SYNTHETIC for
the same reason. Before trusting either: fire one real alert, dump the raw push
body to `infra/fixtures/alert-open.captured.json`, and diff it against
`alert-open.json`. Anything that disagrees, the real payload wins.
"""

from __future__ import annotations

import base64
import binascii
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


class MalformedAlert(ValueError):
    """Permanently unparseable. The caller must ACK (204) — never retry forever."""


# Fields that can carry text originating outside GCP. `summary` and
# `documentation.content` both template log content in a log-based policy, which is
# precisely the injection path demo/poisoned-log.py exercises.
UNTRUSTED_PATHS = (
    ("incident", "summary"),
    ("incident", "documentation", "content"),
    ("incident", "metadata", "user_labels"),
)


def _dig(obj: Any, *path: str) -> Any:
    for key in path:
        if not isinstance(obj, dict):
            return None
        obj = obj.get(key)
    return obj


def _as_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _rfc3339(value: Any) -> str | None:
    """Monitoring sends epoch seconds; be tolerant of an ISO string too."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc).isoformat().replace("+00:00", "Z")
    if isinstance(value, str) and value:
        return value
    return None


def now_rfc3339() -> str:
    return datetime.now(tz=timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass
class ParsedAlert:
    """One Cloud Monitoring incident, with trust already adjudicated."""

    incident_id: str
    state: str  # "open" | "closed"
    started_at: str | None
    ended_at: str | None

    service: str
    metric_type: str | None
    condition_name: str | None
    policy_name: str | None

    observed_value: float | None
    threshold_value: float | None

    # --- untrusted from here down ---
    summary: str = ""
    documentation: str = ""

    message_id: str | None = None
    raw: dict = field(default_factory=dict, repr=False)

    @property
    def is_closed(self) -> bool:
        return self.state == "closed"

    def open_duration_s(self, *, at: str | None = None) -> float | None:
        """Seconds the incident has been open. Feeds flap suppression."""
        if not self.started_at:
            return None
        try:
            start = datetime.fromisoformat(self.started_at.replace("Z", "+00:00"))
            end = (
                datetime.fromisoformat(at.replace("Z", "+00:00"))
                if at
                else datetime.now(tz=timezone.utc)
            )
        except ValueError:
            return None
        return (end - start).total_seconds()

    def untrusted_text(self) -> str:
        """Everything a model may see as free text. Model Armor scans exactly this."""
        return "\n".join(p for p in (self.summary, self.documentation) if p).strip()

    def trusted_facts(self) -> dict:
        """GCP-generated fields only. Safe to interpolate into a prompt verbatim."""
        return {
            "service": self.service,
            "metric_type": self.metric_type,
            "condition_name": self.condition_name,
            "state": self.state,
            "observed_value": self.observed_value,
            "threshold_value": self.threshold_value,
            "open_duration_s": self.open_duration_s(),
        }


def decode_push(body: dict) -> dict:
    """Unwrap the Pub/Sub push envelope. Raises MalformedAlert on anything unusable."""
    message = body.get("message")
    if not isinstance(message, dict):
        raise MalformedAlert("push body has no `message` object")

    data = message.get("data")
    if not data:
        raise MalformedAlert("push message carries no `data`")

    try:
        decoded = base64.b64decode(data, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise MalformedAlert(f"`data` is not valid base64: {exc}") from exc

    try:
        payload = json.loads(decoded)
    except json.JSONDecodeError as exc:
        raise MalformedAlert(f"`data` is not valid JSON: {exc}") from exc

    if not isinstance(payload, dict):
        raise MalformedAlert("notification payload is not a JSON object")

    payload["_message_id"] = message.get("messageId") or message.get("message_id")
    return payload


def parse_notification(payload: dict) -> ParsedAlert:
    """Documented Monitoring notification shape -> ParsedAlert.

    Missing optional fields degrade to None rather than raising: a partial alert is
    still triageable, and a hard failure here would ACK away a real incident. Only a
    missing incident_id is fatal, because without it there is no idempotency key.
    """
    incident = payload.get("incident")
    if not isinstance(incident, dict):
        raise MalformedAlert("notification has no `incident` object")

    incident_id = incident.get("incident_id") or incident.get("incidentId")
    if not incident_id:
        raise MalformedAlert("incident has no incident_id — cannot deduplicate")

    state = str(incident.get("state") or "open").lower()
    if state not in ("open", "closed"):
        state = "open"

    resource_labels = _dig(incident, "resource", "labels") or {}
    service = (
        resource_labels.get("service_name")
        or resource_labels.get("service")
        or _dig(incident, "resource_display_name")
        or "unknown"
    )

    return ParsedAlert(
        incident_id=str(incident_id),
        state=state,
        started_at=_rfc3339(incident.get("started_at") or incident.get("startedAt")),
        ended_at=_rfc3339(incident.get("ended_at") or incident.get("endedAt")),
        service=str(service),
        metric_type=_dig(incident, "metric", "type"),
        condition_name=incident.get("condition_name") or _dig(incident, "condition", "displayName"),
        policy_name=incident.get("policy_name") or incident.get("policyName"),
        observed_value=_as_float(incident.get("observed_value") or incident.get("observedValue")),
        threshold_value=_as_float(
            incident.get("threshold_value")
            or _dig(incident, "condition", "conditionThreshold", "thresholdValue")
        ),
        summary=str(incident.get("summary") or ""),
        documentation=str(_dig(incident, "documentation", "content") or ""),
        message_id=payload.get("_message_id"),
        raw=payload,
    )


def parse_push(body: dict) -> ParsedAlert:
    """The whole ingest path in one call."""
    return parse_notification(decode_push(body))
