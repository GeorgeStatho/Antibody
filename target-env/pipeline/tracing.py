"""W3C trace context, carried across the Pub/Sub hops.

Propagated from the start rather than retrofitted: adding it later is a change that
touches all three services at once, and the fleet's observability claim depends on
one trace spanning scraper, classifier and executor.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass

TRACEPARENT = "traceparent"
VERSION = "00"
SAMPLED = "01"

TRACE_ID_BYTES = 16
SPAN_ID_BYTES = 8


@dataclass(frozen=True)
class TraceContext:
    """One traceparent header, and the pieces Cloud Logging wants from it."""

    trace_id: str
    span_id: str

    @classmethod
    def new(cls) -> TraceContext:
        return cls(
            trace_id=secrets.token_hex(TRACE_ID_BYTES),
            span_id=secrets.token_hex(SPAN_ID_BYTES),
        )

    @classmethod
    def from_header(cls, header: str | None) -> TraceContext:
        """Continues an existing trace, or starts one when the header is unusable."""
        parts = (header or "").split("-")
        if len(parts) < 4 or len(parts[1]) != TRACE_ID_BYTES * 2:
            return cls.new()
        return cls(trace_id=parts[1], span_id=secrets.token_hex(SPAN_ID_BYTES))

    @classmethod
    def from_attributes(cls, attributes: dict | None) -> TraceContext:
        return cls.from_header((attributes or {}).get(TRACEPARENT))

    def as_header(self) -> str:
        return f"{VERSION}-{self.trace_id}-{self.span_id}-{SAMPLED}"

    def as_attributes(self) -> dict:
        return {TRACEPARENT: self.as_header()}

    def as_log_field(self, project_id: str | None) -> str | None:
        """The resource name Cloud Logging correlates traces on.

        The project is passed in rather than read from the environment. A value
        object that reaches for os.environ behaves differently depending on who
        happens to have exported what, which is neither repeatable nor testable.
        """
        return f"projects/{project_id}/traces/{self.trace_id}" if project_id else None
