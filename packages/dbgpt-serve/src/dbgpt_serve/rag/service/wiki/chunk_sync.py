"""Wiki page -> vector store synchronization for retrieval boosting.

Each wiki page becomes one retrievable chunk with a deterministic id
(``wiki-<page.id>``) so re-syncs replace cleanly. The chunk carries
``metadata.source = "wiki_page"``, which the knowledge-space retriever
uses to apply a score boost (WeKnora ``PluginWikiBoost`` semantics).
"""

from __future__ import annotations

import logging
from typing import Any, Iterable

from dbgpt.core import Chunk

logger = logging.getLogger(__name__)

WIKI_CHUNK_META_SOURCE = "wiki_page"
WIKI_RETRIEVAL_BOOST = 1.3
WIKI_CHUNK_CONTENT_CHARS = 1500


def make_wiki_chunk_id(page_id: Any) -> str:
    return f"wiki-{page_id}"


def build_wiki_chunk(page: Any, space_name: str) -> Chunk:
    """Render a wiki page as a retrieval chunk."""
    title = page.title or page.slug
    summary = (page.summary or "").strip()
    body = (page.content or "").strip()[:WIKI_CHUNK_CONTENT_CHARS]
    content = "\n".join(part for part in (f"# {title}", summary, body) if part)
    category_path = []
    if page.category_path:
        try:
            import json

            category_path = json.loads(page.category_path)
        except (TypeError, ValueError):
            category_path = []
    return Chunk(
        chunk_id=make_wiki_chunk_id(page.id),
        chunk_name=title,
        content=content,
        metadata={
            "source": WIKI_CHUNK_META_SOURCE,
            "wiki_slug": page.slug,
            "wiki_page_id": page.id,
            "wiki_category": " / ".join(category_path),
            "space": space_name,
        },
    )


def sync_space_wiki_chunks(system_app: Any, space: Any, pages: Iterable[Any]) -> int:
    """Upsert wiki page chunks into the space's vector store.

    Called from the finalize phase; failures are non-fatal by contract —
    the caller already wraps this in try/except. Returns the number of
    synced pages.
    """
    from dbgpt_serve.rag.storage_manager import StorageManager

    store = StorageManager.get_instance(system_app)
    connector = store.get_storage_connector(space.name, space.vector_type)

    synced = 0
    pending: list = []
    for page in pages:
        if page.page_type == "index":
            continue  # the catalog page is navigation, not retrieval content
        pending.append(page)

    if not pending:
        return 0

    # Replace in one pass: deterministic ids make delete+load idempotent.
    stale_ids = [make_wiki_chunk_id(p.id) for p in pending]
    try:
        connector.delete_by_ids(",".join(stale_ids))
    except Exception as exc:
        logger.debug(f"wiki chunk delete-before-write skipped: {exc}")

    chunks = [build_wiki_chunk(p, space.name) for p in pending]
    connector.load_document(chunks)
    synced = len(chunks)
    logger.info(f"wiki chunk sync: {synced} page chunk(s) loaded")
    return synced


def delete_wiki_chunk(system_app: Any, space: Any, page_id: Any) -> None:
    """Remove a page's retrieval chunk (used when pages are deleted)."""
    try:
        from dbgpt_serve.rag.storage_manager import StorageManager

        store = StorageManager.get_instance(system_app)
        connector = store.get_storage_connector(space.name, space.vector_type)
        connector.delete_by_ids(make_wiki_chunk_id(page_id))
    except Exception as exc:
        logger.debug(f"wiki chunk delete skipped for page {page_id}: {exc}")


def apply_wiki_boost(chunks_with_scores: list) -> list:
    """Multiply scores of wiki chunks after rerank (in place)."""
    for chunk in chunks_with_scores:
        try:
            meta = getattr(chunk, "metadata", None)
            if meta and meta.get("source") == WIKI_CHUNK_META_SOURCE:
                chunk.score = float(chunk.score) * WIKI_RETRIEVAL_BOOST
        except (TypeError, ValueError, AttributeError):
            continue
    return chunks_with_scores
