"""Triage as one collaborator: alert in, verdict out.

Order is load-bearing.

The scan comes first and happens for every alert, including the ones the rules
could settle on their own. Scanning only the alerts headed for a model would leave
a poisoned body unexamined whenever its metrics happened to match a rule, which is
precisely the realistic attack: inject into a log line during a genuine outage. A
blocked body is an incident in its own right and outranks every other rule.

The fingerprint is derived next, and never by a model. The deterministic rules
speak after that. Only what survives all of it is put to a model.
"""

from __future__ import annotations

import logging

from agents.common.alert import Alert, utc_now
from agents.common.armor import TextScanner
from agents.common.fingerprint import SymptomFingerprinter, SymptomInputs
from agents.common.schemas import ArmorVerdict, Decision, Recurrence, Signals, TriageVerdict
from agents.common.values import Fingerprint
from agents.triage.classifier import InjectionResponse, ModelClassifier, UnscannedTextPolicy
from agents.triage.ledger import IncidentLedger
from agents.triage.publisher import VerdictPublisher
from agents.triage.rules import ActionPolicy, ConfidenceFloor, Moment, RuleBook

logger = logging.getLogger(__name__)


class TriageService:
    """Decides one alert and hands the verdict onward."""

    def __init__(
        self,
        fingerprinter: SymptomFingerprinter,
        rule_book: RuleBook,
        scanner: TextScanner,
        classifier: ModelClassifier,
        unscanned_policy: UnscannedTextPolicy,
        ledger: IncidentLedger,
        publisher: VerdictPublisher,
        confidence_floor: ConfidenceFloor | None = None,
        action_policy: ActionPolicy | None = None,
    ) -> None:
        self._fingerprinter = fingerprinter
        self._rule_book = rule_book
        self._scanner = scanner
        self._classifier = classifier
        self._unscanned_policy = unscanned_policy
        self._ledger = ledger
        self._publisher = publisher
        self._confidence_floor = confidence_floor or ConfidenceFloor()
        self._action_policy = action_policy or ActionPolicy()
        self._injection = InjectionResponse()

    async def handle(self, alert: Alert) -> TriageVerdict:
        """Claim, decide, record, publish. Raises IncidentAlreadyHandled on a duplicate."""
        received_at = utc_now()
        self._ledger.claim(alert, received_at)

        symptom = self._describe(alert)
        fingerprint = self._fingerprinter.fingerprint(symptom)
        recurrence = self._ledger.recurrence_of(fingerprint)

        verdict = await self.decide(alert, Moment(received_at), recurrence)
        self._ledger.record(verdict)
        self._publisher.publish(verdict)
        self._log(verdict)
        return verdict

    async def decide(
        self,
        alert: Alert,
        moment: Moment,
        recurrence: Recurrence | None = None,
        correlated_alerts: list[str] | None = None,
    ) -> TriageVerdict:
        symptom = self._describe(alert)
        fingerprint = self._fingerprinter.fingerprint(symptom)

        armor_verdict = self._scanner.scan(alert.untrusted_text())
        decision = await self._judge(alert, armor_verdict, moment)
        return self._assemble(
            alert, decision, armor_verdict, fingerprint, symptom,
            moment, recurrence, correlated_alerts,
        )

    async def _judge(
        self, alert: Alert, armor_verdict: ArmorVerdict, moment: Moment
    ) -> Decision:
        """A blocked body outranks the rubric; otherwise the rules speak first."""
        if armor_verdict.blocked:
            return self._injection.decide(armor_verdict.findings)

        settled = self._rule_book.decide(alert, moment)
        if settled:
            return settled

        if armor_verdict.is_clean:
            return await self._classifier.classify(alert)
        return await self._unscanned_policy.decide(alert, armor_verdict, self._classifier)

    def _describe(self, alert: Alert) -> SymptomInputs:
        return self._fingerprinter.describe(
            service=alert.service,
            metric=alert.metric_type,
            condition=alert.condition_name,
            reading=alert.reading,
        )

    def _assemble(
        self,
        alert: Alert,
        decision: Decision,
        armor_verdict: ArmorVerdict,
        fingerprint: Fingerprint,
        symptom: SymptomInputs,
        moment: Moment,
        recurrence: Recurrence | None,
        correlated_alerts: list[str] | None,
    ) -> TriageVerdict:
        judged = self._confidence_floor.apply(decision)
        return TriageVerdict(
            incident_id=alert.incident_id,
            received_at=moment.timestamp or utc_now(),
            severity=judged.severity,
            confidence=judged.confidence,
            page_human=judged.page_human,
            action=self._action_policy.action_for(judged.severity),
            suspect_service=alert.service,
            symptom_fingerprint=fingerprint.value,
            fingerprint_inputs=symptom.as_dict(),
            signals=self._signals(alert, moment),
            correlated_alerts=correlated_alerts or [],
            recurrence=recurrence or Recurrence(),
            rationale=judged.rationale,
            armor=armor_verdict,
        )

    def _signals(self, alert: Alert, moment: Moment) -> Signals:
        elapsed = alert.seconds_open(moment.timestamp)
        return Signals(
            observed_value=alert.reading.observed,
            threshold_value=alert.reading.threshold,
            seconds_open=int(elapsed) if elapsed is not None else None,
            state=alert.state,
        )

    def _log(self, verdict: TriageVerdict) -> None:
        logger.info(
            "Triaged %s as %s (%s), fingerprint %s",
            verdict.incident_id,
            verdict.severity.value,
            verdict.action.value,
            verdict.symptom_fingerprint,
        )
