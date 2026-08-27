"""Reasoning-chain spans, exported to Cloud Trace.

Instrumentation is added at the boundaries the platform plane promises to show:
alert parse, guardrail scan, model call, publish. Retrofitting spans across four
agents later is strictly worse than opening them the first time.

Configuring the exporter is a startup concern and lives in configure_exporter,
which is safe to call when no exporter is available: the spans still open and the
code paths behave identically, they simply go nowhere.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager

from opentelemetry import trace

logger = logging.getLogger(__name__)

INCIDENT_ID = "antibody.incident_id"
SYMPTOM_FINGERPRINT = "antibody.symptom_fingerprint"
SEVERITY = "antibody.severity"
SERVICE = "antibody.suspect_service"

_tracer = trace.get_tracer("antibody")


def configure_exporter(project_id: str) -> None:
    """Sends spans to Cloud Trace. Never fatal: telemetry must not stop triage."""
    try:
        from opentelemetry.exporter.cloud_trace import CloudTraceSpanExporter
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        provider = TracerProvider()
        provider.add_span_processor(BatchSpanProcessor(CloudTraceSpanExporter(project_id)))
        trace.set_tracer_provider(provider)
    except Exception:  # noqa: BLE001
        logger.exception("Cloud Trace exporter unavailable; spans will not be exported")


@contextmanager
def span(name: str, **attributes):
    with _tracer.start_as_current_span(name) as current:
        for key, value in attributes.items():
            if value is not None:
                current.set_attribute(key, value)
        yield current
