from __future__ import annotations

from typing import Dict, Callable, Optional, List
from dataclasses import dataclass
from abc import ABC, abstractmethod
from enum import Enum
import uuid
from datetime import datetime

from dbgpt.component import BaseComponent, SystemApp, ComponentType


class SpanType(str, Enum):
    BASE = "base"
    RUN = "run"
    CHAT = "chat"


class SpanTypeRunName(str, Enum):
    WEBSERVER = "Webserver"
    WORKER_MANAGER = "WorkerManager"
    MODEL_WORKER = "ModelWorker"
    EMBEDDING_MODEL = "EmbeddingModel"

    @staticmethod
    def values():
        return [item.value for item in SpanTypeRunName]


class Span:
    """Represents a unit of work that is being traced.
    This can be any operation like a function call or a database query.
    """

    def __init__(
        self,
        trace_id: str,
        span_id: str,
        span_type: SpanType = None,
        parent_span_id: str = None,
        operation_name: str = None,
        metadata: Dict = None,
        end_caller: Callable[[Span], None] = None,
    ):
        if not span_type:
            span_type = SpanType.BASE
        self.span_type = span_type
        # The unique identifier for the entire trace
        self.trace_id = trace_id
        # Unique identifier for this span within the trace
        self.span_id = span_id
        # Identifier of the parent span, if this is a child span
        self.parent_span_id = parent_span_id
        # Descriptive name for the operation being traced
        self.operation_name = operation_name
        # Timestamp when this span started
        self.start_time = datetime.now()
        # Timestamp when this span ended, initially None
        self.end_time = None
        # Additional metadata associated with the span
        self.metadata = metadata
        self._end_callers = []
        if end_caller:
            self._end_callers.append(end_caller)

    def end(self, **kwargs):
        """Mark the end of this span by recording the current time."""
        self.end_time = datetime.now()
        if "metadata" in kwargs:
            self.metadata = kwargs.get("metadata")
        for caller in self._end_callers:
            caller(self)

    def add_end_caller(self, end_caller: Callable[[Span], None]):
        if end_caller:
            self._end_callers.append(end_caller)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end()
        return False

    def to_dict(self) -> Dict:
        return {
            "span_type": self.span_type.value,
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "operation_name": self.operation_name,
            "start_time": None
            if not self.start_time
            else self.start_time.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
            "end_time": None
            if not self.end_time
            else self.end_time.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
            "metadata": self.metadata,
        }


class SpanStorageType(str, Enum):
    ON_CREATE = "on_create"
    ON_END = "on_end"
    ON_CREATE_END = "on_create_end"


class SpanStorage(BaseComponent, ABC):
    """Abstract base class for storing spans.

    This allows different storage mechanisms (e.g., in-memory, database) to be implemented.
    """

    name = ComponentType.TRACER_SPAN_STORAGE.value

    def init_app(self, system_app: SystemApp):
        """Initialize the storage with the given application context."""
        pass

    @abstractmethod
    def append_span(self, span: Span):
        """Store the given span. This needs to be implemented by subclasses."""

    def append_span_batch(self, spans: List[Span]):
        """Store the span batch"""
        for span in spans:
            self.append_span(span)


class Tracer(BaseComponent, ABC):
    """Abstract base class for tracing operations.
    Provides the core logic for starting, ending, and retrieving spans.
    """

    name = ComponentType.TRACER.value

    def __init__(self, system_app: SystemApp | None = None):
        super().__init__(system_app)
        self.system_app = system_app  # Application context

    def init_app(self, system_app: SystemApp):
        """Initialize the tracer with the given application context."""
        self.system_app = system_app

    @abstractmethod
    def append_span(self, span: Span):
        """Append the given span to storage. This needs to be implemented by subclasses."""

    @abstractmethod
    def start_span(
        self,
        operation_name: str,
        parent_span_id: str = None,
        span_type: SpanType = None,
        metadata: Dict = None,
    ) -> Span:
        """Begin a new span for the given operation. If provided, the span will be
        a child of the span with the given parent_span_id.
        """

    @abstractmethod
    def end_span(self, span: Span, **kwargs):
        """
        End the given span.
        """

    @abstractmethod
    def get_current_span(self) -> Optional[Span]:
        """
        Retrieve the span that is currently being traced.
        """

    @abstractmethod
    def _get_current_storage(self) -> SpanStorage:
        """
        Get the storage mechanism currently in use for storing spans.
        This needs to be implemented by subclasses.
        """

    def _new_uuid(self) -> str:
        """
        Generate a new unique identifier.
        """
        return str(uuid.uuid4())


@dataclass
class TracerContext:
    span_id: Optional[str] = None
