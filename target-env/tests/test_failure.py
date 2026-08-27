"""The injectable failure mode, which is what the whole demo turns on."""

from pipeline.failure import (
    FailsAtRate,
    NeverFails,
    read_failure_rate,
    select_failure_policy,
)

ALWAYS = lambda: 0.0  # noqa: E731 - a stub source of chance, not logic
NEVER = lambda: 0.99  # noqa: E731


def test_an_unset_rate_is_healthy():
    assert isinstance(select_failure_policy({}), NeverFails)


def test_a_zero_rate_is_healthy():
    assert isinstance(select_failure_policy({"FAILURE_RATE": "0"}), NeverFails)


def test_a_positive_rate_injects_failure():
    assert isinstance(select_failure_policy({"FAILURE_RATE": "0.35"}), FailsAtRate)


def test_an_unparseable_rate_is_healthy():
    """Fail toward serving, never toward silently breaking production."""
    assert isinstance(select_failure_policy({"FAILURE_RATE": "nonsense"}), NeverFails)


def test_an_unparseable_rate_reads_as_zero():
    assert read_failure_rate({"FAILURE_RATE": "nonsense"}) == 0.0


def test_a_healthy_policy_never_fails():
    assert NeverFails().should_fail() is False


def test_a_draw_under_the_rate_fails():
    assert FailsAtRate(0.35, chance=ALWAYS).should_fail() is True


def test_a_draw_over_the_rate_succeeds():
    assert FailsAtRate(0.35, chance=NEVER).should_fail() is False
