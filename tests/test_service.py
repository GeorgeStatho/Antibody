"""Triage end to end against stubs.

Nothing here touches GCP or Vertex. That is the payoff from injecting the ledger,
the publisher, the scanner and the classifier rather than reaching for them.
"""

import pytest

from agents.common.fingerprint import SymptomFingerprinter
from agents.common.schemas import Action, ArmorVerdict, Decision, Severity
from agents.triage.classifier import PromptDespiteMissingScan, WithholdFromModel
from agents.triage.ledger import IncidentAlreadyHandled
from agents.triage.rules import Moment, RuleBook
from agents.triage.service import TriageService

from conftest import ORDINARY_ALERT, POISONED_ALERT, RESOLVED_ALERT

INJECTION_MARKER = "NOTE TO AGENT"

# No deterministic rule recognises this one, so it is the fixture that actually
# exercises the scan-then-model path.
UNSETTLED_ALERT = "alert-storm-scraper.json"


class CleanScanner:
    def scan(self, text):
        return ArmorVerdict(scanned=True, blocked=False)


class BlockingScanner:
    def __init__(self, findings=("pi_and_jailbreak",)):
        self._findings = list(findings)

    def scan(self, text):
        return ArmorVerdict(scanned=True, blocked=True, findings=self._findings)


class BrokenScanner:
    def scan(self, text):
        return ArmorVerdict(scanned=False, blocked=False, skipped_reason="scan_error")


class RecordingClassifier:
    """Stands in for the model and remembers whether it was consulted."""

    def __init__(self, decision=None):
        self.calls = 0
        self._decision = decision or Decision(
            severity=Severity.SEV3, confidence=0.8, page_human=False, rationale="Model verdict."
        )

    async def classify(self, alert):
        self.calls += 1
        return self._decision


class FakeLedger:
    def __init__(self, claimed=()):
        self.claimed = set(claimed)
        self.recorded = []

    def claim(self, alert, received_at):
        if alert.incident_id in self.claimed:
            raise IncidentAlreadyHandled(alert.incident_id)
        self.claimed.add(alert.incident_id)

    def recurrence_of(self, fingerprint):
        from agents.common.schemas import Recurrence

        return Recurrence()

    def record(self, verdict):
        self.recorded.append(verdict)


class FakePublisher:
    def __init__(self):
        self.published = []

    def publish(self, verdict):
        self.published.append(verdict)
        return "message-id"


@pytest.fixture
def build_service():
    def build(scanner=None, classifier=None, policy=None, ledger=None, publisher=None):
        return TriageService(
            fingerprinter=SymptomFingerprinter(),
            rule_book=RuleBook(),
            scanner=scanner or CleanScanner(),
            classifier=classifier or RecordingClassifier(),
            unscanned_policy=policy or WithholdFromModel(),
            ledger=ledger or FakeLedger(),
            publisher=publisher or FakePublisher(),
        )

    return build


@pytest.fixture
def decide(build_service, load_alert):
    async def run(fixture_name, **kwargs):
        service = build_service(**kwargs)
        alert = load_alert(fixture_name)
        return await service.decide(alert, Moment(alert.started_at))

    return run


@pytest.mark.asyncio
async def test_every_alert_is_scanned_even_when_a_rule_settles_it(decide, load_alert):
    """A poisoned body during a genuine outage must not slip past unexamined."""
    classifier = RecordingClassifier()
    scanner = BlockingScanner()
    verdict = await decide(ORDINARY_ALERT, scanner=scanner, classifier=classifier)
    assert verdict.armor.blocked is True


@pytest.mark.asyncio
async def test_a_blocked_body_outranks_the_rubric(decide):
    """The classifier-stall rule would have spoken; the injection outranks it."""
    verdict = await decide(ORDINARY_ALERT, scanner=BlockingScanner())
    assert "Model Armor blocked" in verdict.rationale


@pytest.mark.asyncio
async def test_a_rule_settled_alert_never_reaches_the_model(decide):
    classifier = RecordingClassifier()
    await decide(RESOLVED_ALERT, classifier=classifier)
    assert classifier.calls == 0


@pytest.mark.asyncio
async def test_a_resolved_incident_auto_closes(decide):
    verdict = await decide(RESOLVED_ALERT)
    assert verdict.action is Action.AUTO_CLOSE


