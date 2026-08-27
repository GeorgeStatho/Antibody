"""Fixtures for the target environment.

Nothing here touches GCP. Every collaborator that would is injected.
"""

import base64
import io
import json

import pytest

from pipeline.telemetry import StructuredLogger
from pipeline.tracing import TraceContext

PROJECT = "test-project"


class RecordingPublisher:
    """Stands in for MessagePublisher and remembers what was published."""

    def __init__(self):
        self.published = []

    def publish(self, payload, trace):
        self.published.append((payload, trace))
        return "message-id"


class RecordingCollection:
    """Stands in for a Firestore collection."""

    def __init__(self):
        self.documents = {}

    def document(self, document_id):
        return _RecordingDocument(self.documents, document_id)


class _RecordingDocument:
    def __init__(self, store, document_id):
        self._store = store
        self._document_id = document_id

    def set(self, fields):
        self._store[self._document_id] = fields


@pytest.fixture
def log_stream():
    return io.StringIO()


@pytest.fixture
def logger(log_stream):
    return StructuredLogger("llm-classifier", log_stream, project_id=PROJECT)


@pytest.fixture
def logged(log_stream):
    def read():
        lines = [line for line in log_stream.getvalue().splitlines() if line.strip()]
        return [json.loads(line) for line in lines]

    return read


@pytest.fixture
def publisher():
    return RecordingPublisher()


@pytest.fixture
def collection():
    return RecordingCollection()


@pytest.fixture
def push_message():
    def build(payload, message_id="m1", trace=None):
        context = trace or TraceContext.new()
        return {
            "message": {
                "data": base64.b64encode(json.dumps(payload).encode()).decode(),
                "messageId": message_id,
                "attributes": context.as_attributes(),
            }
        }

    return build
