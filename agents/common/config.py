"""Shared config for the agent fleet.

Single source of truth for the model ID and GCP coordinates, so a change lands
in one place instead of four agent files.
"""

import os

from dotenv import load_dotenv

load_dotenv()


def _required(key: str) -> str:
    value = os.environ.get(key, "")
    if not value:
        raise RuntimeError(f"{key} is not set — copy .env.example to .env and fill it in")
    return value


PROJECT_ID = _required("PROJECT_ID")
REGION = os.environ.get("REGION", "us-central1")
MODEL_ID = _required("VERTEX_MODEL_ID")

TOPIC_INCIDENTS = os.environ.get("TOPIC_INCIDENTS", "incidents")
TOPIC_APPROVALS = os.environ.get("TOPIC_APPROVALS", "approvals")

SIGNATURES_COLLECTION = os.environ.get("FIRESTORE_COLLECTION_SIGNATURES", "incident-signatures")
MODEL_ARMOR_TEMPLATE_ID = os.environ.get("MODEL_ARMOR_TEMPLATE_ID", "")
