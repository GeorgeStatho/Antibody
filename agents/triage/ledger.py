"""Triage's own record of the incidents it has seen.

One document per incident, doing three jobs that all need the same write:
deduplication, the MTTR start stamp, and the recurrence history that lets Triage
recognise a fingerprint it has met before.

This is Triage's bookkeeping, not the Memory Bank. The Memory Bank is written by
the Memory agent, under a different collection and a different service account.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from agents.common.alert import Alert
from agents.common.errors import IncidentAlreadyHandled
from agents.common.schemas import Recurrence, TriageVerdict
from agents.common.values import Fingerprint

logger = logging.getLogger(__name__)

RECURRENCE_WINDOW = timedelta(days=30)
RECURRENCE_SCAN_LIMIT = 50

CLAIMED = "claimed"
DECIDED = "decided"

__all__ = ["IncidentAlreadyHandled", "IncidentLedger"]


class IncidentLedger:
    """Reads and writes the verdict ledger. The Firestore client is injected."""

    def __init__(self, collection) -> None:
        self._collection = collection

    def claim(self, alert: Alert, received_at: str) -> None:
        """Claims the incident, or raises if another delivery got there first.

        Cloud Monitoring re-notifies and Pub/Sub delivers at least once. Without
        this claim one incident becomes several Diagnosis runs and the MTTR figures
        stop meaning anything.
        """
        from google.cloud.exceptions import Conflict

        try:
            self._collection.document(alert.incident_id).create(
                {
                    "incident_id": alert.incident_id,
                    "service": alert.service,
                    "state": alert.state,
                    "t_alert_received": received_at,
                    "message_id": alert.message_id,
                    "status": CLAIMED,
                }
            )
        except Conflict as error:
            raise IncidentAlreadyHandled(alert.incident_id) from error

    def recurrence_of(self, fingerprint: Fingerprint) -> Recurrence:
        """How often this fingerprint has fired lately.

        Best effort: a failure here costs one field on the verdict, never the
        verdict itself.
        """
        try:
            documents = list(self._recent_matches(fingerprint))
        except Exception:  # noqa: BLE001 - diagnostics, never load-bearing
            logger.exception("Recurrence lookup failed; continuing without it")
            return Recurrence()

        last_seen = documents[0].get("t_alert_received") if documents else None
        return Recurrence(count_recent=len(documents), last_seen=last_seen)

    def _recent_matches(self, fingerprint: Fingerprint):
        from google.cloud.firestore import Query

        cutoff = datetime.now(tz=timezone.utc) - RECURRENCE_WINDOW
        return (
            self._collection.where("symptom_fingerprint", "==", fingerprint.value)
            .where("t_alert_received", ">=", cutoff.isoformat().replace("+00:00", "Z"))
            .order_by("t_alert_received", direction=Query.DESCENDING)
            .limit(RECURRENCE_SCAN_LIMIT)
            .stream()
        )

    def record(self, verdict: TriageVerdict) -> None:
        try:
            self._collection.document(verdict.incident_id).set(
                {**verdict.model_dump(mode="json"), "status": DECIDED}, merge=True
            )
        except Exception:  # noqa: BLE001
            logger.exception("Could not record verdict %s", verdict.incident_id)
