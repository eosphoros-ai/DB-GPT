from typing import Dict

from dbgpt.component import SystemApp
from dbgpt.util.tracer import Span, SpanStorage, SpanType, Tracer

# Mock implementations


class MockSpanStorage(SpanStorage):
    def __init__(self):
        self.spans = []

    def append_span(self, span: Span):
        self.spans.append(span)


class MockTracer(Tracer):
    def __init__(self, system_app: SystemApp | None = None):
        super().__init__(system_app)
        self.current_span = None
        self.storage = MockSpanStorage()

    def append_span(self, span: Span):
        self.storage.append_span(span)

    def start_span(
        self, operation_name: str, parent_span_id: str = None, metadata: Dict = None
    ) -> Span:
        trace_id = (
            self._new_uuid() if parent_span_id is None else parent_span_id.split(":")[0]
        )
        span_id = f"{trace_id}:{self._new_uuid()}"
        span = Span(
            trace_id, span_id, SpanType.BASE, parent_span_id, operation_name, metadata
        )
        self.current_span = span
        return span

    def end_span(self, span: Span):
        span.end()
        self.append_span(span)

    def get_current_span(self) -> Span:
        return self.current_span

    def _get_current_storage(self) -> SpanStorage:
        return self.storage


# Tests


def test_span_creation():
    span = Span(
        "trace_id",
        "span_id",
        SpanType.BASE,
        "parent_span_id",
        "operation",
        {"key": "value"},
    )
    assert span.trace_id == "trace_id"
    assert span.span_id == "span_id"
    assert span.parent_span_id == "parent_span_id"
    assert span.operation_name == "operation"
    assert span.metadata == {"key": "value"}


def test_span_end():
    span = Span("trace_id", "span_id")
    assert span.end_time is None
    span.end()
    assert span.end_time is not None


def test_mock_tracer_start_span():
    tracer = MockTracer()
    span = tracer.start_span("operation")
    assert span.operation_name == "operation"
    assert tracer.get_current_span() == span


def test_mock_tracer_end_span():
    tracer = MockTracer()
    span = tracer.start_span("operation")
    tracer.end_span(span)
    assert span in tracer._get_current_storage().spans


def test_mock_tracer_append_span():
    tracer = MockTracer()
    span = Span("trace_id", "span_id")
    tracer.append_span(span)
    assert span in tracer._get_current_storage().spans


def test_parent_child_span_relation():
    tracer = MockTracer()

    # Start a parent span
    parent_span = tracer.start_span("parent_operation")

    # Start a child span with parent span's ID
    child_span = tracer.start_span(
        "child_operation", parent_span_id=parent_span.span_id
    )

    # Assert the relationships
    assert child_span.parent_span_id == parent_span.span_id
    assert (
        child_span.trace_id == parent_span.trace_id
    )  # Assuming children share the same trace ID

    # End spans
    tracer.end_span(child_span)
    tracer.end_span(parent_span)

    # Assert they are in the storage
    assert child_span in tracer._get_current_storage().spans
    assert parent_span in tracer._get_current_storage().spans


# This test checks if unique UUIDs are being generated.
# Note: This is a simple test and doesn't guarantee uniqueness for large numbers of
# UUIDs.


def test_new_uuid_unique():
    tracer = MockTracer()
    uuid_set = {tracer._new_uuid() for _ in range(1000)}
    assert len(uuid_set) == 1000
