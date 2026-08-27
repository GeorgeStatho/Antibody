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

# Alert ingress: Cloud Monitoring notification channel publishes here, Triage subscribes.
TOPIC_INCIDENTS = os.environ.get("TOPIC_INCIDENTS", "incidents")
# Triage -> Diagnosis handoff. The registry calls this output `triage-verdict`.
TOPIC_VERDICTS = os.environ.get("TOPIC_VERDICTS", "triage-verdicts")
TOPIC_APPROVALS = os.environ.get("TOPIC_APPROVALS", "approvals")

# The Memory Bank. Written by Memory, read by Diagnosis. Never written by Triage.
SIGNATURES_COLLECTION = os.environ.get("FIRESTORE_COLLECTION_SIGNATURES", "incident-signatures")
# Triage's own ledger: one doc per incident_id, holding the idempotency claim and
# the MTTR t0 stamp. Distinct from the Memory Bank on purpose.
VERDICTS_COLLECTION = os.environ.get("FIRESTORE_COLLECTION_VERDICTS", "triage-verdicts")
MODEL_ARMOR_TEMPLATE_ID = os.environ.get("MODEL_ARMOR_TEMPLATE_ID", "")

# DEV ONLY. With no Model Armor template configured, Triage refuses to put untrusted
# alert text in front of a model and classifies from trusted metrics alone — which
# means the LLM path cannot be exercised at all until the template exists. Setting
# this to true re-enables prompting on unscanned text for local development. It logs
# a warning on every use and the emitted verdict still reports armor.scanned=False,
# so a run made under it can never be mistaken for a guarded one. Never set it on
# a deployed service.
ALLOW_UNSCANNED_PROMPT = os.environ.get("ALLOW_UNSCANNED_PROMPT", "").strip().lower() in (
    "1", "true", "yes",
)
