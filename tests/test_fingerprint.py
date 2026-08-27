"""The Memory Bank's contract with the rest of the fleet.

If these fail the memory hit stops happening and the MTTR delta disappears with it.
"""

import pytest

from agents.common.fingerprint import DirectionReader, LabelNormaliser, SymptomFingerprinter
from agents.common.values import Direction, MetricReading

CLASSIFIER_METRIC = "logging.googleapis.com/user/classifier_errors"
CLASSIFIER_CONDITION = "error-rate-above-threshold"
SPIKING = MetricReading(observed=0.31, threshold=0.05)


@pytest.fixture
def classifier_symptom(fingerprinter):
    return fingerprinter.describe(
        "llm-classifier", CLASSIFIER_METRIC, CLASSIFIER_CONDITION, SPIKING
    )


def describe_with(fingerprinter, **overrides):
    fields = {
        "service": "llm-classifier",
        "metric": CLASSIFIER_METRIC,
        "condition": CLASSIFIER_CONDITION,
        "reading": SPIKING,
    }
    fields.update(overrides)
    return fingerprinter.describe(**fields)


def test_identical_inputs_produce_one_key(fingerprinter, classifier_symptom):
    first = fingerprinter.fingerprint(classifier_symptom)
    assert first == fingerprinter.fingerprint(classifier_symptom)


def test_a_louder_second_occurrence_keeps_the_same_key(fingerprinter, classifier_symptom):
    louder = describe_with(fingerprinter, reading=MetricReading(0.47, 0.05))
    assert fingerprinter.fingerprint(louder) == fingerprinter.fingerprint(classifier_symptom)


def test_retuning_a_threshold_keeps_the_same_key(fingerprinter):
    """The condition's display name carries the threshold. Retuning is not a new failure."""
    before = describe_with(fingerprinter, condition="error-rate-above-threshold 5%")
    after = describe_with(fingerprinter, condition="error-rate-above-threshold 10%")
    assert fingerprinter.fingerprint(after) == fingerprinter.fingerprint(before)


def test_a_generated_uuid_suffix_keeps_the_same_key(fingerprinter, classifier_symptom):
    suffixed = describe_with(
        fingerprinter,
        condition="error-rate-above-threshold 6c5f2d1a-1111-2222-3333-444455556666",
    )
    assert fingerprinter.fingerprint(suffixed) == fingerprinter.fingerprint(classifier_symptom)


def test_a_different_service_produces_a_different_key(fingerprinter, classifier_symptom):
    other = describe_with(fingerprinter, service="execution-layer")
    assert fingerprinter.fingerprint(other) != fingerprinter.fingerprint(classifier_symptom)


def test_a_different_metric_produces_a_different_key(fingerprinter, classifier_symptom):
    other = describe_with(fingerprinter, metric="run.googleapis.com/request_latencies")
    assert fingerprinter.fingerprint(other) != fingerprinter.fingerprint(classifier_symptom)


def test_a_drop_and_a_spike_are_different_failures(fingerprinter, classifier_symptom):
    """Folding them together would produce a wrong hit, which is worse than a miss."""
    dropping = describe_with(fingerprinter, reading=MetricReading(0.01, 0.05))
    assert fingerprinter.fingerprint(dropping) != fingerprinter.fingerprint(classifier_symptom)


def test_a_missing_service_becomes_unknown(fingerprinter):
    symptom = describe_with(fingerprinter, service=None)
    assert symptom.service == "unknown"


def test_a_missing_reading_leaves_the_direction_unknown(fingerprinter):
    symptom = describe_with(fingerprinter, condition="something odd", reading=MetricReading())
    assert symptom.direction is Direction.UNKNOWN


def test_the_key_is_sixteen_characters(fingerprinter, classifier_symptom):
    assert len(fingerprinter.fingerprint(classifier_symptom).value) == 16


def test_the_key_is_hexadecimal(fingerprinter, classifier_symptom):
    key = fingerprinter.fingerprint(classifier_symptom).value
    assert all(character in "0123456789abcdef" for character in key)


def test_the_classifier_key_is_pinned(
    fingerprinter, classifier_symptom, golden_classifier_fingerprint
):
    """Changing this invalidates every signature already in the Memory Bank.

    If that is deliberate, raise fingerprint.VERSION in the same commit rather than
    pasting the new value here.
    """
    assert fingerprinter.fingerprint(classifier_symptom).value == golden_classifier_fingerprint


def test_the_exporting_host_is_dropped_from_a_metric():
    assert LabelNormaliser().normalise_metric(CLASSIFIER_METRIC) == "user-classifier-errors"


def test_a_missing_metric_normalises_to_unknown():
    assert LabelNormaliser().normalise_metric(None) == "unknown"


def test_normalising_twice_changes_nothing():
    normaliser = LabelNormaliser()
    once = normaliser.normalise("Error Rate Above 5%")
    assert normaliser.normalise(once) == once


def test_an_absent_metric_reads_as_absent():
    assert DirectionReader().read(MetricReading(), "metric absent for 5m") is Direction.ABSENT


def test_a_floor_breach_reads_as_a_drop():
    assert DirectionReader().read(MetricReading(), "requests below floor") is Direction.DROP


def test_a_ceiling_breach_reads_as_a_spike():
    assert DirectionReader().read(MetricReading(), "errors above threshold") is Direction.SPIKE


def test_an_unreadable_condition_reads_as_unknown():
    assert DirectionReader().read(MetricReading(), "something odd") is Direction.UNKNOWN


def test_two_fingerprinters_agree(golden_classifier_fingerprint):
    """Triage, Memory and Diagnosis each build their own. They must not diverge."""
    symptom = SymptomFingerprinter().describe(
        "llm-classifier", CLASSIFIER_METRIC, CLASSIFIER_CONDITION, SPIKING
    )
    assert SymptomFingerprinter().fingerprint(symptom).value == golden_classifier_fingerprint
