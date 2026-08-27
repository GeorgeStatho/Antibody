"""Wire contracts for the fleet.

Every message that crosses an agent boundary is one of these. They are the reason
Diagnosis can trust its input: by the time a verdict reaches it, Triage has already
parsed, scanned and fingerprinted the untrusted alert.

WARNING. Consumers must reject an unrecognised SCHEMA_VERSION rather than
duck-typing their way through it. A silent field rename otherwise becomes a silent
Memory Bank miss, which is the one failure that looks like success.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

SCHEMA_VERSION = 1
RATIONALE_LIMIT = 400


class Severity(str, Enum):
    SEV1 = "sev1"
    SEV2 = "sev2"
    SEV3 = "sev3"
    SEV4 = "sev4"


class Action(str, Enum):
    INVESTIGATE = "investigate"
    AUTO_CLOSE = "auto_close"


class Signals(BaseModel):
    """Trusted numbers, straight from Cloud Monitoring. Never model-authored."""

    observed_value: float | None = None
    threshold_value: float | None = None
    seconds_open: int | None = None
    state: str = "open"


class ArmorVerdict(BaseModel):
    """Outcome of the Model Armor scan over the untrusted region of an alert."""

    scanned: bool = False
    blocked: bool = False
    findings: list[str] = Field(default_factory=list)
    skipped_reason: str | None = None

    @property
    def is_clean(self) -> bool:
        """True only when the text was scanned and came back clear.

        An unscanned result is not a clean one, and collapsing the two is how an
        agent ships looking guarded while being unguarded.
        """
        return self.scanned and not self.blocked


class Recurrence(BaseModel):
    """What Triage's own ledger knows about this fingerprint's history."""

    count_recent: int = 0
    last_seen: str | None = None


class Decision(BaseModel):
    """The narrow slice a model is allowed to author.

    Everything else on TriageVerdict is derived before the model is consulted.
    Keeping this small is the point: nothing Diagnosis or Memory keys on is written
    by a model.
    """

    severity: Severity
    confidence: float = Field(ge=0.0, le=1.0)
    page_human: bool
    rationale: str = Field(max_length=RATIONALE_LIMIT)


class TriageVerdict(BaseModel):
    """Triage's only output."""

    schema_version: int = SCHEMA_VERSION

    incident_id: str
    received_at: str

    severity: Severity
    confidence: float = Field(ge=0.0, le=1.0)
    page_human: bool
    action: Action

    suspect_service: str
    symptom_fingerprint: str
    fingerprint_inputs: dict

    signals: Signals = Field(default_factory=Signals)
    correlated_alerts: list[str] = Field(default_factory=list)
    recurrence: Recurrence = Field(default_factory=Recurrence)

    rationale: str
    armor: ArmorVerdict = Field(default_factory=ArmorVerdict)


class UnsupportedSchemaVersion(ValueError):
    """Raised by consumers on a wire version they were not written against."""


def require_supported_version(payload: dict, expected: int = SCHEMA_VERSION) -> None:
    received = payload.get("schema_version")
    if received != expected:
        raise UnsupportedSchemaVersion(
            f"schema_version {received!r} is not supported (expected {expected})"
        )
