"""Composition root for Triage.

The one place that reads configuration and builds the object graph. Everything it
constructs receives its collaborators here, which is what lets the rest of the
package be exercised against stubs.
"""

from __future__ import annotations

from agents.common import config
from agents.common.armor import TextScanner
from agents.common.fingerprint import SymptomFingerprinter
from agents.common.wiring import build_scanner
from agents.triage.agent import build_triage_agent
from agents.triage.classifier import (
    ModelClassifier,
    PromptDespiteMissingScan,
    UnscannedTextPolicy,
    WithholdFromModel,
)
from agents.triage.ledger import IncidentLedger
from agents.triage.publisher import VerdictPublisher
from agents.triage.rules import RuleBook
from agents.triage.service import TriageService

APP_NAME = "antibody-triage"


def build_triage_service() -> TriageService:
    scanner = build_scanner()
    return TriageService(
        fingerprinter=SymptomFingerprinter(),
        rule_book=RuleBook(),
        scanner=scanner,
        classifier=build_classifier(scanner),
        unscanned_policy=select_unscanned_policy(),
        ledger=build_ledger(),
        publisher=build_publisher(),
    )


def build_classifier(scanner: TextScanner) -> ModelClassifier:
    return ModelClassifier(runner_factory=lambda: build_runner(scanner))


def build_runner(scanner: TextScanner):
    from google.adk.runners import InMemoryRunner

    return InMemoryRunner(
        agent=build_triage_agent(config.MODEL_ID, scanner), app_name=APP_NAME
    )


def select_unscanned_policy() -> UnscannedTextPolicy:
    """Chosen once, from configuration, rather than tested for on every alert."""
    if config.ALLOW_UNSCANNED_PROMPT:
        return PromptDespiteMissingScan()
    return WithholdFromModel()


def build_ledger() -> IncidentLedger:
    from google.cloud import firestore

    client = firestore.Client(
        project=config.PROJECT_ID, database=config.FIRESTORE_DATABASE
    )
    return IncidentLedger(client.collection(config.VERDICTS_COLLECTION))


def build_publisher() -> VerdictPublisher:
    from google.cloud import pubsub_v1

    client = pubsub_v1.PublisherClient()
    return VerdictPublisher(
        client, client.topic_path(config.PROJECT_ID, config.TOPIC_VERDICTS)
    )
