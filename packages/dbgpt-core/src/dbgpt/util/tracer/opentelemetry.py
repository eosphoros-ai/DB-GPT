from typing import Dict, List, Optional

from .base import Span, SpanStorage, _split_span_id

try:
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import Span as OTSpan
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.trace import SpanContext, SpanKind
except ImportError:
    raise ImportError(
        "To use OpenTelemetrySpanStorage, you must install opentelemetry-api, "
        "opentelemetry-sdk and opentelemetry-exporter-otlp."
        "You can install it via `pip install opentelemetry-api opentelemetry-sdk "
        "opentelemetry-exporter-otlp`"
    )


class OpenTelemetrySpanStorage(SpanStorage):
    """OpenTelemetry span storage."""

    def __init__(
        self,
        service_name: str,
        otlp_endpoint: Optional[str] = None,
        otlp_insecure: Optional[bool] = None,
        otlp_timeout: Optional[int] = None,
    ):
        super().__init__()
        self.service_name = service_name

        resource = Resource(attributes={"service.name": service_name})
        self.tracer_provider = TracerProvider(resource=resource)
        self.tracer = self.tracer_provider.get_tracer(__name__)
        # Store the spans that have not ended
        self.spans: Dict[str, OTSpan] = {}
        otlp_exporter = OTLPSpanExporter(
            endpoint=otlp_endpoint,
            insecure=otlp_insecure,
            timeout=otlp_timeout,
        )
        span_processor = BatchSpanProcessor(otlp_exporter)
        self.tracer_provider.add_span_processor(span_processor)
        trace.set_tracer_provider(self.tracer_provider)

    def append_span(self, span: Span):
        span_id = span.span_id

        if span_id in self.spans:
            otel_span = self.spans.pop(span_id)
            # Update the end time and attributes of the span
            end_time = int(span.end_time.timestamp() * 1e9) if span.end_time else None
            if span.metadata:
                for key, value in span.metadata.items():
                    if isinstance(value, (bool, str, bytes, int, float)) or (
                        isinstance(value, list)
                        and all(
                            isinstance(i, (bool, str, bytes, int, float)) for i in value
                        )
                    ):
                        otel_span.set_attribute(key, value)
            if end_time:
                otel_span.end(end_time=end_time)
            else:
                otel_span.end()
        else:
            parent_context = self._create_parent_context(span)
            # Datetime -> int
            start_time = int(span.start_time.timestamp() * 1e9)

            otel_span = self.tracer.start_span(
                span.operation_name,
                context=parent_context,
                kind=SpanKind.INTERNAL,
                start_time=start_time,
            )

            otel_span.set_attribute("dbgpt_trace_id", span.trace_id)
            otel_span.set_attribute("dbgpt_span_id", span.span_id)

            if span.parent_span_id:
                otel_span.set_attribute("dbgpt_parent_span_id", span.parent_span_id)

            otel_span.set_attribute("span_type", span.span_type.value)
            if span.metadata:
                for key, value in span.metadata.items():
                    if isinstance(value, (bool, str, bytes, int, float)) or (
                        isinstance(value, list)
                        and all(
                            isinstance(i, (bool, str, bytes, int, float)) for i in value
                        )
                    ):
                        otel_span.set_attribute(key, value)

            if not span.end_time:
                self.spans[span_id] = otel_span

    def append_span_batch(self, spans: List[Span]):
        for span in spans:
            self.append_span(span)

    def _create_parent_context(self, span: Span):
        if not span.parent_span_id:
            return trace.set_span_in_context(trace.INVALID_SPAN)

        trace_id, parent_span_id = _split_span_id(span.parent_span_id)
        if not trace_id:
            return trace.set_span_in_context(trace.INVALID_SPAN)

        span_context = SpanContext(
            trace_id=trace_id,
            span_id=parent_span_id,
            is_remote=True,
            trace_flags=trace.TraceFlags(0x01),  # Default: SAMPLED
        )
        return trace.set_span_in_context(trace.NonRecordingSpan(span_context))

    def close(self):
        self.tracer_provider.shutdown()
