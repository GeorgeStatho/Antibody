"""Shared fixtures. Every test builds its collaborators explicitly."""

import json
import pathlib

import pytest

from agents.common.alert import AlertParser
from agents.common.fingerprint import SymptomFingerprinter

FIXTURE_DIR = pathlib.Path(__file__).resolve().parents[1] / "infra" / "fixtures"

ORDINARY_ALERT = "alert-open.json"
RESOLVED_ALERT = "alert-closed.json"
FLAPPING_ALERT = "alert-flap.json"
WRITE_PATH_ALERT = "alert-sev1-executor.json"
POISONED_ALERT = "alert-poisoned.json"


@pytest.fixture
def golden_classifier_fingerprint():
    """Pins the classifier failure's key across the whole suite."""
    return "b652bf2462ccf09c"


@pytest.fixture
def parser():
    return AlertParser()


@pytest.fixture
def fingerprinter():
    return SymptomFingerprinter()


@pytest.fixture
def load_alert(parser):
    def load(name):
        return parser.parse(json.loads((FIXTURE_DIR / name).read_text()))

    return load


@pytest.fixture
def read_fixture():
    def read(name):
        return json.loads((FIXTURE_DIR / name).read_text())

    return read
