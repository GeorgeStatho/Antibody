"""Acknowledgement semantics.

These decide whether a bad alert disappears quietly or storms the fleet forever,
which is not something a unit run makes obvious. Hence a test per outcome.
"""

import base64
import json

import pytest
from fastapi.testclient import TestClient

from agents.common.errors import IncidentAlreadyHandled
from agents.common.serve import ACKNOWLEDGED, RETRY_REQUESTED, RetryPolicy, create_app

from conftest import FIXTURE_DIR, ORDINARY_ALERT

AGENT_NAME = "triage"


class ServiceUnavailable(Exception):
    code = 503


class ProgrammingMistake(Exception):
    """Nothing classified this one."""


class StubService:
    """Stands in for TriageService and can be told how to fail."""

    def __init__(self, error=None):
        self._error = error
        self.handled = []

    async def handle(self, alert):
        if self._error:
            raise self._error
        self.handled.append(alert)
        return _verdict_for(alert)


def _verdict_for(alert):
    from agents.common.schemas import Action, Severity, TriageVerdict

    return TriageVerdict(
        incident_id=alert.incident_id,
        received_at="2026-08-26T00:00:00Z",
        severity=Severity.SEV2,
        confidence=0.9,
        page_human=True,
        action=Action.INVESTIGATE,
        suspect_service=alert.service,
        symptom_fingerprint="b652bf2462ccf09c",
        fingerprint_inputs={},
        rationale="Stubbed.",
    )


@pytest.fixture
def push_body():
    return json.loads((FIXTURE_DIR / ORDINARY_ALERT).read_text())


@pytest.fixture
def build_client():
    def build(service=None):
        return TestClient(create_app(service or StubService(), AGENT_NAME))

    return build


def encode(payload: dict) -> dict:
    data = base64.b64encode(json.dumps(payload).encode()).decode()
    return {"message": {"data": data, "messageId": "m1"}}


def test_a_handled_alert_is_acknowledged(build_client, push_body):
    assert build_client().post("/", json=push_body).status_code == ACKNOWLEDGED


def test_a_handled_alert_reaches_the_service(build_client, push_body):
    service = StubService()
    build_client(service).post("/", json=push_body)
    assert len(service.handled) == 1


def test_an_unparseable_alert_is_acknowledged(build_client):
    """Acknowledged so a parse bug never becomes an endless redelivery."""
    response = build_client().post("/", json={"message": {"data": "!!!", "messageId": "m"}})
    assert response.status_code == ACKNOWLEDGED


def test_an_alert_without_an_incident_id_is_acknowledged(build_client):
    response = build_client().post("/", json=encode({"incident": {"state": "open"}}))
    assert response.status_code == ACKNOWLEDGED


def test_an_unparseable_alert_never_reaches_the_service(build_client):
    service = StubService()
    build_client(service).post("/", json={"message": {}})
    assert service.handled == []


def test_a_duplicate_delivery_is_acknowledged(build_client, push_body):
    service = StubService(error=IncidentAlreadyHandled("0.abc123"))
    assert build_client(service).post("/", json=push_body).status_code == ACKNOWLEDGED


def test_a_transient_failure_requests_redelivery(build_client, push_body):
    service = StubService(error=ServiceUnavailable())
    assert build_client(service).post("/", json=push_body).status_code == RETRY_REQUESTED


def test_an_unclassified_failure_requests_redelivery(build_client, push_body):
    """Better a redelivery capped by the dead-letter topic than a dropped incident."""
    service = StubService(error=ProgrammingMistake())
    assert build_client(service).post("/", json=push_body).status_code == RETRY_REQUESTED


def test_the_health_endpoint_reports_ok(build_client):
    assert build_client().get("/healthz").json()["status"] == "ok"


def test_the_health_endpoint_names_the_agent(build_client):
    assert build_client().get("/healthz").json()["agent"] == AGENT_NAME


def test_a_rate_limit_counts_as_transient():
    error = ServiceUnavailable()
    error.code = 429
    assert RetryPolicy().is_transient(error) is True


def test_a_duplicate_does_not_count_as_transient():
    assert RetryPolicy().is_transient(IncidentAlreadyHandled("x")) is False
