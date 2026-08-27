"""The log schema is a contract the fleet reads. These pin its shape."""

import json

from pipeline.telemetry import TRACE_FIELD, StructuredLogger
from pipeline.tracing import TraceContext


def test_a_line_is_valid_json(logger, log_stream):
    logger.info("article_published")
    assert json.loads(log_stream.getvalue())


def test_the_severity_is_top_level(logger, logged):
    """Cloud Logging promotes severity only when it is at the top level."""
    logger.info("article_published")
    assert logged()[0]["severity"] == "INFO"


def test_a_failure_logs_at_error(logger, logged):
    logger.error("classify_failed", error_class="injected_failure")
    assert logged()[0]["severity"] == "ERROR"


def test_the_service_field_is_stable(logger, logged):
    logger.info("article_published")
    assert logged()[0]["service"] == "llm-classifier"


def test_the_event_field_is_present(logger, logged):
    logger.info("article_published")
    assert logged()[0]["event"] == "article_published"


def test_a_failure_names_its_error_class(logger, logged):
    """The metric counts on this, and the fingerprint distinguishes failures by it."""
    logger.error("classify_failed", error_class="injected_failure")
    assert logged()[0]["error_class"] == "injected_failure"


def test_extra_fields_are_carried_through(logger, logged):
    logger.info("article_published", article_id="a1")
    assert logged()[0]["article_id"] == "a1"


def test_a_traced_line_carries_the_traceparent(logger, logged):
    trace = TraceContext.new()
    logger.info("article_published", trace=trace)
    assert logged()[0]["traceparent"] == trace.as_header()


def test_a_traced_line_carries_the_cloud_logging_trace_field(logger, logged):
    trace = TraceContext.new()
    logger.info("article_published", trace=trace)
    assert logged()[0][TRACE_FIELD] == f"projects/test-project/traces/{trace.trace_id}"


def test_an_untraced_line_omits_the_traceparent(logger, logged):
    logger.info("article_published")
    assert "traceparent" not in logged()[0]


def test_the_observed_rate_is_never_logged(logger, logged):
    """The rate is the metric's job. Near the fingerprint it would break stability."""
    logger.error("classify_failed", error_class="injected_failure")
    assert "error_rate" not in logged()[0]


def test_a_line_without_a_project_omits_the_trace_resource(log_stream, logged):
    StructuredLogger("news-scraper", log_stream).info("x", trace=TraceContext.new())
    assert TRACE_FIELD not in logged()[0]
