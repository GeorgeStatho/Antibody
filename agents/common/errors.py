"""Failures the ingest layer has to tell apart.

They live together, and outside any one agent's package, because the HTTP layer
that acts on them is shared by the whole fleet and must not depend on a particular
agent to name them.
"""


class MalformedAlert(ValueError):
    """Permanently unparseable. The caller acknowledges rather than retrying."""


class IncidentAlreadyHandled(Exception):
    """A verdict for this incident exists. The caller acknowledges and stops."""
