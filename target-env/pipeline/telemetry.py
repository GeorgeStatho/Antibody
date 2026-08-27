"""Structured logs, which are the contract the whole fleet reads.

Three separate things key on the fields emitted here:

  - the log-based metric the alert policy fires on,
  - Triage's symptom fingerprint, which hashes the metric's name,
  - the injection demo, which needs an attacker-reachable log body to reach the
    alert notification.

WARNING. `event` and `error_class` values are part of that contract. Changing one
changes which log lines the metric counts, and therefore which incidents the Memory
Bank can match. The observed error RATE is deliberately absent: the rate is the
metric's job, and putting it near the fingerprint's inputs would break stability
across occurrences.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass

from pipeline.tracing import TraceContext

INFO = "INFO"
ERROR = "ERROR"

TRACE_FIELD = "logging.googleapis.com/trace"


@dataclass(frozen=True)
class LogRecord:
    """One line, already shaped the way Cloud Logging promotes it."""

    severity: str
    service: str
    event: str
    fields: dict

    def as_json(self) -> str:
        return json.dumps({"severity": self.severity, "service": self.service,
                           "event": self.event, **self.fields})


class StructuredLogger:
    """Writes one JSON object per line. The stream is injected so tests can read it."""

    def __init__(self, service: str, stream=None, project_id: str | None = None) -> None:
        self._service = service
        self._stream = stream or sys.stdout
        self._project_id = project_id

    def info(self, event: str, trace: TraceContext | None = None, **fields) -> None:
        self._write(LogRecord(INFO, self._service, event, self._decorate(trace, fields)))

    def error(self, event: str, error_class: str, trace: TraceContext | None = None,
              **fields) -> None:
        decorated = self._decorate(trace, {"error_class": error_class, **fields})
        self._write(LogRecord(ERROR, self._service, event, decorated))

    def _decorate(self, trace: TraceContext | None, fields: dict) -> dict:
        if trace is None:
            return fields
        resource = trace.as_log_field(self._project_id)
        traced = {**fields, "traceparent": trace.as_header()}
        return {**traced, TRACE_FIELD: resource} if resource else traced

    def _write(self, record: LogRecord) -> None:
        print(record.as_json(), file=self._stream, flush=True)
