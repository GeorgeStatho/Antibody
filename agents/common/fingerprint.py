"""The symptom fingerprint — the Memory Bank's primary key.

Triage mints the key, Memory persists under it, Diagnosis looks it up. All three
use this one class, because a second implementation that disagreed by a character
would turn every memory hit into a silent miss.

WARNING. Changing the hashed inputs or the normalisation invalidates every
signature already stored. If that is deliberate, raise VERSION and treat the older
signatures as a separate keyspace rather than silently re-keying them.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from agents.common.values import Direction, Fingerprint, MetricReading

VERSION = 1
FINGERPRINT_LENGTH = 16
UNKNOWN = "unknown"

_UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.I)
_DIGITS = re.compile(r"\d+(?:\.\d+)?")
_SEPARATORS = re.compile(r"[^a-z0-9]+")

_ABSENCE_PHRASES = ("absent", "no data")
_DROP_PHRASES = ("below", "less", "drop")
_SPIKE_PHRASES = ("above", "greater", "exceed")


@dataclass(frozen=True)
class SymptomInputs:
    """The four stable strings that identify a failure class.

    Stable is the operative word: observed values, incident ids, revision names and
    timestamps all differ between two occurrences of one failure, so none of them
    appear here.
    """

    service: str
    metric: str
    condition: str
    direction: Direction

    def as_dict(self) -> dict:
        return {
            "service": self.service,
            "metric": self.metric,
            "condition": self.condition,
            "direction": self.direction.value,
        }


class LabelNormaliser:
    """Strips the churn that differs between occurrences of one failure class."""

    def normalise(self, label: str | None) -> str:
        if not label:
            return UNKNOWN
        stripped = _UUID.sub("", label.strip().lower())
        without_numbers = _DIGITS.sub("", stripped)
        return _SEPARATORS.sub("-", without_numbers).strip("-") or UNKNOWN

    def normalise_metric(self, metric_type: str | None) -> str:
        """Keeps the metric path but drops the exporting host prefix."""
        if not metric_type:
            return UNKNOWN
        path = self._without_host(metric_type.strip().lower())
        return _SEPARATORS.sub("-", path).strip("-") or UNKNOWN

    def _without_host(self, metric_type: str) -> str:
        host, separator, path = metric_type.partition("/")
        return path if separator and "." in host else metric_type


class DirectionReader:
    """Reads which way a metric moved, from its values or from its condition text."""

    def read(self, reading: MetricReading, condition: str | None = None) -> Direction:
        description = (condition or "").lower()
        if self._describes_absence(description):
            return Direction.ABSENT
        if reading.is_comparable:
            return reading.direction()
        return self._from_description(description)

    def _describes_absence(self, description: str) -> bool:
        return any(phrase in description for phrase in _ABSENCE_PHRASES)

    def _from_description(self, description: str) -> Direction:
        if any(phrase in description for phrase in _DROP_PHRASES):
            return Direction.DROP
        if any(phrase in description for phrase in _SPIKE_PHRASES):
            return Direction.SPIKE
        return Direction.UNKNOWN


class SymptomFingerprinter:
    """Derives a stable key for a failure class. Deterministic and side-effect free."""

    def __init__(
        self,
        normaliser: LabelNormaliser | None = None,
        direction_reader: DirectionReader | None = None,
    ) -> None:
        self._normaliser = normaliser or LabelNormaliser()
        self._direction_reader = direction_reader or DirectionReader()

    def describe(
        self,
        service: str | None,
        metric: str | None,
        condition: str | None,
        reading: MetricReading,
    ) -> SymptomInputs:
        return SymptomInputs(
            service=service or UNKNOWN,
            metric=metric or UNKNOWN,
            condition=condition or UNKNOWN,
            direction=self._direction_reader.read(reading, condition),
        )

    def fingerprint(self, inputs: SymptomInputs) -> Fingerprint:
        key = "|".join(
            (
                str(VERSION),
                self._normaliser.normalise(inputs.service),
                self._normaliser.normalise_metric(inputs.metric),
                self._normaliser.normalise(inputs.condition),
                inputs.direction.value,
            )
        )
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        return Fingerprint(digest[:FINGERPRINT_LENGTH])
