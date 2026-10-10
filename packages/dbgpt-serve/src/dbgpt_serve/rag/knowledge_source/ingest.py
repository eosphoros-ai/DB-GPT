"""Ingest adapter: hand a connector FetchedItem to the existing document
pipeline — THE seam between knowledge_source and domain/index layers.

Precedent: GitRepoSyncService short-circuits the normal sync gate by
driving chunks + document status directly (git_repo_sync_service.py:300+).
Here we clear stale chunks and re-drive ``Service._sync_knowledge_document``
so the standard domain pipeline (Normal / custom) fires and the tail hooks
(wiki enqueue, heading graph) behave exactly like a manual sync.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, Optional

if TYPE_CHECKING:
    from dbgpt_serve.rag.models.document_db import KnowledgeDocumentEntity

logger = logging.getLogger(__name__)


def content_hash(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


class IngestResult:
    CREATED = "created"
    UPDATED = "updated"
    SKIPPED = "skipped"


class KnowledgeSourceIngestor:
    """Applies fetched items to knowledge documents."""

    def __init__(self, rag_service: Any):
        self._service = rag_service

    async def ingest_item(
        self,
        space_id: int,
        source_row: Any,  # KnowledgeSourceEntity
        item: Any,  # FetchedItem
        mapping: Dict[str, int],
    ) -> str:
        from dbgpt_serve.rag.models.document_db import KnowledgeDocumentEntity

        doc_id = mapping.get(item.external_id)
        doc: Optional[KnowledgeDocumentEntity] = None
        if doc_id:
            docs = self._service._document_dao.documents_by_ids([int(doc_id)])
            doc = docs[0] if docs else None
        if doc is None:
            # mapping miss (e.g. a previous run failed before persisting
            # mapping): reuse an earlier same-name doc so old broken rows
            # are healed in place instead of duplicating
            doc = self._find_existing_doc(
                space_id, (item.title or item.external_id)[:255]
            )

        # conflict resolution: skip when content unchanged
        if doc is not None and source_row.conflict_strategy == "skip":
            if content_hash(doc.content) == content_hash(item.content):
                return IngestResult.SKIPPED

        chunk_params = self._build_chunk_params(space_id)

        if doc is not None:
            self._clear_stale_doc(doc)
            doc.content = item.content
            # self-heal: content-platform docs must use the TEXT knowledge
            # type (DOCUMENT routes to from_file_path, which treats the
            # content as a file path and dies on extensionless text)
            doc.doc_type = "TEXT"
            doc.status = "RUNNING"
            doc.result = f"knowledge-source sync: {source_row.name}"
            self._service._document_dao.update_knowledge_document(doc)
            action = IngestResult.UPDATED
        else:
            space = self._service.get({"id": space_id})
            entity = KnowledgeDocumentEntity(
                doc_name=(item.title or item.external_id)[:255],
                # TEXT → KnowledgeFactory.from_text: content-platform docs
                # carry no file extension and are ingested from content
                doc_type="TEXT",
                space=space.name,
                content=item.content,
                chunk_size=0,
                status="RUNNING",
                last_sync=datetime.now(),
                result=f"knowledge-source sync: {source_row.name}",
            )
            created_id = self._service._document_dao.create_knowledge_document(entity)
            docs = self._service._document_dao.documents_by_ids([int(created_id)])
            doc = docs[0]
            action = IngestResult.CREATED

        try:
            await self._service._sync_knowledge_document(space_id, doc, chunk_params)
        except Exception:
            # keep the sync going for other items; mark the doc failed
            doc.status = "FAILED"
            doc.result = "knowledge-source sync failed (embedding/index)"
            self._service._document_dao.update_knowledge_document(doc)
            raise

        mapping[item.external_id] = int(doc.id)
        return action

    def _find_existing_doc(
        self, space_id: int, doc_name: str
    ) -> Optional["KnowledgeDocumentEntity"]:
        """Latest knowledge-source-managed doc with this name in the space
        (any status) — the reuse keeps old failed rows from duplicating."""
        from dbgpt_serve.rag.models.document_db import (
            KnowledgeDocumentDao,
            KnowledgeDocumentEntity,
        )

        space = self._service.get({"id": space_id})
        if space is None:
            return None
        dao = KnowledgeDocumentDao()
        session = dao.get_raw_session()
        try:
            return (
                session.query(KnowledgeDocumentEntity)
                .filter(
                    KnowledgeDocumentEntity.space == space.name,
                    KnowledgeDocumentEntity.doc_name == doc_name,
                    KnowledgeDocumentEntity.result.like("knowledge-source%"),
                )
                .order_by(KnowledgeDocumentEntity.id.desc())
                .first()
            )
        finally:
            session.close()

    def _clear_stale_doc(self, doc: Any) -> None:
        """Remove old vector entries and chunk rows before a content update."""
        if doc.vector_ids:
            try:
                store = self._service.create_vector_store(doc.space)
                store.delete_by_ids(doc.vector_ids)
            except Exception as exc:  # noqa: BLE001 - vector cleanup is best effort
                logger.warning(
                    f"knowledge-source: vector cleanup failed for doc {doc.id}: {exc}"
                )
        self._service._chunk_dao.raw_delete(doc.id)

    def _build_chunk_params(self, space_id: int) -> Any:
        from dbgpt_ext.rag.chunk_manager import ChunkParameters

        space_context = self._service.get_space_context(space_id) or {}
        embedding_ctx = space_context.get("embedding") or {}
        chunk_size = (
            self._service._serve_config.chunk_size
            if not embedding_ctx.get("chunk_size")
            else int(embedding_ctx["chunk_size"])
        )
        chunk_overlap = (
            self._service._serve_config.chunk_overlap
            if not embedding_ctx.get("chunk_overlap")
            else int(embedding_ctx["chunk_overlap"])
        )
        return ChunkParameters(
            chunk_strategy="CHUNK_BY_SIZE",
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
