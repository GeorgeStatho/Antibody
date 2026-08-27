"""The deterministic rubric. No GCP, no model, no clock beyond the moment passed in."""

import pytest

from agents.common.schemas import Action, Severity
from agents.triage.rules import (
    ActionPolicy,
    BriefFlap,
    ClassifierStalled,
    ConfidenceFloor,
    Moment,
    ResolvedIncident,
    RuleBook,
    StormGrouper,
    WritePathDown,
)

from conftest import FLAPPING_ALERT, ORDINARY_ALERT, RESOLVED_ALERT, WRITE_PATH_ALERT

STORM_FIXTURES = (
    "alert-storm-executor.json",
    "alert-storm-classifier.json",
    "alert-storm-scraper.json",
)


@pytest.fixture
def rule_book():
    return RuleBook()


@pytest.fixture
def decide(rule_book, load_alert):
    def run(fixture_name):
        alert = load_alert(fixture_name)
        return rule_book.decide(alert, Moment(alert.started_at))

    return run


def test_a_resolved_incident_is_noise(decide):
    assert decide(RESOLVED_ALERT).severity is Severity.SEV4


def test_a_resolved_incident_does_not_page(decide):
    assert decide(RESOLVED_ALERT).page_human is False


def test_a_brief_flap_is_noise(decide):
    assert decide(FLAPPING_ALERT).severity is Severity.SEV4


def test_a_failing_write_path_is_the_worst_case(decide):
    assert decide(WRITE_PATH_ALERT).severity is Severity.SEV1


def test_a_failing_write_path_pages(decide):
    assert decide(WRITE_PATH_ALERT).page_human is True


def test_a_stalled_classifier_is_second_worst(decide):
    assert decide(ORDINARY_ALERT).severity is Severity.SEV2


def test_an_unrecognised_alert_is_left_to_the_model(decide):
    assert decide("alert-storm-scraper.json") is None


def test_a_resolved_incident_is_recognised_before_anything_else(load_alert):
    """It must cost no model call whatever else is true of it."""
    alert = load_alert(RESOLVED_ALERT)
    assert ResolvedIncident().recognises(alert, Moment(alert.started_at))


def test_a_healthy_classifier_is_not_a_stall(load_alert):
    alert = load_alert(FLAPPING_ALERT)
    assert ClassifierStalled().recognises(alert, Moment(alert.started_at)) is False


def test_a_long_running_incident_is_not_a_flap(load_alert):
    alert = load_alert(ORDINARY_ALERT)
    later = "2026-08-26T23:59:00Z"
    assert BriefFlap().recognises(alert, Moment(later)) is False


def test_a_healthy_executor_is_not_a_write_path_failure(load_alert):
    alert = load_alert(ORDINARY_ALERT)
    assert WritePathDown().recognises(alert, Moment(alert.started_at)) is False


def test_an_empty_rule_book_decides_nothing(load_alert):
    alert = load_alert(WRITE_PATH_ALERT)
    assert RuleBook(rules=[]).decide(alert, Moment(alert.started_at)) is None


def test_noise_goes_to_memory_rather_than_diagnosis():
    assert ActionPolicy().action_for(Severity.SEV4) is Action.AUTO_CLOSE


def test_a_real_incident_goes_to_diagnosis():
    assert ActionPolicy().action_for(Severity.SEV2) is Action.INVESTIGATE


def test_a_confident_verdict_is_left_alone(decide):
    original = decide(WRITE_PATH_ALERT)
    assert ConfidenceFloor().apply(original) == original


def test_an_unconfident_verdict_is_raised_to_a_page(decide):
    unsure = decide(RESOLVED_ALERT).model_copy(update={"confidence": 0.2})
    assert ConfidenceFloor().apply(unsure).page_human is True


def test_an_unconfident_verdict_keeps_its_severity(decide):
    unsure = decide(RESOLVED_ALERT).model_copy(update={"confidence": 0.2})
    assert ConfidenceFloor().apply(unsure).severity is Severity.SEV4


def test_a_storm_names_the_most_upstream_service_as_suspect(load_alert):
    alerts = [load_alert(name) for name in STORM_FIXTURES]
    suspect, _ = StormGrouper().group(alerts)
    assert suspect.service == "news-scraper"


def test_a_storm_carries_the_remaining_alerts_as_symptoms(load_alert):
    alerts = [load_alert(name) for name in STORM_FIXTURES]
    _, symptoms = StormGrouper().group(alerts)
    assert len(symptoms) == 2


def test_an_empty_storm_is_rejected():
    with pytest.raises(ValueError):
        StormGrouper().group([])
