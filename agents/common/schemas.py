"""Wire contracts for the fleet.

Every message that crosses an agent boundary is one of these. They are the reason
Diagnosis can trust its input: by the time a verdict reaches it, Triage has already
parsed, scanned, and fingerprinted the untrusted alert.

SCHEMA_VERSION is not decoration. Consumers must reject an unknown version loudly
rather than duck-typing their way through it — a silent field rename otherwise
becomes a silent Memory Bank miss, which is the one failure mode that looks like
success.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION = 1


class Severity(str, Enum):
    """Ordered worst-first so `min()` picks the most severe of a storm."""

    SEV1 = "sev1"
    SEV2 = "sev2"
    SEV3 = "sev3"
    SEV4 = "sev4"

    @property
    def rank(self) -> int:
        return {"sev1": 1, "sev2": 2, "sev3": 3, "sev4": 4}[self.value]


class Action(str, Enum):
    INVESTIGATE = "investigate"  # -> Diagnosis
    AUTO_CLOSE = "auto_close"  # -> Memory, no diagnosis run


class FingerprintInputs(BaseModel):
    """The exact strings hashed into `symptom_fingerprint`.

    Emitted alongside the hash so a memory miss is debuggable in one diff instead
    of a re-run. If these four fields match and the hashes do not, the bug is in
    fingerprint.py; if the hashes match and the fields do not, something is
    fabricating keys.
    """

    model_config = ConfigDict(frozen=True)

    service: str
    metric: str
    condition: str
    direction: Literal["spike", "drop", "absent", "unknown"]


class Signals(BaseModel):
    """Trusted numbers, straight from Cloud Monitoring. Never model-authored."""

    observed_value: float | None = None
    threshold_value: float | None = None
    window_s: int | None = None
    state: Literal["open", "closed"] = "open"


class ArmorResult(BaseModel):
    """Outcome of the Model Armor scan over the untrusted fields.

    `scanned=False` means the guardrail was not consulted at all — either the
    template is unset or the scan itself errored. That is a materially different
    claim from `scanned=True, blocked=False`, and the two must never be collapsed.
    """

    scanned: bool = False
    blocked: bool = False
    findings: list[str] = Field(default_factory=list)
    skipped_reason: str | None = None


class Recurrence(BaseModel):
    """What Triage's own ledger knows about this fingerprint's history."""

    count_30d: int = 0
    last_seen: str | None = None


class TriageVerdict(BaseModel):
    """Triage's only output. Published to TOPIC_VERDICTS.

    Consumed by Diagnosis (action=investigate) or Memory (action=auto_close).
    """

    schema_version: int = SCHEMA_VERSION

    incident_id: str
    received_at: str  # RFC3339 UTC, stamped by Triage on ingest — the MTTR t0

    severity: Severity
    confidence: float = Field(ge=0.0, le=1.0)
    page_human: bool
    action: Action

    suspect_service: str
    symptom_fingerprint: str = Field(min_length=16, max_length=16)
    fingerprint_inputs: FingerprintInputs

    signals: Signals = Field(default_factory=Signals)
    correlated_alerts: list[str] = Field(default_factory=list)
    recurrence: Recurrence = Field(default_factory=Recurrence)

    rationale: str
    armor: ArmorResult = Field(default_factory=ArmorResult)


class VerdictDecision(BaseModel):
    """The narrow slice the LLM is allowed to author.

    Everything else on TriageVerdict is computed in Python before the model is
    called. This is the agent's `output_schema`, and keeping it this small is the
    point: the model contributes judgment on ambiguous cases and one sentence of
    prose, nothing that Diagnosis or Memory will key on.
    """

    severity: Severity
    confidence: float = Field(ge=0.0, le=1.0)
    page_human: bool
    rationale: str = Field(max_length=400)


def require_schema_version(payload: dict, *, expected: int = SCHEMA_VERSION) -> None:
    """Fail loudly on an unrecognised wire version. Call this in every consumer."""
    got = payload.get("schema_version")
    if got != expected:
        raise ValueError(
            f"unsupported schema_version {got!r} (expected {expected}) — "
            "refusing to duck-type; bump the consumer or fix the producer"
        )