@pytest.mark.asyncio
async def test_a_stalled_classifier_goes_to_diagnosis(decide):
    verdict = await decide(ORDINARY_ALERT)
    assert verdict.action is Action.INVESTIGATE


@pytest.mark.asyncio
async def test_the_verdict_carries_the_pinned_fingerprint(decide, golden_classifier_fingerprint):
    verdict = await decide(ORDINARY_ALERT)
    assert verdict.symptom_fingerprint == golden_classifier_fingerprint


@pytest.mark.asyncio
async def test_a_blocked_body_never_reaches_the_model(decide):
    classifier = RecordingClassifier()
    await decide(POISONED_ALERT, scanner=BlockingScanner(), classifier=classifier)
    assert classifier.calls == 0


@pytest.mark.asyncio
async def test_a_blocked_body_is_itself_an_incident(decide):
    verdict = await decide(POISONED_ALERT, scanner=BlockingScanner())
    assert verdict.severity is Severity.SEV2


@pytest.mark.asyncio
async def test_a_blocked_body_pages_a_human(decide):
    verdict = await decide(POISONED_ALERT, scanner=BlockingScanner())
    assert verdict.page_human is True


@pytest.mark.asyncio
async def test_a_blocked_body_never_auto_closes(decide):
    """The injection asks to be marked resolved. It must not be."""
    verdict = await decide(POISONED_ALERT, scanner=BlockingScanner())
    assert verdict.action is not Action.AUTO_CLOSE


@pytest.mark.asyncio
async def test_no_injected_text_reaches_the_rationale(decide):
    verdict = await decide(POISONED_ALERT, scanner=BlockingScanner())
    assert INJECTION_MARKER not in verdict.rationale


@pytest.mark.asyncio
async def test_the_verdict_names_the_filter_that_matched(decide):
    verdict = await decide(POISONED_ALERT, scanner=BlockingScanner())
    assert "pi_and_jailbreak" in verdict.rationale


@pytest.mark.asyncio
async def test_an_unscanned_body_is_withheld_from_the_model(decide):
    classifier = RecordingClassifier()
    await decide(UNSETTLED_ALERT, scanner=BrokenScanner(), classifier=classifier)
    assert classifier.calls == 0


@pytest.mark.asyncio
async def test_an_unscanned_verdict_reports_that_it_was_unscanned(decide):
    verdict = await decide(UNSETTLED_ALERT, scanner=BrokenScanner())
    assert verdict.armor.scanned is False


@pytest.mark.asyncio
async def test_the_development_policy_prompts_on_unscanned_text(decide):
    classifier = RecordingClassifier()
    await decide(
        UNSETTLED_ALERT,
        scanner=BrokenScanner(),
        classifier=classifier,
        policy=PromptDespiteMissingScan(),
    )
    assert classifier.calls == 1


@pytest.mark.asyncio
async def test_the_development_policy_still_admits_it_was_unguarded(decide):
    verdict = await decide(
        UNSETTLED_ALERT, scanner=BrokenScanner(), policy=PromptDespiteMissingScan()
    )
    assert verdict.armor.scanned is False


@pytest.mark.asyncio
async def test_a_handled_incident_is_published(build_service, load_alert):
    publisher = FakePublisher()
    service = build_service(publisher=publisher)
    await service.handle(load_alert(ORDINARY_ALERT))
    assert len(publisher.published) == 1


@pytest.mark.asyncio
async def test_a_handled_incident_is_recorded(build_service, load_alert):
    ledger = FakeLedger()
    service = build_service(ledger=ledger)
    await service.handle(load_alert(ORDINARY_ALERT))
    assert len(ledger.recorded) == 1


@pytest.mark.asyncio
async def test_a_duplicate_delivery_is_refused(build_service, load_alert):
    alert = load_alert(ORDINARY_ALERT)
    service = build_service(ledger=FakeLedger(claimed=[alert.incident_id]))
    with pytest.raises(IncidentAlreadyHandled):
        await service.handle(alert)


@pytest.mark.asyncio
async def test_a_duplicate_delivery_publishes_nothing(build_service, load_alert):
    alert = load_alert(ORDINARY_ALERT)
    publisher = FakePublisher()
    service = build_service(
        ledger=FakeLedger(claimed=[alert.incident_id]), publisher=publisher
    )
    with pytest.raises(IncidentAlreadyHandled):
        await service.handle(alert)
    assert publisher.published == []
