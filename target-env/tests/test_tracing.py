"""One trace must span scraper, classifier and executor."""

from pipeline.tracing import TRACEPARENT, TraceContext


def test_a_new_context_has_a_trace_id():
    assert len(TraceContext.new().trace_id) == 32


def test_a_new_context_has_a_span_id():
    assert len(TraceContext.new().span_id) == 16


def test_two_contexts_differ():
    assert TraceContext.new().trace_id != TraceContext.new().trace_id


def test_a_hop_keeps_the_trace_id():
    """This is the property that makes one trace span all three services."""
    original = TraceContext.new()
    assert TraceContext.from_header(original.as_header()).trace_id == original.trace_id


def test_a_hop_mints_a_new_span_id():
    original = TraceContext.new()
    assert TraceContext.from_header(original.as_header()).span_id != original.span_id


def test_a_missing_header_starts_a_trace():
    assert len(TraceContext.from_header(None).trace_id) == 32


def test_a_malformed_header_starts_a_trace():
    assert len(TraceContext.from_header("garbage").trace_id) == 32


def test_attributes_round_trip():
    original = TraceContext.new()
    assert TraceContext.from_attributes(original.as_attributes()).trace_id == original.trace_id


def test_the_attribute_key_is_the_w3c_name():
    assert TRACEPARENT in TraceContext.new().as_attributes()
