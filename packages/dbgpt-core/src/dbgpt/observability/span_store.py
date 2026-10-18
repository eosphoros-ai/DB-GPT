"""Isolated SQLite store for observability spans.

This is the default backend's persistence layer. It is deliberately **separate
from the DB-GPT main metadata DB**: it uses its own declarative base and its own
SQLite file (default ``logs/observability.db``), so high-volume telemetry never
bloats the operational database. Both :class:`SqliteSpanStorage` (write side)
and :class:`DefaultObservabilityProvider` (read side) share this store.
"""

import json
import logging
import os
import threading
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import Session, declarative_base, sessionmaker

logger = logging.getLogger(__name__)

# Isolated declarative base — NOT the global ``Model`` base used by the main DB,
# so ``create_all`` here only ever creates ``observability_span``.
ObservabilityBase = declarative_base()

DEFAULT_SQLITE_PATH = "logs/observability.db"
ENV_SQLITE_PATH = "DBGPT_OBSERVABILITY_SQLITE_PATH"


class ObservabilitySpanEntity(ObservabilityBase):  # type: ignore[misc,valid-type]
    """A single persisted span row."""

    __tablename__ = "observability_span"

    id = Column(Integer, primary_key=True, autoincrement=True)
    trace_id = Column(String(64), index=True, nullable=False)
    span_id = Column(String(128), index=True, nullable=False, unique=True)
    parent_span_id = Column(String(128), index=True, nullable=True)
    span_type = Column(String(32), nullable=True)
    operation_name = Column(String(256), index=True, nullable=True)
    agent_name = Column(String(255), index=True, nullable=True)
    model_name = Column(String(128), nullable=True)
    tool_name = Column(String(255), nullable=True)
    conversation_id = Column(String(128), index=True, nullable=True)
    session_id = Column(String(255), nullable=True)
    start_time = Column(DateTime, index=True, nullable=True)
    end_time = Column(DateTime, nullable=True)
    duration_ms = Column(Integer, nullable=True, index=True)
    status = Column(String(16), index=True, nullable=True)
    prompt_tokens = Column(Integer, nullable=True)
    completion_tokens = Column(Integer, nullable=True)
    total_tokens = Column(Integer, nullable=True)
    # Prompt-cache split (DeepSeek usage.prompt_cache_hit_tokens /
    # prompt_cache_miss_tokens; Anthropic cache_read_input_tokens etc.). Nullable
    # so providers without caching just leave them NULL.
    cache_hit_tokens = Column(Integer, nullable=True)
    cache_miss_tokens = Column(Integer, nullable=True)
    cost = Column(Float, nullable=True)
    metadata_json = Column(Text, nullable=True)
    error_json = Column(Text, nullable=True)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "span_type": self.span_type,
            "operation_name": self.operation_name,
            "agent_name": self.agent_name,
            "model_name": self.model_name,
            "tool_name": self.tool_name,
            "conversation_id": self.conversation_id,
            "session_id": self.session_id,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_ms": self.duration_ms,
            "status": self.status,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "cache_hit_tokens": self.cache_hit_tokens,
            "cache_miss_tokens": self.cache_miss_tokens,
            "cost": self.cost,
            "metadata": json.loads(self.metadata_json) if self.metadata_json else None,  # type: ignore
            "error": json.loads(self.error_json) if self.error_json else None,  # type: ignore
        }


_engine_lock = threading.Lock()
_engines: Dict[str, Tuple[Any, sessionmaker]] = {}


def resolve_sqlite_path(sqlite_path: Optional[str] = None) -> str:
    if sqlite_path:
        return sqlite_path
    return os.getenv(ENV_SQLITE_PATH, DEFAULT_SQLITE_PATH)


def _ensure_new_columns(engine: Any) -> None:
    """Additively migrate columns that ``create_all`` won't add to existing DBs.

    Keeps old ``observability.db`` files compatible when new columns are added to
    :class:`ObservabilitySpanEntity` (e.g. the cache-token split). Failure is
    non-fatal — worst case the column stays NULL on old files.
    """
    from sqlalchemy import inspect, text

    new_columns = {
        "cache_hit_tokens": "INTEGER",
        "cache_miss_tokens": "INTEGER",
    }
    try:
        insp = inspect(engine)
        if ObservabilitySpanEntity.__tablename__ not in insp.get_table_names():
            return
        existing = {
            c["name"] for c in insp.get_columns(ObservabilitySpanEntity.__tablename__)
        }
        for name, col_type in new_columns.items():
            if name not in existing:
                with engine.begin() as conn:
                    conn.execute(
                        text(
                            f"ALTER TABLE {ObservabilitySpanEntity.__tablename__} "
                            f"ADD COLUMN {name} {col_type}"
                        )
                    )
                logger.info(f"observability_span: added column {name}")
    except Exception as e:
        logger.warning(f"observability_span column migration skipped: {e}")


def get_observability_store(
    sqlite_path: Optional[str] = None,
) -> Tuple[Any, sessionmaker]:
    """Return ``(engine, session_factory)`` for the isolated observability SQLite file.

    Creates the file and the ``observability_span`` table on first use. Thread-safe
    singleton keyed by absolute path.
    """
    path = os.path.abspath(resolve_sqlite_path(sqlite_path))
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with _engine_lock:
        if path not in _engines:
            engine = create_engine(
                f"sqlite:///{path}",
                future=True,
                connect_args={"check_same_thread": False, "timeout": 30},
            )
            ObservabilityBase.metadata.create_all(engine, checkfirst=True)
            _ensure_new_columns(engine)
            factory = sessionmaker(bind=engine, expire_on_commit=False, class_=Session)
            _engines[path] = (engine, factory)
            logger.info(f"Observability sqlite store initialized at {path}")
        return _engines[path]


def now() -> datetime:
    return datetime.now()
