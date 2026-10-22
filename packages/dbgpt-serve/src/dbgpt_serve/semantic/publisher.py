"""Chunk rendering + publish pipeline (phase 2).

Publish flow (design doc §7.5): edit draft (structured DB only) -> human
confirm -> status=published, version+1 -> write the KB managed space
(delete old chunk by metadata.id -> insert -> embed). The vector store is a
**derived index**: chunk text is rendered from the authoritative rows here and
can always be rebuilt from them.

Phase 2 ships the sink protocol plus a :class:`LoggingSink`; the
:class:`ManagedSpaceSink` attempts to wire the existing rag storage and
degrades fail-soft (warning + in-memory) when the embedding/vector stack is
not available in the current process. Full vector wiring is exercised in
phase 3 when the retriever consumes the space.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Protocol

from dbgpt_serve.semantic.models import (
    SemEntryEntity,
    SemExampleEntity,
    SemMetricEntity,
    SemPublishLogDao,
    SemPublishLogEntity,
    load_json,
)

logger = logging.getLogger(__name__)


@dataclass
class RenderedChunk:
    """A chunk ready for the managed space (text + pointer metadata)."""

    chunk_id: str
    text: str
    metadata: Dict[str, Any] = field(default_factory=dict)


def render_column_chunk(
    ds_id: int, entry: SemEntryEntity, table_name: str, column_name: str
) -> RenderedChunk:
    synonyms = load_json(entry.synonyms) or []
    parts = [f"{table_name}.{column_name}"]
    if entry.entry_comment:
        parts.append(entry.entry_comment)
    if synonyms:
        parts.append("同义词: " + ",".join(synonyms))
    version = entry.publish_version or entry.version
    return RenderedChunk(
        chunk_id=f"col_{entry.id}",
        text="; ".join(parts),
        metadata={
            "id": f"col_{entry.id}",
            "type": "column",
            "target": f"{table_name}.{column_name}",
            "v": version,
            "ds": ds_id,
        },
    )


def render_table_chunk(
    ds_id: int, entry: SemEntryEntity, table_name: str
) -> RenderedChunk:
    synonyms = load_json(entry.synonyms) or []
    parts = [table_name]
    if entry.entry_comment:
        parts.append(entry.entry_comment)
    if synonyms:
        parts.append("同义词: " + ",".join(synonyms))
    version = entry.publish_version or entry.version
    return RenderedChunk(
        chunk_id=f"tbl_{entry.id}",
        text="; ".join(parts),
        metadata={
            "id": f"tbl_{entry.id}",
            "type": "table",
            "target": table_name,
            "v": version,
            "ds": ds_id,
        },
    )


def render_metric_chunk(ds_id: int, metric: SemMetricEntity) -> RenderedChunk:
    dims = load_json(metric.dimensions) or []
    parts = [f"{metric.metric_name}"]
    if metric.metric_comment:
        parts.append(metric.metric_comment)
    if metric.formula:
        parts.append(f"expression: {metric.formula}")
    if dims:
        parts.append("dimensions: " + ",".join(dims))
    version = metric.publish_version or metric.version
    return RenderedChunk(
        chunk_id=f"met_{metric.id}",
        text="; ".join(parts),
        metadata={
            "id": f"met_{metric.id}",
            "type": "metric",
            "target": metric.metric_name,
            "v": version,
            "ds": ds_id,
        },
    )


def render_example_chunk(ds_id: int, example: SemExampleEntity) -> RenderedChunk:
    version = example.publish_version or 1
    return RenderedChunk(
        chunk_id=f"ex_{example.id}",
        text=f"Q: {example.question} -> {example.sql_text}",
        metadata={
            "id": f"ex_{example.id}",
            "type": "example",
            "target": example.example_name or example.question,
            "v": version,
            "ds": ds_id,
            "src": example.source,
        },
    )


class ChunkSink(Protocol):
    """Where published chunks go (managed KB space in production)."""

    def delete(self, space_name: str, chunk_ids: List[str]) -> None: ...

    def insert(self, space_name: str, chunks: List[RenderedChunk]) -> None: ...


class LoggingSink:
    """In-memory sink used by tests and as fail-soft fallback."""

    def __init__(self) -> None:
        self.spaces: Dict[str, List[RenderedChunk]] = {}
        self.deleted: Dict[str, List[str]] = {}

    def delete(self, space_name: str, chunk_ids: List[str]) -> None:
        self.deleted.setdefault(space_name, []).extend(chunk_ids)
        kept = [
            c for c in self.spaces.get(space_name, []) if c.chunk_id not in chunk_ids
        ]
        self.spaces[space_name] = kept

    def insert(self, space_name: str, chunks: List[RenderedChunk]) -> None:
        self.spaces.setdefault(space_name, []).extend(chunks)


class ManagedSpaceSink:
    """Adapter to the KB managed space; degrades fail-soft when unwired."""

    def __init__(self, system_app: Optional[Any] = None) -> None:
        self._system_app = system_app
        self._fallback = LoggingSink()
        self._warned = False

    def _wire(self) -> Optional[Any]:
        # TODO(phase-3): wire StorageManager + EmbeddingFactory once the
        # retriever consumes the space; keep phase 2 dependency-free.
        return None

    def delete(self, space_name: str, chunk_ids: List[str]) -> None:
        store = self._wire()
        if store is None:
            self._warn_once()
            self._fallback.delete(space_name, chunk_ids)
            return
        store.delete_by_ids(chunk_ids)  # pragma: no cover - wired in phase 3

    def insert(self, space_name: str, chunks: List[RenderedChunk]) -> None:
        store = self._wire()
        if store is None:
            self._warn_once()
            self._fallback.insert(space_name, chunks)
            return
        store.load_document(chunks)  # pragma: no cover - wired in phase 3

    def _warn_once(self) -> None:
        if not self._warned:
            logger.warning(
                "ManagedSpaceSink unwired (phase 2): chunks kept in-memory; "
                "vector wiring lands with the phase-3 retriever."
            )
            self._warned = True


class SemanticPublisher:
    """Renders chunks, writes the sink, and appends the publish audit log."""

    def __init__(
        self,
        sink: Optional[ChunkSink] = None,
        log_dao: Optional[SemPublishLogDao] = None,
    ) -> None:
        self._sink = sink or ManagedSpaceSink()
        self._log_dao = log_dao or SemPublishLogDao()
        self._lock = threading.Lock()

    def publish_entry(
        self,
        ds_id: int,
        space_name: str,
        entry: SemEntryEntity,
        table_name: str,
        column_name: Optional[str] = None,
        user: Optional[str] = None,
    ) -> str:
        if entry.entry_type == "column":
            chunk = render_column_chunk(ds_id, entry, table_name, column_name or "")
        else:
            chunk = render_table_chunk(ds_id, entry, table_name)
        with self._lock:
            self._sink.delete(space_name, [chunk.chunk_id])
            self._sink.insert(space_name, [chunk])
            self._log(
                ds_id,
                f"entry:{entry.entry_type}",
                [entry.id],
                [chunk.chunk_id],
                entry.publish_version or entry.version,
                user,
            )
        return chunk.chunk_id

    def publish_metric(
        self,
        ds_id: int,
        space_name: str,
        metric: SemMetricEntity,
        user: Optional[str] = None,
        change_note: str = "",
    ) -> str:
        chunk = render_metric_chunk(ds_id, metric)
        with self._lock:
            self._sink.delete(space_name, [chunk.chunk_id])
            self._sink.insert(space_name, [chunk])
            self._log(
                ds_id,
                "metric",
                [metric.id],
                [chunk.chunk_id],
                metric.publish_version or metric.version,
                user,
                change_note,
            )
        return chunk.chunk_id

    def publish_example(
        self,
        ds_id: int,
        space_name: str,
        example: SemExampleEntity,
        user: Optional[str] = None,
    ) -> str:
        chunk = render_example_chunk(ds_id, example)
        with self._lock:
            self._sink.delete(space_name, [chunk.chunk_id])
            self._sink.insert(space_name, [chunk])
            self._log(
                ds_id,
                "example",
                [example.id],
                [chunk.chunk_id],
                example.publish_version or 1,
                user,
            )
        return chunk.chunk_id

    def _log(
        self,
        ds_id: int,
        publish_type: str,
        entry_ids: List[int],
        chunk_ids: List[str],
        version: int,
        user: Optional[str],
        change_note: str = "",
    ) -> None:
        from dbgpt_serve.semantic.models import dump_json

        self._log_dao.append(
            SemPublishLogEntity(
                ds_id=ds_id,
                publish_type=publish_type,
                entry_ids=dump_json(entry_ids),
                chunk_ids=dump_json(chunk_ids),
                version=version,
                change_note=change_note,
                published_at=datetime.utcnow(),
                published_by=user,
            )
        )
