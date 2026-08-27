"""Deterministic severity rules.

Each rule is a separate type that recognises one situation and speaks for it. A new
rule is a new class added to the RuleBook rather than another branch in a growing
conditional, so adding one cannot change how the existing rules behave.

Nothing here performs I/O or reads a clock it was not given, which is what makes
the rubric testable without GCP and identical across two occurrences of a failure.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Protocol

from agents.common.alert import Alert
from agents.common.schemas import Action, Decision, Severity

# The target-env pipeline, most upstream first. Failures propagate along it, so the
# earliest failing service in a storm is the suspect and the rest are symptoms.
PIPELINE = ("news-scraper", "llm-classifier", "execution-layer")

WRITE_PATH_SERVICE = "execution-layer"
CLASSIFIER_SERVICE = "llm-classifier"

FLAP_WINDOW = timedelta(seconds=60)
CLASSIFIER_STALL_RATE = 0.20
LOW_CONFIDENCE = 0.5

CERTAIN = 1.0
NEARLY_CERTAIN = 0.95
CONFIDENT = 0.9
TENTATIVE = 0.4


@dataclass(frozen=True)
class Moment:
    """The instant a decision is being made, passed in rather than read from a clock.

    Rules that call datetime.now() themselves are neither repeatable nor testable,
    and two occurrences of one failure would classify differently by accident.
    """

    timestamp: str | None = None


class SeverityRule(Protocol):
    """One recognisable situation and the verdict it implies."""

    def recognises(self, alert: Alert, moment: Moment) -> bool: ...

    def decide(self, alert: Alert, moment: Moment) -> Decision: ...


class ResolvedIncident:
    """A closed incident costs no model call, whatever else is true of it."""

    def recognises(self, alert: Alert, moment: Moment) -> bool:
        return alert.is_resolved

    def decide(self, alert: Alert, moment: Moment) -> Decision:
        return Decision(
            severity=Severity.SEV4,
            confidence=CERTAIN,
            page_human=False,
            rationale=(
                f"Incident on {alert.service} is already closed; recording it and "
                "auto-closing without diagnosis."
            ),
        )


class BriefFlap:
    """Barely over threshold, open for less than a minute. Noise, not an incident."""

    def recognises(self, alert: Alert, moment: Moment) -> bool:
        opened_recently = alert.opened_within(FLAP_WINDOW, moment.timestamp)
        return opened_recently and alert.reading.sits_within_margin()

    def decide(self, alert: Alert, moment: Moment) -> Decision:
        return Decision(
            severity=Severity.SEV4,
            confidence=CONFIDENT,
            page_human=False,
            rationale=(
                f"{alert.service} crossed its threshold by a narrow margin for under "
                f"{int(FLAP_WINDOW.total_seconds())}s. Flap, not an incident."
            ),
        )


class WritePathDown:
    """The executor erroring means positions are being lost, not delayed."""

    def recognises(self, alert: Alert, moment: Moment) -> bool:
        return alert.service == WRITE_PATH_SERVICE and alert.reading.is_present

    def decide(self, alert: Alert, moment: Moment) -> Decision:
        return Decision(
            severity=Severity.SEV1,
            confidence=CERTAIN,
            page_human=True,
            rationale=(
                "execution-layer is erroring, so the write path is down and position "
                "writes are being lost rather than delayed."
            ),
        )


class ClassifierStalled:
    """Above this error rate nothing reaches the executor and the pipeline is stalled."""

    def recognises(self, alert: Alert, moment: Moment) -> bool:
        return alert.service == CLASSIFIER_SERVICE and alert.reading.reaches(
            CLASSIFIER_STALL_RATE
        )

    def decide(self, alert: Alert, moment: Moment) -> Decision:
        return Decision(
            severity=Severity.SEV2,
            confidence=NEARLY_CERTAIN,
            page_human=True,
            rationale=(
                f"llm-classifier error rate {alert.reading.as_percentage()} against a "
                f"{alert.reading.threshold_as_percentage()} threshold; the pipeline is "
                "stalled and nothing is reaching the executor."
            ),
        )


class RuleBook:
    """The rules in priority order. The first that recognises the alert speaks."""

    def __init__(self, rules: list[SeverityRule] | None = None) -> None:
        self._rules = rules if rules is not None else default_rules()

    def decide(self, alert: Alert, moment: Moment) -> Decision | None:
        """Returns None when no rule applies and the alert needs a model."""
        for rule in self._rules:
            if rule.recognises(alert, moment):
                return rule.decide(alert, moment)
        return None


def default_rules() -> list[SeverityRule]:
    return [ResolvedIncident(), BriefFlap(), WritePathDown(), ClassifierStalled()]


class ConfidenceFloor:
    """Raises a poorly understood verdict to a page rather than letting it pass quietly.

    An agent that auto-closes something it did not understand destroys trust in the
    whole fleet. One that pages on noise is merely annoying.
    """

    def __init__(self, threshold: float = LOW_CONFIDENCE) -> None:
        self._threshold = threshold

    def apply(self, decision: Decision) -> Decision:
        if decision.confidence >= self._threshold:
            return decision
        return decision.model_copy(
            update={
                "page_human": True,
                "rationale": (
                    f"{decision.rationale} Low confidence, so paging rather than "
                    "assuming noise."
                ),
            }
        )


class ActionPolicy:
    """Where a verdict goes next."""

    def action_for(self, severity: Severity) -> Action:
        return Action.AUTO_CLOSE if severity is Severity.SEV4 else Action.INVESTIGATE


class StormGrouper:
    """Collapses several alerts sharing one root cause into a single verdict.

    A verdict per alert would fan out one Diagnosis run per symptom and make the
    MTTR measurement meaningless.
    """

    def group(self, alerts: list[Alert]) -> tuple[Alert, list[str]]:
        if not alerts:
            raise ValueError("cannot group an empty alert set")
        ordered = sorted(alerts, key=self._upstream_first)
        suspect, *symptoms = ordered
        return suspect, [alert.incident_id for alert in symptoms]

    def _upstream_first(self, alert: Alert) -> tuple[int, str]:
        return (self._pipeline_position(alert.service), alert.started_at or "")

    def _pipeline_position(self, service: str) -> int:
        """Services outside the pipeline sort last and are never named as suspect."""
        if service in PIPELINE:
            return PIPELINE.index(service)
        return len(PIPELINE)
