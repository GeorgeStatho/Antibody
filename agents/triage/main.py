"""Cloud Run entry point for Triage.

The container runs `uvicorn agents.<FLEET_AGENT>.main:app`, so this module's only
job is to compose the service once at startup and hand it to the shared HTTP layer.
"""

from agents.common import config, serve, tracing
from agents.triage.factory import build_triage_service

AGENT_NAME = "triage"

tracing.configure_exporter(config.PROJECT_ID)

app = serve.create_app(build_triage_service(), AGENT_NAME)
