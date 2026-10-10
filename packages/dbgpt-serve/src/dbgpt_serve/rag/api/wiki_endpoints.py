"""Wiki API endpoints.

Mounted under the RagServe prefix (``/api/v2/serve/knowledge``) with the
shape ``/{space_id}/wiki/...``. Contract mirrors WeKnora's wiki routes:

- pages CRUD with optimistic locking (409 on version conflict)
- revisions + revert-as-new-edit
- tree / index / graph / search / status views
- generate trigger for full re-generation
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request

from dbgpt._private.pydantic import BaseModel, Field
from dbgpt.component import SystemApp
from dbgpt_serve.core import Result

from ..models.wiki_db import (
    KnowledgeWikiPageDao,
    WikiVersionConflictError,
)
from ..service.wiki.config import WikiSpaceConfig
from ..service.wiki.link_service import parse_out_links

router = APIRouter()
global_system_app: Optional[SystemApp] = None


def _get_page_dao() -> KnowledgeWikiPageDao:
    return KnowledgeWikiPageDao()


def _space_or_404(space_id: int):
    from ..models.models import KnowledgeSpaceDao

    spaces = KnowledgeSpaceDao().get_knowledge_space_by_ids([space_id])
    if not spaces:
        raise HTTPException(status_code=404, detail=f"space {space_id} not found")
    return spaces[0]


def _cfg_or_400(space) -> WikiSpaceConfig:
    cfg = WikiSpaceConfig.from_space(space)
    if not cfg.enabled:
        raise HTTPException(
            status_code=400, detail="wiki is not enabled on this knowledge space"
        )
    return cfg


# --------------------------------------------------------------------------
# Schemas
# --------------------------------------------------------------------------
class WikiPageCreateRequest(BaseModel):
    slug: Optional[str] = None
    title: str = Field(..., min_length=1)
    content: str = ""
    summary: Optional[str] = None
    page_type: str = "entity"
    category_path: List[str] = Field(default_factory=list)
    aliases: List[str] = Field(default_factory=list)


class WikiPageUpdateRequest(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    summary: Optional[str] = None
    aliases: Optional[List[str]] = None
    status: Optional[str] = None
    version: Optional[int] = Field(None, description="optimistic lock; 409 when stale")


class WikiRevertRequest(BaseModel):
    slug: str
    version: int


class WikiGenerateRequest(BaseModel):
    document_ids: Optional[List[int]] = None


# --------------------------------------------------------------------------
# Status
# --------------------------------------------------------------------------
@router.get("/{space_id}/wiki/status")
async def wiki_status(space_id: int) -> Result:
    from ..models.wiki_db import KnowledgeWikiTaskDao

    space = _space_or_404(space_id)
    cfg = WikiSpaceConfig.from_space(space)
    page_dao = _get_page_dao()
    pages, total = page_dao.list_pages(space_id, page_size=10000)
    by_type: Dict[str, int] = defaultdict(int)
    total_links = 0
    orphans = 0
    for p in pages:
        by_type[p.page_type or "entity"] += 1
        out_links = parse_out_links(p.content or "")
        total_links += len(out_links)
        in_links = json.loads(p.in_links) if p.in_links else []
        if not in_links and p.page_type not in ("index", "summary"):
            orphans += 1
    return Result.succ(
        {
            "wiki_enabled": cfg.enabled,
            "granularity": cfg.granularity,
            "pending_tasks": KnowledgeWikiTaskDao().count_pending(space_id)
            if cfg.enabled
            else 0,
            "is_active": False,
            "stats": {
                "total_pages": total,
                "pages_by_type": dict(by_type),
                "total_links": total_links,
                "orphan_count": orphans,
            },
        }
    )


# --------------------------------------------------------------------------
# Pages
# --------------------------------------------------------------------------
@router.get("/{space_id}/wiki/pages")
async def wiki_list_pages(
    space_id: int,
    page_type: Optional[str] = None,
    status: Optional[str] = None,
    query: Optional[str] = None,
    category: Optional[str] = None,
    page: int = 1,
    page_size: int = 50,
) -> Result:
    _space_or_404(space_id)
    page_types = [t.strip() for t in page_type.split(",")] if page_type else None
    page_dao = _get_page_dao()
    if category is not None:
        # Exact-category listing for the sidebar tree: filter must run over
        # the whole space (not inside the paged SQL window), then paginate.
        target = [s for s in category.split("/") if s]
        all_rows, _ = page_dao.list_pages(
            space_id, page_types=page_types, status=status, page=1, page_size=100000
        )
        matched = [
            r
            for r in all_rows
            if (json.loads(r.category_path) if r.category_path else []) == target
        ]
        total = len(matched)
        start = (max(page, 1) - 1) * page_size
        rows = matched[start : start + page_size]
        return Result.succ({"pages": [r.to_dict_lite() for r in rows], "total": total})
    rows, total = page_dao.list_pages(
        space_id,
        page_types=page_types,
        status=status,
        query=query,
        page=page,
        page_size=page_size,
    )
    return Result.succ({"pages": [r.to_dict_lite() for r in rows], "total": total})


@router.post("/{space_id}/wiki/pages")
async def wiki_create_page(space_id: int, request: WikiPageCreateRequest) -> Result:
    space = _space_or_404(space_id)
    _cfg_or_400(space)
    from ..service.wiki.link_service import build_slug

    slug = build_slug(request.slug or "", request.title)
    dao = _get_page_dao()
    if dao.get_page_by_slug(space_id, slug) is not None:
        raise HTTPException(status_code=409, detail=f"slug exists: {slug}")
    page = dao.create_page(
        {
            "space_id": space_id,
            "slug": slug,
            "title": request.title,
            "page_type": request.page_type,
            "content": request.content,
            "summary": request.summary,
            "aliases": request.aliases,
            "category_path": request.category_path,
            "depth": len(request.category_path),
            "out_links": parse_out_links(request.content),
            "source_refs": [],
            "chunk_refs": [],
            "last_edit_source": "user",
        }
    )
    return Result.succ(page.to_dict())


@router.get("/{space_id}/wiki/pages/{slug_path:path}")
async def wiki_get_page(space_id: int, slug_path: str) -> Result:
    page = _get_page_dao().get_page_by_slug(space_id, slug_path)
    if page is None:
        raise HTTPException(status_code=404, detail=f"wiki page not found: {slug_path}")
    data = page.to_dict()
    in_links = json.loads(page.in_links) if page.in_links else []
    data["backlinks"] = [{"slug": s} for s in in_links]
    return Result.succ(data)


@router.put("/{space_id}/wiki/pages/{slug_path:path}")
async def wiki_update_page(
    space_id: int, slug_path: str, request: WikiPageUpdateRequest
) -> Result:
    _space_or_404(space_id)
    updates = {
        k: v
        for k, v in {
            "title": request.title,
            "content": request.content,
            "summary": request.summary,
            "aliases": request.aliases,
            "status": request.status,
        }.items()
        if v is not None
    }
    if not updates:
        raise HTTPException(status_code=400, detail="no fields to update")
    if request.content is not None:
        updates["out_links"] = parse_out_links(request.content)
    try:
        page = _get_page_dao().update_with_revision(
            space_id,
            slug_path,
            updates,
            edit_source="user",
            expected_version=request.version,
        )
    except WikiVersionConflictError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "version conflict",
                "current_version": exc.current_version,
            },
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return Result.succ(page.to_dict())


@router.delete("/{space_id}/wiki/pages/{slug_path:path}")
async def wiki_delete_page(space_id: int, slug_path: str) -> Result:
    ok = _get_page_dao().delete_page(space_id, slug_path)
    if not ok:
        raise HTTPException(status_code=404, detail=f"wiki page not found: {slug_path}")
    return Result.succ(True)


# --------------------------------------------------------------------------
# Tree / index
# --------------------------------------------------------------------------
@router.get("/{space_id}/wiki/tree")
async def wiki_tree(space_id: int) -> Result:
    _space_or_404(space_id)
    pages, total = _get_page_dao().list_pages(space_id, page_size=10000)
    by_type: Dict[str, int] = defaultdict(int)
    categories: Dict[str, Dict[tuple, int]] = defaultdict(lambda: defaultdict(int))
    for p in pages:
        by_type[p.page_type or "entity"] += 1
        try:
            path = tuple(json.loads(p.category_path)) if p.category_path else ()
        except (TypeError, ValueError):
            path = ()
        # count page into every ancestor folder for tree aggregation
        for depth in range(1, len(path) + 1):
            categories[p.page_type or "entity"][path[:depth]] += 1
    return Result.succ(
        {
            "total": total,
            "by_type": dict(by_type),
            "categories": [
                {"page_type": t, "path": list(path), "count": count}
                for t, path_map in categories.items()
                for path, count in path_map.items()
            ],
        }
    )


@router.get("/{space_id}/wiki/index")
async def wiki_index(space_id: int) -> Result:
    space = _space_or_404(space_id)
    _cfg_or_400(space)
    pages, _ = _get_page_dao().list_pages(space_id, page_size=10000)
    intro = None
    groups: Dict[tuple, List[Dict[str, Any]]] = defaultdict(list)
    for p in pages:
        if p.page_type == "index":
            intro = {"slug": p.slug, "title": p.title, "content": p.content}
            continue
        try:
            path = tuple(json.loads(p.category_path)) if p.category_path else ()
        except (TypeError, ValueError):
            path = ()
        groups[path].append(p.to_dict_lite())
    return Result.succ(
        {
            "intro": intro,
            "groups": [
                {
                    "path": list(path),
                    "pages": sorted(items, key=lambda x: x["title"] or ""),
                }
                for path, items in sorted(
                    groups.items(), key=lambda kv: (len(kv[0]), kv[0])
                )
            ],
        }
    )


# --------------------------------------------------------------------------
# Revisions / revert
# --------------------------------------------------------------------------
@router.get("/{space_id}/wiki/revisions/{slug_path:path}")
async def wiki_revisions(
    space_id: int, slug_path: str, version: Optional[int] = None
) -> Result:
    page = _get_page_dao().get_page_by_slug(space_id, slug_path)
    if page is None:
        raise HTTPException(status_code=404, detail=f"wiki page not found: {slug_path}")
    revisions = _get_page_dao().list_revisions(page.id, version=version, limit=100)
    if version is not None:
        if not revisions:
            raise HTTPException(
                status_code=404, detail=f"revision v{version} not found"
            )
        return Result.succ(revisions[0].to_dict(with_content=True))
    return Result.succ({"revisions": [r.to_dict() for r in revisions]})


@router.post("/{space_id}/wiki/revert")
async def wiki_revert(space_id: int, request: WikiRevertRequest) -> Result:
    dao = _get_page_dao()
    page = dao.get_page_by_slug(space_id, request.slug)
    if page is None:
        raise HTTPException(
            status_code=404, detail=f"wiki page not found: {request.slug}"
        )
    if request.version >= page.version:
        raise HTTPException(
            status_code=400,
            detail=f"cannot revert to current version v{page.version}",
        )
    revisions = dao.list_revisions(page.id, version=request.version)
    if not revisions:
        raise HTTPException(
            status_code=404, detail=f"revision v{request.version} not found"
        )
    rev = revisions[0]
    updated = dao.update_with_revision(
        space_id,
        request.slug,
        {
            "title": rev.title,
            "content": rev.content,
            "summary": rev.summary,
            "aliases": json.loads(rev.aliases) if rev.aliases else [],
            "out_links": parse_out_links(rev.content or ""),
        },
        edit_source="revert",
    )
    return Result.succ(updated.to_dict())


# --------------------------------------------------------------------------
# Graph / search
# --------------------------------------------------------------------------
@router.get("/{space_id}/wiki/graph")
async def wiki_graph(
    space_id: int,
    mode: str = "overview",
    center: Optional[str] = None,
    depth: int = 1,
    limit: int = 500,
) -> Result:
    page_dao = _get_page_dao()
    pages, _ = page_dao.list_pages(space_id, page_size=10000)
    nodes_by_slug = {p.slug: p for p in pages}
    out_map = {
        p.slug: [
            s
            for s in parse_out_links(p.content or "")
            if s in nodes_by_slug and s != p.slug
        ]
        for p in pages
    }
    in_map: Dict[str, List[str]] = defaultdict(list)
    for src, targets in out_map.items():
        for t in targets:
            in_map[t].append(src)

    def _node(p) -> Dict[str, Any]:
        return {
            "slug": p.slug,
            "title": p.title,
            "page_type": p.page_type,
            "link_count": len(out_map.get(p.slug, [])) + len(in_map.get(p.slug, [])),
        }

    kept: set = set()
    truncated = False
    if mode == "ego":
        if not center or center not in nodes_by_slug:
            raise HTTPException(
                status_code=404, detail=f"center page not found: {center}"
            )
        frontier = {center}
        for _ in range(max(1, min(depth, 3))):
            nxt = set()
            for slug in frontier:
                nxt.update(out_map.get(slug, []))
                nxt.update(in_map.get(slug, []))
            frontier |= nxt
            if len(frontier) > limit:
                kept = set(list(frontier)[:limit])
                truncated = True
                break
            kept = frontier
        kept.add(center)
    else:
        ranked = sorted(
            pages,
            key=lambda p: len(out_map.get(p.slug, [])) + len(in_map.get(p.slug, [])),
            reverse=True,
        )
        if len(ranked) > max(10, min(limit, 2000)):
            ranked = ranked[: max(10, min(limit, 2000))]
            truncated = True
        kept = {p.slug for p in ranked}

    nodes = [_node(nodes_by_slug[s]) for s in sorted(kept)]
    edges = [
        {"source": src, "target": t}
        for src, targets in out_map.items()
        if src in kept
        for t in targets
        if t in kept
    ]
    return Result.succ(
        {
            "nodes": nodes,
            "edges": edges,
            "meta": {"mode": mode, "total": len(nodes_by_slug), "truncated": truncated},
        }
    )


@router.get("/{space_id}/wiki/search")
async def wiki_search(space_id: int, q: str, limit: int = 20) -> Result:
    _space_or_404(space_id)
    rows, _ = _get_page_dao().list_pages(space_id, query=q, page_size=limit)
    return Result.succ(
        {
            "results": [
                {
                    "slug": r.slug,
                    "title": r.title,
                    "page_type": r.page_type,
                    "summary": r.summary,
                    "snippet": (r.content or "")[:200],
                }
                for r in rows
            ]
        }
    )


# --------------------------------------------------------------------------
# Enable + generate trigger
# --------------------------------------------------------------------------
@router.post("/{space_id}/wiki/enable")
async def wiki_enable(space_id: int) -> Result:
    """One-click entry: add ``Wiki`` to the space index methods, seed a
    default ``wiki_config`` into the space context and enqueue full
    generation over all existing documents (short debounce)."""
    import json as _json

    from ..models.models import KnowledgeSpaceDao, KnowledgeSpaceEntity
    from ..service.wiki.config import WIKI_INDEX_METHOD

    space = _space_or_404(space_id)
    already_enabled = WikiSpaceConfig.from_space(space).enabled

    if not already_enabled:
        # 1. index_methods: append "Wiki"
        try:
            methods = _json.loads(space.index_methods) if space.index_methods else []
        except (TypeError, ValueError):
            methods = []
        if not isinstance(methods, list):
            methods = []
        if not any(str(m).lower() == WIKI_INDEX_METHOD.lower() for m in methods):
            methods.append(WIKI_INDEX_METHOD)

        # 2. context: merge default wiki_config (preserve embedding etc.)
        try:
            context = _json.loads(space.context) if space.context else {}
        except (TypeError, ValueError):
            context = {}
        if not isinstance(context, dict):
            context = {}
        wiki_config = context.get("wiki_config") or {}
        if not isinstance(wiki_config, dict):
            wiki_config = {}
        wiki_config.setdefault("granularity", "standard")
        context["wiki_config"] = wiki_config

        # 3. persist both fields
        dao = KnowledgeSpaceDao()
        session = dao.get_raw_session()
        try:
            row = (
                session.query(KnowledgeSpaceEntity)
                .filter(KnowledgeSpaceEntity.id == space_id)
                .first()
            )
            if row is None:
                raise HTTPException(status_code=404, detail="space not found")
            row.index_methods = _json.dumps(methods, ensure_ascii=False)
            row.context = _json.dumps(context, ensure_ascii=False)
            row.gmt_modified = datetime.now()
            session.commit()
        finally:
            session.close()

    # 4. enqueue a full generation shortly (documents that actually have chunks)
    from ..service.wiki.task_scheduler import get_wiki_scheduler

    scheduler = get_wiki_scheduler()
    if scheduler is None:
        return Result.succ(
            {
                "status": "enabled",
                "already_enabled": already_enabled,
                "generation_enqueued": False,
            }
        )

    doc_ids = _docs_synced_with_chunks(space.name)
    scheduler.enqueue_ingest_soon(space_id, doc_ids, delay_seconds=2.0)
    return Result.succ(
        {
            "status": "enabled",
            "already_enabled": already_enabled,
            "generation_enqueued": bool(doc_ids),
            "queued_documents": len(doc_ids),
        }
    )


def _docs_synced_with_chunks(space_name: str) -> List[int]:
    """Document ids whose sync actually produced chunks.

    Wiki generation reads chunked content; documents without chunks
    (upload-only / failed sync / still running) are filtered out so the
    pipeline doesn't no-op silently.
    """
    from ..models.chunk_db import DocumentChunkDao, DocumentChunkEntity
    from ..models.document_db import KnowledgeDocumentDao, KnowledgeDocumentEntity

    doc_dao = KnowledgeDocumentDao()
    session = doc_dao.get_raw_session()
    try:
        doc_rows = (
            session.query(KnowledgeDocumentEntity)
            .filter(KnowledgeDocumentEntity.space == space_name)
            .all()
        )
    finally:
        session.close()

    chunk_dao = DocumentChunkDao()
    chunk_session = chunk_dao.get_raw_session()
    synced: List[int] = []
    try:
        for row in doc_rows:
            has_chunks = (
                chunk_session.query(DocumentChunkEntity.id)
                .filter(DocumentChunkEntity.document_id == row.id)
                .first()
                is not None
            )
            if has_chunks:
                synced.append(row.id)
    finally:
        chunk_session.close()
    return synced


@router.post("/{space_id}/wiki/generate")
async def wiki_generate(space_id: int, request: Request) -> Result:
    space = _space_or_404(space_id)
    _cfg_or_400(space)
    from ..service.wiki.task_scheduler import get_wiki_scheduler

    scheduler = get_wiki_scheduler()
    if scheduler is None:
        raise HTTPException(status_code=503, detail="wiki scheduler is not running")

    try:
        body = await request.json() if request.headers.get("content-length") else {}
    except Exception:
        body = {}
    document_ids = (body or {}).get("document_ids")

    synced_ids = _docs_synced_with_chunks(space.name)
    if not synced_ids:
        raise HTTPException(
            status_code=400,
            detail=(
                "no documents are synced yet (no chunks found). "
                "Finish document sync first — wiki generation reads chunked content."
            ),
        )

    if document_ids:
        requested = [int(d) for d in document_ids]
        valid = [d for d in requested if d in synced_ids]
        if not valid:
            raise HTTPException(
                status_code=400,
                detail="requested documents have no chunks yet (sync not finished)",
            )
        scheduler.enqueue_ingest(space_id, valid)
    else:
        for i in range(0, len(synced_ids), 100):
            scheduler.enqueue_ingest(space_id, synced_ids[i : i + 100])
    return Result.succ(
        {
            "status": "accepted",
            "debounce_seconds": 30,
            "queued_documents": len(synced_ids),
        }
    )


def init_wiki_endpoints(system_app: SystemApp, config: Any) -> None:
    global global_system_app
    global_system_app = system_app
