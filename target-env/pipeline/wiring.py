"""Where configuration turns into collaborators.

Mirrors agents/common/wiring.py deliberately: the environment is read here and
nowhere below, so nothing deeper in the pipeline behaves differently depending on
who exported what.
"""

from __future__ import annotations

import os

from pipeline.messaging import MessagePublisher
from pipeline.telemetry import StructuredLogger

DEFAULT_DATABASE = "(default)"
DEFAULT_POSITIONS = "positions"


def project_id() -> str:
    return os.environ["PROJECT_ID"]


def build_logger(service_name: str) -> StructuredLogger:
    return StructuredLogger(service_name, project_id=os.environ.get("PROJECT_ID"))


def build_publisher(topic_variable: str) -> MessagePublisher:
    from google.cloud import pubsub_v1

    client = pubsub_v1.PublisherClient()
    return MessagePublisher(client, client.topic_path(project_id(), os.environ[topic_variable]))


def build_positions_collection():
    from google.cloud import firestore

    client = firestore.Client(
        project=project_id(),
        database=os.environ.get("FIRESTORE_DATABASE", DEFAULT_DATABASE),
    )
    return client.collection(
        os.environ.get("FIRESTORE_COLLECTION_POSITIONS", DEFAULT_POSITIONS)
    )
