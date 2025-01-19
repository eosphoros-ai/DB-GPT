from __future__ import annotations

import json
import secrets
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from dbgpt.component import BaseComponent, ComponentType, SystemApp

DBGPT_TRACER_SPAN_ID = "DB-GPT-Trace-Span-Id"

# Compatibility with OpenTelemetry API
_TRACE_ID_MAX_VALUE = 2**128 - 1
_SPAN_ID_MAX_VALUE = 2**64 - 1
INVALID_SPAN_ID = 0x0000000000000000
INVALID_TRACE_ID = 0x00000000000000000000000000000000


class SpanType(str, Enum):
    BASE = "base"
    RUN = "run"
    CHAT = "chat"
    AGENT = "agent"


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
        self.metadata = metadata or {}
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
            "start_time": (
                None
                if not self.start_time
                else self.start_time.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            ),
            "end_time": (
                None
                if not self.end_time
                else self.end_time.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            ),
            "metadata": _clean_for_json(self.metadata) if self.metadata else None,
        }

    def copy(self) -> Span:
        """Create a copy of this span."""
        metadata = self.metadata.copy() if self.metadata else None
        span = Span(
            self.trace_id,
            self.span_id,
            self.span_type,
            self.parent_span_id,
            self.operation_name,
            metadata=metadata,
        )
        span.start_time = self.start_time
        span.end_time = self.end_time
        return span


class SpanStorageType(str, Enum):
    ON_CREATE = "on_create"
    ON_END = "on_end"
    ON_CREATE_END = "on_create_end"


class SpanStorage(BaseComponent, ABC):
    """Abstract base class for storing spans.

    This allows different storage mechanisms (e.g., in-memory, database) to be
    implemented.
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
        """Append the given span to storage.

        This needs to be implemented by subclasses.
        """

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

    def _new_random_trace_id(self) -> str:
        """Create a new random trace ID."""

        return _new_random_trace_id()

    def _new_random_span_id(self) -> str:
        """Create a new random span ID."""

        return _new_random_span_id()


def _new_random_trace_id() -> str:
    """Create a new random trace ID."""
    # Generate a 128-bit hex string
    return secrets.token_hex(16)


def _is_valid_trace_id(trace_id: Union[str, int]) -> bool:
    if isinstance(trace_id, str):
        try:
            trace_id = int(trace_id, 16)
        except ValueError:
            return False
    return INVALID_TRACE_ID < int(trace_id) <= _TRACE_ID_MAX_VALUE


def _new_random_span_id() -> str:
    """Create a new random span ID."""

    # Generate a 64-bit hex string
    return secrets.token_hex(8)


def _is_valid_span_id(span_id: Union[str, int]) -> bool:
    if isinstance(span_id, str):
        try:
            span_id = int(span_id, 16)
        except ValueError:
            return False
    return INVALID_SPAN_ID < int(span_id) <= _SPAN_ID_MAX_VALUE


def _split_span_id(span_id: str) -> Tuple[int, int]:
    parent_span_id_parts = span_id.split(":")
    if len(parent_span_id_parts) != 2:
        return 0, 0
    trace_id, parent_span_id = parent_span_id_parts
    try:
        trace_id = int(trace_id, 16)
        span_id = int(parent_span_id, 16)
        return trace_id, span_id
    except ValueError:
        return 0, 0


@dataclass
class TracerContext:
    span_id: Optional[str] = None


def _clean_for_json(data: Optional[str, Any] = None):
    if data is None:
        return None
    if isinstance(data, dict):
        cleaned_dict = {}
        for key, value in data.items():
            # Try to clean the sub-items
            cleaned_value = _clean_for_json(value)
            if cleaned_value is not None:
                # Only add to the cleaned dict if it's not None
                try:
                    json.dumps({key: cleaned_value})
                    cleaned_dict[key] = cleaned_value
                except TypeError:
                    # Skip this key-value pair if it can't be serialized
                    pass
        return cleaned_dict
    elif isinstance(data, list):
        cleaned_list = []
        for item in data:
            cleaned_item = _clean_for_json(item)
            if cleaned_item is not None:
                try:
                    json.dumps(cleaned_item)
                    cleaned_list.append(cleaned_item)
                except TypeError:
                    pass
        return cleaned_list
    else:
        try:
            json.dumps(data)
            return data
        except TypeError:
            return None


def _parse_span_id(body: Any) -> Optional[str]:
    from starlette.requests import Request

    from dbgpt._private.pydantic import BaseModel, model_to_dict

    span_id: Optional[str] = None
    if isinstance(body, Request):
        span_id = body.headers.get(DBGPT_TRACER_SPAN_ID)
    elif isinstance(body, dict):
        span_id = body.get(DBGPT_TRACER_SPAN_ID) or body.get("span_id")
    elif isinstance(body, BaseModel):
        dict_body = model_to_dict(body)
        span_id = dict_body.get(DBGPT_TRACER_SPAN_ID) or dict_body.get("span_id")
    if not span_id:
        return None
    else:
        int_trace_id, int_span_id = _split_span_id(span_id)
        if not int_trace_id:
            return None
        if _is_valid_span_id(int_span_id) and _is_valid_trace_id(int_trace_id):
            return span_id
        else:
            return span_id
