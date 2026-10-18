"""Wiki data models for the LLM-Wiki capability.

Ported from WeKnora's wiki subsystem (wiki_pages / wiki_page_revisions /
task queue), adapted to DB-GPT's storage conventions:

- JSON-ish fields are stored as ``Text`` holding a JSON string (same as
  ``knowledge_space.index_methods``).
- Revisions follow WeKnora's ``UpdateWithRevision`` algorithm: the
  superseded state is snapshotted inside the same transaction, then the
  page row is rewritten and ``version`` bumps only when a user-visible
  field actually changed. Snapshotting is idempotent on
  ``(page_id, version)``.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from sqlalchemy import Column, DateTime, Integer, String, Text, or_

from dbgpt.storage.metadata import BaseDao, Model

logger = logging.getLogger(__name__)

WIKI_PAGE_TYPES = (
    "summary",  # per-document summary page
    "entity",
    "concept",
    "index",  # the KB-level catalog page
    "synthesis",
    "comparison",
)

WIKI_EDIT_SOURCES = ("pipeline", "agent", "user", "revert")

WIKI_REVISION_PRUNABLE_SOURCES = ("pipeline", "")  # machine-authored revisions
WIKI_REVISION_SOFT_CAP = 50
WIKI_REVISION_HARD_CAP = 200

WIKI_TASK_TYPES = ("wiki:ingest", "wiki:finalize", "wiki:reconcile")

# Fields whose change triggers a version bump / revision snapshot
VERSIONED_FIELDS = ("title", "content", "summary", "aliases")


class WikiVersionConflictError(Exception):
    """Raised when an optimistic-lock guarded update hits a stale version."""

    def __init__(self, current_version: int):
        super().__init__(f"version conflict, current_version={current_version}")
        self.current_version = current_version


def _dump_json(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)


def _load_json(value: Optional[str], default: Any = None) -> Any:
    if value is None or value == "":
        return default
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default


class KnowledgeWikiPageEntity(Model):
    __tablename__ = "knowledge_wiki_page"

    id = Column(Integer, primary_key=True)
    space_id = Column(Integer, index=True)
    slug = Column(String(255), index=True)
    title = Column(String(255))
    page_type = Column(String(32))
    status = Column(String(32), default="published")
    content = Column(Text)
    summary = Column(Text)
    aliases = Column(Text)  # JSON string list
    parent_slug = Column(String(255))
    category_path = Column(Text)  # JSON string list[str]
    depth = Column(Integer, default=0)
    sort_order = Column(Integer, default=0)
    source_refs = Column(Text)  # JSON string list[{document_id, doc_name}]
    chunk_refs = Column(Text)  # JSON string list[str]
    in_links = Column(Text)  # JSON string list[str]
    out_links = Column(Text)  # JSON string list[str]
    version = Column(Integer, default=1)
    last_edit_source = Column(String(16), default="pipeline")
    gmt_created = Column(DateTime)
    gmt_modified = Column(DateTime)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "space_id": self.space_id,
            "slug": self.slug,
            "title": self.title,
            "page_type": self.page_type,
            "status": self.status,
            "content": self.content,
            "summary": self.summary,
            "aliases": _load_json(self.aliases, []),
            "parent_slug": self.parent_slug,
            "category_path": _load_json(self.category_path, []),
            "depth": self.depth or 0,
            "sort_order": self.sort_order or 0,
            "source_refs": _load_json(self.source_refs, []),
            "chunk_refs": _load_json(self.chunk_refs, []),
            "in_links": _load_json(self.in_links, []),
            "out_links": _load_json(self.out_links, []),
            "version": self.version or 1,
            "last_edit_source": self.last_edit_source,
            "gmt_created": self.gmt_created.isoformat() if self.gmt_created else None,
            "gmt_modified": self.gmt_modified.isoformat()
            if self.gmt_modified
            else None,
        }

    def to_dict_lite(self) -> Dict[str, Any]:
        """Slim projection for index/graph/list payloads."""
        return {
            "id": self.id,
            "slug": self.slug,
            "title": self.title,
            "page_type": self.page_type,
            "status": self.status,
            "summary": self.summary,
            "parent_slug": self.parent_slug,
            "category_path": _load_json(self.category_path, []),
            "depth": self.depth or 0,
            "version": self.version or 1,
            "last_edit_source": self.last_edit_source,
            "gmt_modified": self.gmt_modified.isoformat()
            if self.gmt_modified
            else None,
        }


class KnowledgeWikiPageRevisionEntity(Model):
    """Immutable snapshot of a superseded page version.

    The *current* state lives on the page row itself; each content-changing
    write snapshots the pre-edit state here.
    """

    __tablename__ = "knowledge_wiki_page_revision"

    id = Column(Integer, primary_key=True)
    page_id = Column(Integer, index=True)
    space_id = Column(Integer, index=True)
    version = Column(Integer)
    title = Column(String(255))
    content = Column(Text)
    summary = Column(Text)
    aliases = Column(Text)
    edit_source = Column(String(16))
    editor = Column(String(64))
    gmt_created = Column(DateTime)

    def to_dict(self, with_content: bool = False) -> Dict[str, Any]:
        data = {
            "id": self.id,
            "page_id": self.page_id,
            "version": self.version,
            "title": self.title,
            "summary": self.summary,
            "edit_source": self.edit_source,
            "editor": self.editor,
            "gmt_created": self.gmt_created.isoformat() if self.gmt_created else None,
        }
        if with_content:
            data["content"] = self.content
            data["aliases"] = _load_json(self.aliases, [])
        return data


class KnowledgeWikiTaskEntity(Model):
    """Durable wiki task record (replaces WeKnora's asynq/Redis queue).

    ``run_after`` implements debounce: enqueues repeatedly push the due
    time forward and merge payloads, so bursty document syncs collapse
    into a single ingest run.
    """

    __tablename__ = "knowledge_wiki_task"

    id = Column(Integer, primary_key=True)
    space_id = Column(Integer, index=True)
    task_type = Column(String(32), index=True)
    status = Column(String(16), default="pending")  # pending/running/done/failed/dead
    payload = Column(Text)  # JSON string
    run_after = Column(DateTime)
    retry_count = Column(Integer, default=0)
    last_error = Column(Text)
    gmt_created = Column(DateTime)
    gmt_modified = Column(DateTime)


class KnowledgeWikiPageDao(BaseDao):
    # ------------------------------------------------------------------
    # Basic CRUD
    # ------------------------------------------------------------------
    def create_page(self, values: Dict[str, Any]) -> KnowledgeWikiPageEntity:
        now = datetime.now()
        entity = KnowledgeWikiPageEntity(
            space_id=values["space_id"],
            slug=values["slug"],
            title=values.get("title") or values["slug"],
            page_type=values.get("page_type") or "entity",
            status=values.get("status") or "published",
            content=values.get("content") or "",
            summary=values.get("summary"),
            aliases=_dump_json(values.get("aliases")),
            parent_slug=values.get("parent_slug"),
            category_path=_dump_json(values.get("category_path")),
            depth=values.get("depth") or 0,
            sort_order=values.get("sort_order") or 0,
            source_refs=_dump_json(values.get("source_refs")),
            chunk_refs=_dump_json(values.get("chunk_refs")),
            in_links="[]",
            out_links=_dump_json(values.get("out_links")) or "[]",
            version=1,
            last_edit_source=values.get("last_edit_source") or "pipeline",
            gmt_created=now,
            gmt_modified=now,
        )
        session = self.get_raw_session()
        try:
            session.add(entity)
            # keep attribute values available on the detached instance
            session.expire_on_commit = False
            session.commit()
            session.expunge(entity)
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
        return entity

    def get_page_by_slug(
        self, space_id: int, slug: str
    ) -> Optional[KnowledgeWikiPageEntity]:
        session = self.get_raw_session()
        try:
            return (
                session.query(KnowledgeWikiPageEntity)
                .filter(
                    KnowledgeWikiPageEntity.space_id == space_id,
                    KnowledgeWikiPageEntity.slug == slug,
                    KnowledgeWikiPageEntity.status != "archived",
                )
                .first()
            )
        finally:
            session.close()

    def list_pages(
        self,
        space_id: int,
        page_types: Optional[Sequence[str]] = None,
        status: Optional[str] = None,
        query: Optional[str] = None,
        category_prefix: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Tuple[List[KnowledgeWikiPageEntity], int]:
        """Paged, filtered page listing. Returns (rows, total)."""
        session = self.get_raw_session()
        try:
            q = session.query(KnowledgeWikiPageEntity).filter(
                KnowledgeWikiPageEntity.space_id == space_id
            )
            if page_types:
                types = [t.strip() for t in page_types if t]
                if types:
                    q = q.filter(KnowledgeWikiPageEntity.page_type.in_(types))
            if status:
                q = q.filter(KnowledgeWikiPageEntity.status == status)
            if category_prefix is not None:
                q = q.filter(
                    KnowledgeWikiPageEntity.category_path.like(f"{category_prefix}%")
                )
            if query:
                like = f"%{query}%"
                q = q.filter(
                    or_(
                        KnowledgeWikiPageEntity.title.like(like),
                        KnowledgeWikiPageEntity.slug.like(like),
                        KnowledgeWikiPageEntity.aliases.like(like),
                        KnowledgeWikiPageEntity.content.like(like),
                    )
                )
            total = q.count()
            rows = (
                q.order_by(
                    KnowledgeWikiPageEntity.page_type.asc(),
                    KnowledgeWikiPageEntity.depth.asc(),
                    KnowledgeWikiPageEntity.sort_order.asc(),
                    KnowledgeWikiPageEntity.id.asc(),
                )
                .offset((max(page, 1) - 1) * page_size)
                .limit(page_size)
                .all()
            )
            return rows, total
        finally:
            session.close()

    def list_pages_by_slugs(
        self, space_id: int, slugs: Iterable[str]
    ) -> List[KnowledgeWikiPageEntity]:
        slugs = [s for s in slugs if s]
        if not slugs:
            return []
        session = self.get_raw_session()
        try:
            return (
                session.query(KnowledgeWikiPageEntity)
                .filter(
                    KnowledgeWikiPageEntity.space_id == space_id,
                    KnowledgeWikiPageEntity.slug.in_(slugs),
                    KnowledgeWikiPageEntity.status != "archived",
                )
                .all()
            )
        finally:
            session.close()

    def list_pages_by_source_document(
        self, space_id: int, document_id: str
    ) -> List[KnowledgeWikiPageEntity]:
        """Find pages whose ``source_refs`` mention the given document.

        Wiki pages may be regenerated many times, so we match on the JSON
        text rather than parse every row in Python first.
        """
        marker = f'"document_id": {document_id}'
        alt_marker = f'"document_id":"{document_id}"'
        session = self.get_raw_session()
        try:
            return (
                session.query(KnowledgeWikiPageEntity)
                .filter(
                    KnowledgeWikiPageEntity.space_id == space_id,
                    or_(
                        KnowledgeWikiPageEntity.source_refs.like(f"%{marker}%"),
                        KnowledgeWikiPageEntity.source_refs.like(f"%{alt_marker}%"),
                    ),
                )
                .all()
            )
        finally:
            session.close()

    def delete_page(self, space_id: int, slug: str) -> bool:
        session = self.get_raw_session()
        try:
            row = (
                session.query(KnowledgeWikiPageEntity)
                .filter(
                    KnowledgeWikiPageEntity.space_id == space_id,
                    KnowledgeWikiPageEntity.slug == slug,
                )
                .first()
            )
            if row is None:
                return False
            session.query(KnowledgeWikiPageRevisionEntity).filter(
                KnowledgeWikiPageRevisionEntity.page_id == row.id
            ).delete()
            session.delete(row)
            session.commit()
            return True
        finally:
            session.close()

    # ------------------------------------------------------------------
    # Snapshot-then-update (WeKnora UpdateWithRevision port)
    # ------------------------------------------------------------------
    def update_with_revision(
        self,
        space_id: int,
        slug: str,
        updates: Dict[str, Any],
        edit_source: str = "user",
        editor: Optional[str] = None,
        expected_version: Optional[int] = None,
        touch_source: bool = True,
    ) -> KnowledgeWikiPageEntity:
        """Apply a partial update; snapshot the pre-edit state first.

        - Raises :class:`WikiVersionConflictError` when ``expected_version``
          is given and stale (the caller gets the current version).
        - Bumps ``version`` and writes a revision row only when a versioned
          field actually changed.
        - With ``touch_source=False`` (link-cache maintenance), the update
          does not re-stamp ``last_edit_source``/``gmt_modified`` so user
          edit provenance survives background passes.
        """
        session = self.get_raw_session()
        try:
            page = (
                session.query(KnowledgeWikiPageEntity)
                .filter(
                    KnowledgeWikiPageEntity.space_id == space_id,
                    KnowledgeWikiPageEntity.slug == slug,
                )
                .first()
            )
            if page is None:
                raise ValueError(f"wiki page not found: {slug}")
            if expected_version is not None and page.version != expected_version:
                raise WikiVersionConflictError(page.version or 1)

            changed_versioned = False
            normalized: Dict[str, Any] = {}
            for key, value in updates.items():
                if key in (
                    "id",
                    "space_id",
                    "slug",
                    "gmt_created",
                    "gmt_modified",
                    "id",
                ):
                    continue
                if key in ("aliases", "category_path", "source_refs", "chunk_refs"):
                    value = _dump_json(value)
                elif key in ("in_links", "out_links") and isinstance(value, list):
                    value = _dump_json(value)
                if key in VERSIONED_FIELDS and getattr(page, key, None) != value:
                    changed_versioned = True
                if value is not None or key in ("summary",):
                    normalized[key] = value

            if not normalized:
                return page  # nothing to do

            if changed_versioned:
                # Idempotent snapshot: unique on (page_id, version)
                exists = (
                    session.query(KnowledgeWikiPageRevisionEntity)
                    .filter(
                        KnowledgeWikiPageRevisionEntity.page_id == page.id,
                        KnowledgeWikiPageRevisionEntity.version == page.version,
                    )
                    .first()
                )
                if exists is None:
                    session.add(
                        KnowledgeWikiPageRevisionEntity(
                            page_id=page.id,
                            space_id=space_id,
                            version=page.version,
                            title=page.title,
                            content=page.content,
                            summary=page.summary,
                            aliases=page.aliases,
                            edit_source=page.last_edit_source,
                            editor=editor,
                            gmt_created=datetime.now(),
                        )
                    )
                page.version = (page.version or 1) + 1

            for key, value in normalized.items():
                setattr(page, key, value)
            if touch_source:
                page.last_edit_source = edit_source
                page.gmt_modified = datetime.now()
            # keep attribute values available on the detached instance
            session.expire_on_commit = False
            session.commit()
            session.expunge(page)
            return page
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    # ------------------------------------------------------------------
    # Revisions
    # ------------------------------------------------------------------
    def list_revisions(
        self, page_id: int, version: Optional[int] = None, limit: int = 50, offset=0
    ) -> List[KnowledgeWikiPageRevisionEntity]:
        session = self.get_raw_session()
        try:
            q = session.query(KnowledgeWikiPageRevisionEntity).filter(
                KnowledgeWikiPageRevisionEntity.page_id == page_id
            )
            if version is not None:
                q = q.filter(KnowledgeWikiPageRevisionEntity.version == version)
                return q.all()
            return (
                q.order_by(KnowledgeWikiPageRevisionEntity.version.desc())
                .limit(limit)
                .offset(offset)
                .all()
            )
        finally:
            session.close()

    def prune_revisions(self, page_id: int) -> int:
        """Two-tier retention: prune machine-authored revisions beyond the
        soft cap, then hard-cap everything (WeKnora semantics)."""
        session = self.get_raw_session()
        try:
            all_revs = (
                session.query(KnowledgeWikiPageRevisionEntity)
                .filter(KnowledgeWikiPageRevisionEntity.page_id == page_id)
                .order_by(KnowledgeWikiPageRevisionEntity.version.desc())
                .all()
            )
            pruned = 0
            soft_count = 0
            for idx, rev in enumerate(all_revs):
                if rev.edit_source in WIKI_REVISION_PRUNABLE_SOURCES:
                    soft_count += 1
                    if soft_count > WIKI_REVISION_SOFT_CAP:
                        session.delete(rev)
                        pruned += 1
                        continue
                if idx + 1 > WIKI_REVISION_HARD_CAP:
                    session.delete(rev)
                    pruned += 1
            session.commit()
            return pruned
        finally:
            session.close()


class KnowledgeWikiTaskDao(BaseDao):
    # ------------------------------------------------------------------
    # Enqueue (debounce-aware upsert)
    # ------------------------------------------------------------------
    def enqueue(
        self,
        space_id: int,
        task_type: str,
        payload: Optional[Dict[str, Any]] = None,
        delay_seconds: float = 0,
        merge_document_ids: Optional[Sequence[str]] = None,
    ) -> None:
        """Create or refresh a pending task.

        If a pending task of the same (space, type) exists: merge given
        ``merge_document_ids`` into its payload and push ``run_after``
        forward (debounce). Terminal tasks are ignored.
        """
        now = datetime.now()
        session = self.get_raw_session()
        try:
            task = (
                session.query(KnowledgeWikiTaskEntity)
                .filter(
                    KnowledgeWikiTaskEntity.space_id == space_id,
                    KnowledgeWikiTaskEntity.task_type == task_type,
                    KnowledgeWikiTaskEntity.status.in_(["pending", "running"]),
                )
                .first()
            )
            if task is not None and task.status == "running":
                # Another worker is on it; the close-out will re-enqueue a
                # finalize if needed. Nothing to do.
                session.close()
                return
            if task is None:
                payload_map = dict(payload or {})
                if merge_document_ids:
                    payload_map["document_ids"] = sorted(set(merge_document_ids))
                session.add(
                    KnowledgeWikiTaskEntity(
                        space_id=space_id,
                        task_type=task_type,
                        status="pending",
                        payload=_dump_json(payload_map),
                        run_after=now + timedelta(seconds=delay_seconds),
                        retry_count=0,
                        gmt_created=now,
                        gmt_modified=now,
                    )
                )
            else:
                payload_map = _load_json(task.payload, {}) or {}
                if merge_document_ids:
                    doc_ids = set(payload_map.get("document_ids") or [])
                    doc_ids.update(merge_document_ids)
                    payload_map["document_ids"] = sorted(doc_ids)
                if payload:
                    for key, value in payload.items():
                        if key == "document_ids" and payload_map.get("document_ids"):
                            continue
                        payload_map[key] = value
                task.payload = _dump_json(payload_map)
                task.run_after = now + timedelta(seconds=delay_seconds)
                task.gmt_modified = now
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    # ------------------------------------------------------------------
    # Worker ops
    # ------------------------------------------------------------------
    def claim_due_tasks(self, limit: int = 5) -> List[KnowledgeWikiTaskEntity]:
        """Claim due pending tasks (single worker P0; P2 may add row locks)."""
        now = datetime.now()
        session = self.get_raw_session()
        try:
            due = (
                session.query(KnowledgeWikiTaskEntity)
                .filter(
                    KnowledgeWikiTaskEntity.status == "pending",
                    KnowledgeWikiTaskEntity.run_after <= now,
                )
                .order_by(KnowledgeWikiTaskEntity.run_after.asc())
                .limit(limit)
                .all()
            )
            claimed: List[KnowledgeWikiTaskEntity] = []
            for task in due:
                task.status = "running"
                task.gmt_modified = now
                claimed.append(task)
            if claimed:
                # keep attribute values available on the detached instances
                session.expire_on_commit = False
                session.commit()
                for task in claimed:
                    session.expunge(task)
            return claimed
        finally:
            session.close()

    def complete_task(self, task_id: int, error: Optional[str] = None) -> None:
        """Close out a running task; failures retry with fixed backoff and
        dead-letter after 3 retries."""
        session = self.get_raw_session()
        try:
            task = (
                session.query(KnowledgeWikiTaskEntity)
                .filter(KnowledgeWikiTaskEntity.id == task_id)
                .first()
            )
            if task is None:
                return
            now = datetime.now()
            task.gmt_modified = now
            if error:
                task.retry_count = (task.retry_count or 0) + 1
                task.last_error = error[:2000]
                if task.retry_count >= 3:
                    task.status = "dead"
                else:
                    task.status = "pending"
                    task.run_after = now + timedelta(seconds=15)
            else:
                task.status = "done"
            session.commit()
        finally:
            session.close()

    def finish_re_enqueue_finalize(self, space_id: int) -> None:
        """After an ingest, ensure a debounced finalize exists."""
        self.enqueue(space_id, "wiki:finalize", payload={}, delay_seconds=20)

    def recover_stale_running(self, stale_minutes: int = 15) -> int:
        """Reset running tasks that look abandoned (e.g. process restart)."""
        deadline = datetime.now() - timedelta(minutes=stale_minutes)
        session = self.get_raw_session()
        try:
            rows = (
                session.query(KnowledgeWikiTaskEntity)
                .filter(
                    KnowledgeWikiTaskEntity.status == "running",
                    KnowledgeWikiTaskEntity.gmt_modified < deadline,
                )
                .all()
            )
            for task in rows:
                task.status = "pending"
                task.run_after = datetime.now()
                task.gmt_modified = datetime.now()
            if rows:
                session.commit()
            return len(rows)
        finally:
            session.close()

    def count_pending(self, space_id: int) -> int:
        session = self.get_raw_session()
        try:
            return (
                session.query(KnowledgeWikiTaskEntity)
                .filter(
                    KnowledgeWikiTaskEntity.space_id == space_id,
                    KnowledgeWikiTaskEntity.status.in_(["pending", "running"]),
                )
                .count()
            )
        finally:
            session.close()


class KnowledgeWikiRevisionDao(BaseDao):
    """Thin helper kept separate from the page DAO for endpoint clarity."""

    def get_revision(
        self, page_id: int, version: int
    ) -> Optional[KnowledgeWikiPageRevisionEntity]:
        session = self.get_raw_session()
        try:
            return (
                session.query(KnowledgeWikiPageRevisionEntity)
                .filter(
                    KnowledgeWikiPageRevisionEntity.page_id == page_id,
                    KnowledgeWikiPageRevisionEntity.version == version,
                )
                .first()
            )
        finally:
            session.close()
