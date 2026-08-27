"""Cloud Run entry point for Triage.

The container runs `uvicorn agents.<FLEET_AGENT>.main:app`, so this module's only
job is to compose the service once at startup and hand it to the shared HTTP layer.
"""

from agents.common import config, serve, tracing
from agents.triage.factory import build_triage_service

AGENT_NAME = "triage"


def app_factory():
    """Built on demand, not at import. `uvicorn ... --factory` calls this.

    Importing the entry point must not require a project, a client, or a network,
    or the module cannot be read by a test and its composition stays invisible
    until it fails at startup.
    """
    tracing.configure_exporter(config.PROJECT_ID)
    return serve.create_app(build_triage_service(), AGENT_NAME)
