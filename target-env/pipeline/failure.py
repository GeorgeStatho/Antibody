"""The injectable failure mode.

The policy is chosen once from the environment, at startup, rather than tested for
on every request. Which policy is in force is therefore a property of the running
REVISION, which is what makes the rollback in the Response agent's remediation a
real operation rather than a gesture: the broken state is a revision, and rolling
back to the previous one genuinely restores service.
"""

from __future__ import annotations

import random
from typing import Protocol

FAILURE_RATE_VARIABLE = "FAILURE_RATE"
INJECTED_FAILURE = "injected_failure"

HEALTHY = 0.0


class InjectedFailure(RuntimeError):
    """Raised by the failure policy. Distinct from a genuine bug, on purpose."""


class FailurePolicy(Protocol):
    def should_fail(self) -> bool: ...


class NeverFails:
    """The healthy revision."""

    def should_fail(self) -> bool:
        return False


class FailsAtRate:
    """Fails a fraction of requests. The source of chance is injected for testability."""

    def __init__(self, rate: float, chance=random.random) -> None:
        self._rate = rate
        self._chance = chance

    def should_fail(self) -> bool:
        return self._chance() < self._rate


def read_failure_rate(environment) -> float:
    """A rate that cannot be parsed means healthy, never accidentally broken."""
    try:
        return float(environment.get(FAILURE_RATE_VARIABLE, HEALTHY))
    except (TypeError, ValueError):
        return HEALTHY


def select_failure_policy(environment) -> FailurePolicy:
    rate = read_failure_rate(environment)
    return FailsAtRate(rate) if rate > HEALTHY else NeverFails()
