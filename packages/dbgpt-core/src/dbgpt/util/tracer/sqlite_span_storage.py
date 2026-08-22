"""``SpanStorage`` that persists spans to the isolated observability SQLite file.

Selected via the existing ``tracer_storage_cls`` dotted-path config (instantiated
with no args, like ``OpenTelemetrySpanStorage``), so it slots into the existing
``SpanStorageContainer`` fan-out alongside ``FileSpanStorage``. It writes to
``logs/observability.db`` (override via ``DBGPT_OBSERVABILITY_SQLITE_PATH``) and
**never touches the main metadata DB**.

A span is delivered twice (``SpanStorageType.ON_CREATE_END``): once on create
(no ``end_time``) and once on end (with ``end_time`` + enriched metadata). We
upsert by ``span_id`` so the end call updates the row with duration / cost /
tokens / status / final metadata.
"""

import json
import logging
from typing import Any, Dict, Optional

from dbgpt.observability.span_store import (
    ObservabilitySpanEntity,
    get_observability_store,
    resolve_sqlite_path,
)
from dbgpt.util.tracer.base import Span, SpanStorage

logger = logging.getLogger(__name__)


def _as_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    s = str(value)
    return s[:255] if len(s) > 255 else s


def _as_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _json_dumps(value: Any) -> Optional[str]:
    if value is None:
        return None
    try:
        return json.dumps(value, ensure_ascii=False, default=str)
    except Exception:
        return None


def _extract(meta: Dict[str, Any]) -> Dict[str, Any]:
    """Pull common fields out of span metadata into indexed columns."""
    conversation_id = (
        meta.get("conversation_id")
        or meta.get("conv_uid")
        or meta.get("conv_id")
        or meta.get("chat_session_id")
    )
    error = meta.get("error") or meta.get("exception")
    status = meta.get("status")
    if status is None and error is not None:
        status = "ERROR"
    usage = meta.get("usage") or {}
    # Prompt-cache split across providers:
    #   DeepSeek:   prompt_cache_hit_tokens / prompt_cache_miss_tokens
    #   Anthropic:  cache_read_input_tokens / cache_creation_input_tokens
    #   OpenAI:     cached_tokens (inside prompt_tokens_details)
    cache_hit = (
        meta.get("cache_hit_tokens")
        or usage.get("prompt_cache_hit_tokens")
        or usage.get("cache_read_input_tokens")
        or usage.get("cached_tokens")
    )
    cache_miss = (
        meta.get("cache_miss_tokens")
        or usage.get("prompt_cache_miss_tokens")
        or usage.get("cache_creation_input_tokens")
    )
    return dict(
        agent_name=_as_str(
            meta.get("agent_name") or meta.get("agent") or meta.get("sender")
        ),
        model_name=_as_str(meta.get("model_name") or meta.get("model")),
        tool_name=_as_str(
            meta.get("tool_name") or meta.get("resource") or meta.get("tool")
        ),
        conversation_id=_as_str(conversation_id),
        session_id=_as_str(meta.get("session_id")),
        status=_as_str(status),
        prompt_tokens=_as_int(meta.get("prompt_tokens") or usage.get("prompt_tokens")),
        completion_tokens=_as_int(
            meta.get("completion_tokens") or usage.get("completion_tokens")
        ),
        total_tokens=_as_int(meta.get("total_tokens") or usage.get("total_tokens")),
        cache_hit_tokens=_as_int(cache_hit),
        cache_miss_tokens=_as_int(cache_miss),
        cost=_as_float(meta.get("cost")),
        error_json=_json_dumps(error),
    )


class SqliteSpanStorage(SpanStorage):
    """Persist spans to an isolated observability SQLite file."""

    def __init__(self, sqlite_path: Optional[str] = None):
        super().__init__()
        self._sqlite_path = resolve_sqlite_path(sqlite_path)

    def append_span(self, span: Span):
        try:
            _, factory = get_observability_store(self._sqlite_path)
            with factory() as session:
                self._upsert(session, span)
                session.commit()
        except Exception as e:
            logger.warning(f"SqliteSpanStorage append_span failed: {e}")

    def append_span_batch(self, spans):
        try:
            _, factory = get_observability_store(self._sqlite_path)
            with factory() as session:
                for span in spans:
                    self._upsert(session, span)
                session.commit()
        except Exception as e:
            logger.warning(f"SqliteSpanStorage append_span_batch failed: {e}")

    def _upsert(self, session, span: Span):
        meta = span.metadata or {}
        duration_ms = None
        if span.start_time and span.end_time:
            duration_ms = int((span.end_time - span.start_time).total_seconds() * 1000)
        extra = _extract(meta)
        values = dict(
            trace_id=span.trace_id,
            span_id=span.span_id,
            parent_span_id=span.parent_span_id,
            span_type=span.span_type.value if span.span_type else None,
            operation_name=_as_str(span.operation_name),
            start_time=span.start_time,
            end_time=span.end_time,
            duration_ms=duration_ms,
            metadata_json=_json_dumps(meta),
            **extra,
        )
        existing = (
            session.query(ObservabilitySpanEntity)
            .filter(ObservabilitySpanEntity.span_id == span.span_id)
            .first()
        )
        if existing is not None:
            for key, value in values.items():
                setattr(existing, key, value)
        else:
            session.add(ObservabilitySpanEntity(**values))
