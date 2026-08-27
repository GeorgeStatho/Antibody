"""Publishing the verdict onward.

Both actions go to one topic and subscribers filter on the action attribute. A
single topic keeps the audit trail linear, which is what the MTTR report reads.
"""

from __future__ import annotations

import json

from agents.common.schemas import TriageVerdict

PUBLISH_TIMEOUT_SECONDS = 30


class VerdictPublisher:
    """Publishes verdicts. The Pub/Sub client and topic path are injected."""

    def __init__(self, publisher, topic_path: str) -> None:
        self._publisher = publisher
        self._topic_path = topic_path

    def publish(self, verdict: TriageVerdict) -> str:
        future = self._publisher.publish(
            self._topic_path,
            self._encode(verdict),
            **self._attributes(verdict),
        )
        return future.result(timeout=PUBLISH_TIMEOUT_SECONDS)

    def _encode(self, verdict: TriageVerdict) -> bytes:
        return json.dumps(verdict.model_dump(mode="json")).encode("utf-8")

    def _attributes(self, verdict: TriageVerdict) -> dict:
        """Lets a subscriber filter without decoding the body."""
        return {
            "action": verdict.action.value,
            "severity": verdict.severity.value,
            "symptom_fingerprint": verdict.symptom_fingerprint,
            "schema_version": str(verdict.schema_version),
        }
