"""Value objects shared across the fleet.

Each replaces a primitive that was carrying meaning the type system could not see.
The trust distinction is the important one: TrustedFacts and UntrustedText are
different types precisely so that handing attacker-reachable text to something
expecting Cloud Monitoring's own numbers is a mistake you cannot make quietly.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum

FLAP_MARGIN_MULTIPLIER = 1.5


class Direction(str, Enum):
    """Which way a metric moved relative to its threshold."""

    SPIKE = "spike"
    DROP = "drop"
    ABSENT = "absent"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class MetricReading:
    """An observed value against its threshold.

    Every threshold comparison in the fleet lives here, so the boundary conditions
    sit in one place rather than being re-derived at each call site.
    """

    observed: float | None = None
    threshold: float | None = None

    @property
    def is_comparable(self) -> bool:
        return self.observed is not None and self.threshold is not None

    @property
    def exceeds_threshold(self) -> bool:
        return self.is_comparable and self.observed > self.threshold

    @property
    def falls_below_threshold(self) -> bool:
        return self.is_comparable and self.observed < self.threshold

    @property
    def is_present(self) -> bool:
        return self.observed is not None and self.observed > 0

    def sits_within_margin(self, multiplier: float = FLAP_MARGIN_MULTIPLIER) -> bool:
        """True when the observed value only just crossed its threshold."""
        if not self.is_comparable or self.threshold == 0:
            return False
        return abs(self.observed) <= abs(self.threshold) * multiplier

    def reaches(self, rate: float) -> bool:
        return self.observed is not None and self.observed >= rate

    def direction(self) -> Direction:
        if self.exceeds_threshold:
            return Direction.SPIKE
        if self.falls_below_threshold:
            return Direction.DROP
        return Direction.UNKNOWN

    def as_percentage(self) -> str:
        return "unknown" if self.observed is None else f"{self.observed:.0%}"

    def threshold_as_percentage(self) -> str:
        return "unknown" if self.threshold is None else f"{self.threshold:.0%}"


@dataclass(frozen=True)
class Fingerprint:
    """The Memory Bank's primary key.

    A dedicated type because a bare string here is indistinguishable from an
    incident id or a message id, and confusing the three produces a memory miss
    that looks exactly like a first occurrence.
    """

    value: str

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class UntrustedText:
    """Text an attacker can reach: alert summaries and documentation bodies.

    This is what Model Armor scans and the only text that may become prompt
    content. It is a distinct type so that reaching a model with it requires
    passing through a scanner rather than merely remembering to.
    """

    content: str

    @property
    def is_empty(self) -> bool:
        return not self.content.strip()

    def __str__(self) -> str:
        return self.content


@dataclass(frozen=True)
class TrustedFacts:
    """Fields Cloud Monitoring generated. Safe to interpolate verbatim."""

    values: dict

    def as_json(self) -> str:
        return json.dumps(self.values, indent=2, sort_keys=True)
