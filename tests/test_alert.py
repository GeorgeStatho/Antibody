"""The ingest boundary.

Two properties are protected. Malformed input raises, so the caller acknowledges
and a parse bug never becomes an endless Pub/Sub redelivery. And the trust split
holds, since every downstream agent's safety assumption rests on it.
"""

import base64
import json

import pytest

from agents.common.alert import AlertParser, MalformedAlert
from agents.common.values import Direction

from conftest import ORDINARY_ALERT, POISONED_ALERT, RESOLVED_ALERT, WRITE_PATH_ALERT

INJECTION_MARKER = "NOTE TO AGENT"
EXFILTRATION_HOST = "evil.example"

MALFORMED_FIXTURES = [
    "malformed-no-message.json",
    "malformed-bad-base64.json",
    "malformed-no-incident-id.json",
]


def test_the_incident_id_is_read(load_alert):
    assert load_alert(ORDINARY_ALERT).incident_id == "0.abc123"


def test_the_service_is_read_from_the_resource_labels(load_alert):
    assert load_alert(ORDINARY_ALERT).service == "llm-classifier"


def test_the_observed_value_is_read(load_alert):
    assert load_alert(ORDINARY_ALERT).reading.observed == pytest.approx(0.31)


def test_the_threshold_is_read(load_alert):
    assert load_alert(ORDINARY_ALERT).reading.threshold == pytest.approx(0.05)


def test_the_metric_type_is_read(load_alert):
    expected = "logging.googleapis.com/user/classifier_errors"
    assert load_alert(ORDINARY_ALERT).metric_type == expected


def test_the_message_id_survives_the_envelope(load_alert):
    assert load_alert(ORDINARY_ALERT).message_id == "msg-0.abc123"


def test_an_epoch_start_becomes_a_timestamp(load_alert):
    assert load_alert(ORDINARY_ALERT).started_at.endswith("Z")


def test_a_closed_incident_reads_as_resolved(load_alert):
    assert load_alert(RESOLVED_ALERT).is_resolved


def test_an_open_incident_does_not_read_as_resolved(load_alert):
    assert load_alert(ORDINARY_ALERT).is_resolved is False


def test_a_spiking_metric_reads_as_a_spike(load_alert):
    assert load_alert(ORDINARY_ALERT).reading.direction() is Direction.SPIKE


def test_the_summary_reaches_the_untrusted_region(load_alert):
    alert = load_alert(ORDINARY_ALERT)
    assert alert.summary.content in alert.untrusted_text().content


def test_the_incident_id_stays_out_of_the_untrusted_region(load_alert):
    alert = load_alert(ORDINARY_ALERT)
    assert alert.incident_id not in alert.untrusted_text().content


def test_an_injection_lands_in_the_untrusted_region(load_alert):
    """Exactly where the scanner looks for it."""
    assert INJECTION_MARKER in load_alert(POISONED_ALERT).untrusted_text().content


def test_an_injection_never_reaches_the_trusted_facts(load_alert):
    facts = load_alert(POISONED_ALERT).trusted_facts().as_json()
    assert INJECTION_MARKER not in facts


def test_an_exfiltration_host_never_reaches_the_trusted_facts(load_alert):
    facts = load_alert(POISONED_ALERT).trusted_facts().as_json()
    assert EXFILTRATION_HOST not in facts


def test_the_write_path_fixture_names_the_executor(load_alert):
    assert load_alert(WRITE_PATH_ALERT).service == "execution-layer"


@pytest.mark.parametrize("fixture_name", MALFORMED_FIXTURES)
def test_malformed_input_is_rejected(parser, read_fixture, fixture_name):
    with pytest.raises(MalformedAlert):
        parser.parse(read_fixture(fixture_name))


def test_a_payload_that_is_not_an_object_is_rejected(parser):
    encoded = base64.b64encode(json.dumps("just a string").encode()).decode()
    with pytest.raises(MalformedAlert):
        parser.parse({"message": {"data": encoded, "messageId": "m"}})


def test_ingest_feeds_the_pinned_fingerprint(
    load_alert, fingerprinter, golden_classifier_fingerprint
):
    """The whole path from push body to Memory Bank key, in one assertion."""
    alert = load_alert(ORDINARY_ALERT)
    symptom = fingerprinter.describe(
        alert.service, alert.metric_type, alert.condition_name, alert.reading
    )
    assert fingerprinter.fingerprint(symptom).value == golden_classifier_fingerprint


def test_a_later_occurrence_matches_the_first(load_alert, fingerprinter):
    """The memory hit, simulated: same failure class, different incident."""
    first = load_alert(ORDINARY_ALERT)
    later = load_alert("alert-storm-classifier.json")
    keys = {
        fingerprinter.fingerprint(
            fingerprinter.describe(a.service, a.metric_type, a.condition_name, a.reading)
        )
        for a in (first, later)
    }
    assert len(keys) == 1
