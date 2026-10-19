"""Wiki generation pipeline (WeKnora wiki_ingest port).

Five phases, mirroring the reference implementation:

1. MAP (per document, concurrent): candidate slug extraction + summary
   page + chunk citation grounding.
2. DEDUP: surface-similarity prefilter + LLM merge confirmation.
3. TAXONOMY: single-pass folder planning (max two levels).
4. REDUCE (per slug): merge batch contributions and incrementally rewrite
   the page ("compiler, not writer").
5. FINALIZE (per space, debounced): index page rebuild, dead-link
   cleanup, cross-link injection, wiki chunk sync.

Plus ``wiki:reconcile`` handling document deletion cleanup.

All page writes go through :meth:`KnowledgeWikiPageDao.update_with_revision`
so every generation pass is tracked as a revision with
``edit_source="pipeline"``.
"""

from __future__ import annotations

import asyncio
import difflib
import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from dbgpt.component import ComponentType
from dbgpt.core import LLMClient, ModelMessage, ModelRequest
from dbgpt.model import DefaultLLMClient
from dbgpt.model.cluster import WorkerManagerFactory
from dbgpt_serve.rag.models.wiki_db import (
    KnowledgeWikiPageDao,
    WikiVersionConflictError,
)
from dbgpt_serve.rag.service.wiki import prompts
from dbgpt_serve.rag.service.wiki.config import WikiSpaceConfig
from dbgpt_serve.rag.service.wiki.link_service import (
    build_slug,
    compute_in_link_diff,
    parse_out_links,
    parse_summary_line,
    strip_dead_links,
)

logger = logging.getLogger(__name__)

MAX_CONTENT_CHARS = 32000
CITATION_BATCH_CHARS = 12000
MAP_CONCURRENCY = 4
REDUCE_CONCURRENCY = 2
LLM_MAX_ATTEMPTS = 3
MAX_EXCERPT_PER_DOC = 2
EXCERPT_CHARS = 1200
INDEX_SLUG = "index"

_JSON_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.MULTILINE)


def parse_llm_json(text: str) -> Any:
    """Tolerant JSON extraction: strips code fences and trailing prose."""
    if not text:
        raise ValueError("empty llm output")
    cleaned = _JSON_FENCE_RE.sub("", text.strip())
    start = min(
        (i for i in (cleaned.find("{"), cleaned.find("[")) if i >= 0), default=-1
    )
    if start > 0:
        cleaned = cleaned[start:]
    try:
        return json.loads(cleaned)
    except (TypeError, ValueError):
        # last resort: outermost brace/bracket slice
        for open_ch, close_ch in (("{", "}"), ("[", "]")):
            if open_ch in cleaned and close_ch in cleaned:
                sliced = cleaned[cleaned.find(open_ch) : cleaned.rfind(close_ch) + 1]
                try:
                    return json.loads(sliced)
                except (TypeError, ValueError):
                    continue
        raise


@dataclass
class Candidate:
    name: str
    slug: str
    aliases: List[str] = field(default_factory=list)
    description: str = ""
    chunk_ids: List[int] = field(default_factory=list)
    document_ids: List[int] = field(default_factory=list)

    def to_prompt_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "slug": self.slug,
            "aliases": self.aliases,
            "description": self.description,
        }


@dataclass
class PendingPage:
    """Aggregate state for one slug between MAP and REDUCE."""

    slug: str
    candidate: Optional[Candidate] = None
    summary_page: Optional[Dict[str, Any]] = None  # summary page payload
    materials: List[Dict[str, Any]] = field(default_factory=list)


class WikiIngestPipeline:
    def __init__(self, system_app: Any, space: Any, cfg: WikiSpaceConfig):
        self._system_app = system_app
        self._space = space
        self._cfg = cfg
        self._page_dao = KnowledgeWikiPageDao()
        self._model_name: Optional[str] = None
        self._llm_client: Optional[LLMClient] = None

    # ------------------------------------------------------------------
    # LLM plumbing
    # ------------------------------------------------------------------
    @property
    def llm_client(self) -> LLMClient:
        if self._llm_client is None:
            worker_manager = self._system_app.get_component(
                ComponentType.WORKER_MANAGER_FACTORY, WorkerManagerFactory
            ).create()
            self._llm_client = DefaultLLMClient(worker_manager, True)
        return self._llm_client

    async def resolve_model(self) -> str:
        if self._model_name:
            return self._model_name
        if self._cfg.synthesis_model:
            self._model_name = self._cfg.synthesis_model
            return self._model_name
        models = await self.llm_client.models()
        if not models:
            raise Exception("wiki pipeline: no models available")
        self._model_name = models[0].model
        logger.info(f"wiki pipeline resolved synthesis model: {self._model_name}")
        return self._model_name

    async def _llm_text(self, llm_prompt: str, retries: int = LLM_MAX_ATTEMPTS) -> str:
        model = await self.resolve_model()
        request = ModelRequest(
            model=model,
            messages=[ModelMessage(role="human", content=llm_prompt)],
        )
        last_error: Optional[str] = None
        for attempt in range(1, retries + 1):
            try:
                response = await self.llm_client.generate(request=request)
                if response.success and response.text:
                    return response.text
                last_error = f"unsuccessful: {response.error_code} {response.text}"
            except Exception as exc:  # transient network/provider errors
                last_error = str(exc)
            logger.warning(f"wiki llm attempt {attempt}/{retries} failed: {last_error}")
            if attempt < retries:
                await asyncio.sleep(2**attempt)
        raise RuntimeError(f"wiki llm failed after {retries} attempts: {last_error}")

    async def _llm_json(self, llm_prompt: str) -> Any:
        return parse_llm_json(await self._llm_text(llm_prompt))

    # ------------------------------------------------------------------
    # Data access helpers
    # ------------------------------------------------------------------
    def _load_document(self, document_id: int) -> Optional[Any]:
        from dbgpt_serve.rag.models.document_db import KnowledgeDocumentDao

        docs = KnowledgeDocumentDao().get_one({"id": document_id})
        return docs

    def _load_document_content(
        self, document_id: int
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """Return (full_text_capped, chunk_rows) for a document."""
        from dbgpt_serve.rag.models.chunk_db import (
            DocumentChunkDao,
            DocumentChunkEntity,
        )

        rows = DocumentChunkDao().get_document_chunks(
            DocumentChunkEntity(document_id=document_id), page=1, page_size=10000
        )
        chunks = []
        total_rows = rows if not isinstance(rows, tuple) else rows[0]
        for row in sorted(total_rows, key=lambda r: r.id or 0):
            chunks.append({"chunk_id": row.id, "content": (row.content or "").strip()})
        text = "\n\n".join(c["content"] for c in chunks)
        return text[:MAX_CONTENT_CHARS], chunks

    def _existing_slugs(self) -> List[Dict[str, str]]:
        pages, _ = self._page_dao.list_pages(self._cfg.space_id, page_size=1000)
        return [{"slug": p.slug, "title": p.title, "type": p.page_type} for p in pages]

    # ==================================================================
    # INGEST
    # ==================================================================
    async def run_ingest(self, document_ids: Sequence[int]) -> Dict[str, Any]:
        if not document_ids:
            return {"mapped": 0, "updated": 0}
        logger.info(
            f"wiki ingest start: space={self._cfg.space_id} docs={list(document_ids)}"
        )

        # ---- MAP ----
        existing_slugs = self._existing_slugs()
        semaphore = asyncio.Semaphore(MAP_CONCURRENCY)
        map_results: List[Optional[Dict[str, Any]]] = []

        async def _map_one(document_id: int) -> Optional[Dict[str, Any]]:
            async with semaphore:
                try:
                    return await self._map_document(document_id, existing_slugs)
                except Exception as exc:
                    logger.error(f"wiki map failed for document {document_id}: {exc}")
                    return None

        map_results = await asyncio.gather(
            *[_map_one(document_id) for document_id in document_ids]
        )
        valid_maps = [m for m in map_results if m]
        if not valid_maps:
            logger.warning("wiki ingest: nothing mapped")
            return {"mapped": 0, "updated": 0}

        # Aggregate candidates across documents (per-slug merge)
        by_slug: Dict[str, Candidate] = {}
        summary_pages: Dict[int, Dict[str, Any]] = {}
        for m in valid_maps:
            for cand in m["candidates"]:
                slug = cand.slug
                if slug not in by_slug:
                    by_slug[slug] = cand
                else:
                    merged = by_slug[slug]
                    merged.chunk_ids.extend(
                        c for c in cand.chunk_ids if c not in merged.chunk_ids
                    )
                    merged.document_ids.extend(
                        d for d in cand.document_ids if d not in merged.document_ids
                    )
                    merged.aliases = list(dict.fromkeys(merged.aliases + cand.aliases))
                    if cand.description and len(cand.description) > len(
                        merged.description
                    ):
                        merged.description = cand.description
            for cand in m.get("new_candidates", []):
                if cand.slug not in by_slug:
                    by_slug[cand.slug] = cand
                else:
                    # citation pass re-discovered an existing candidate: merge
                    # its document/chunk evidence into the primary entry
                    merged = by_slug[cand.slug]
                    merged.document_ids.extend(
                        d for d in cand.document_ids if d not in merged.document_ids
                    )
                    merged.chunk_ids.extend(
                        c for c in cand.chunk_ids if c not in merged.chunk_ids
                    )
            for doc_id, payload in m["summary_pages"].items():
                summary_pages[doc_id] = payload

        # ---- DEDUP ----
        try:
            merged_candidates = await self._dedup_candidates(list(by_slug.values()))
        except Exception as exc:
            logger.warning(f"wiki dedup llm failed, keep as-is: {exc}")
            merged_candidates = list(by_slug.values())
        by_slug = {c.slug: c for c in merged_candidates}

        # ---- TAXONOMY ----
        try:
            category_map = await self._plan_taxonomy(merged_candidates)
        except Exception as exc:
            logger.warning(f"wiki taxonomy llm failed, flat layout: {exc}")
            category_map = {c.slug: [] for c in merged_candidates}

        # ---- REDUCE ----
        all_slugs = {p["slug"] for p in existing_slugs} | set(by_slug.keys())
        updated = await self._reduce_pages(
            by_slug, category_map, all_slugs, list(document_ids)
        )

        # summary pages (per-doc)
        for doc_id, payload in summary_pages.items():
            await self._write_summary_page(doc_id, payload, by_slug, all_slugs)

        logger.info(
            f"wiki ingest done: space={self._cfg.space_id} "
            f"pages_updated={updated} summaries={len(summary_pages)}"
        )
        return {"mapped": len(valid_maps), "updated": updated}

    # ------------------------------------------------------------------
    # MAP
    # ------------------------------------------------------------------
    async def _map_document(
        self, document_id: int, existing_slugs: List[Dict[str, str]]
    ) -> Optional[Dict[str, Any]]:
        doc = self._load_document(document_id)
        if doc is None:
            logger.warning(f"wiki map: document {document_id} missing, skip")
            return None
        text, chunks = self._load_document_content(document_id)
        if len(text.strip()) < 50:
            return None

        granularity = prompts.WIKI_GRANULARITY_GUIDANCE.get(
            self._cfg.granularity, prompts.WIKI_GRANULARITY_GUIDANCE["standard"]
        )
        existing_lines = (
            "\n".join(
                f"- {s['slug']} ({s['title']}, {s['type']})" for s in existing_slugs
            )
            or "(尚无页面)"
        )

        candidate_data = await self._llm_json(
            prompts.WIKI_CANDIDATE_SLUG_PROMPT.format(
                granularity=granularity,
                extraction_instructions=self._cfg.extraction_instructions
                or "无额外要求",
                existing_slugs=existing_lines,
                doc_name=doc.doc_name,
                content=text,
            )
        )
        candidates: List[Candidate] = []
        for item in candidate_data.get("candidates", []) or []:
            slug = build_slug(str(item.get("slug") or ""), str(item.get("name") or ""))
            if not slug.rsplit("/", 1)[-1]:
                continue
            candidates.append(
                Candidate(
                    name=str(item.get("name") or slug.rsplit("/", 1)[-1]),
                    slug=slug,
                    aliases=[a for a in item.get("aliases", []) or [] if a],
                    description=str(item.get("description") or ""),
                    document_ids=[document_id],
                )
            )

        # summary page generation (parallel with citation would be faster;
        # sequential keeps prompt budget predictable in P0)
        candidate_links = "\n".join(f"- [[{c.slug}|{c.name}]]" for c in candidates)
        summary_text = await self._llm_text(
            prompts.WIKI_DOC_SUMMARY_PROMPT.format(
                candidate_links=candidate_links or "（无）",
                doc_name=doc.doc_name,
                content=text,
            )
        )
        summary, summary_content = parse_summary_line(summary_text)
        summary_pages = {
            document_id: {
                "title": f"{doc.doc_name} - Summary",
                "summary": summary,
                "content": summary_content,
            }
        }

        # chunk citation: map candidates -> supporting chunk row ids
        all_candidates = candidates
        cited: Dict[str, List[int]] = {}
        new_candidates: List[Candidate] = []
        label_to_row = {
            f"c{idx + 1}": row["chunk_id"] for idx, row in enumerate(chunks)
        }

        batches: List[List[Dict[str, Any]]] = []
        current: List[Dict[str, Any]] = []
        current_chars = 0
        for idx, row in enumerate(chunks):
            entry = {"label": f"c{idx + 1}", "content": row["content"]}
            if current and current_chars + len(row["content"]) > CITATION_BATCH_CHARS:
                batches.append(current)
                current, current_chars = [], 0
            current.append(entry)
            current_chars += len(row["content"])
        if current:
            batches.append(current)

        if all_candidates and batches:
            for batch in batches:
                batch_text = "\n\n".join(
                    f"[{entry['label']}]\n{entry['content']}" for entry in batch
                )
                try:
                    cited_data = await self._llm_json(
                        prompts.WIKI_CHUNK_CITATION_PROMPT.format(
                            candidates_json=json.dumps(
                                [c.to_prompt_dict() for c in all_candidates],
                                ensure_ascii=False,
                            ),
                            chunks_text=batch_text,
                        )
                    )
                except Exception as exc:
                    logger.warning(f"wiki citation batch failed: {exc}")
                    continue
                for item in cited_data.get("citations", []) or []:
                    slug = str(item.get("slug") or "")
                    row_ids = [
                        label_to_row[label]
                        for label in item.get("chunk_ids", []) or []
                        if label in label_to_row
                    ]
                    if slug in cited:
                        cited[slug].extend(r for r in row_ids if r not in cited[slug])
                    else:
                        cited[slug] = row_ids
                for item in cited_data.get("new_slugs", []) or []:
                    slug = build_slug(
                        str(item.get("slug") or ""), str(item.get("name") or "")
                    )
                    if slug and slug not in by_slug_names(all_candidates):
                        new_candidates.append(
                            Candidate(
                                name=str(item.get("name") or slug),
                                slug=slug,
                                aliases=[a for a in item.get("aliases", []) or [] if a],
                                description=str(item.get("description") or ""),
                                document_ids=[document_id],
                            )
                        )

        for cand in candidates:
            cand.chunk_ids = cited.get(cand.slug, [])
        return {
            "candidates": candidates,
            "new_candidates": new_candidates,
            "summary_pages": summary_pages,
        }

    # ------------------------------------------------------------------
    # DEDUP
    # ------------------------------------------------------------------
    async def _dedup_candidates(self, candidates: List[Candidate]) -> List[Candidate]:
        """Surface-similarity prefilter then one LLM merge pass."""
        if len(candidates) < 2:
            return candidates

        def _sig(c: Candidate) -> str:
            return f"{c.name} {c.description}".strip()

        groups: List[List[Candidate]] = []
        used: Set[int] = set()
        for i, cand in enumerate(candidates):
            if i in used:
                continue
            group = [cand]
            for j in range(i + 1, len(candidates)):
                if j in used:
                    continue
                ratio = difflib.SequenceMatcher(
                    None, _sig(cand), _sig(candidates[j])
                ).ratio()
                if ratio >= 0.45:
                    group.append(candidates[j])
                    used.add(j)
            groups.append(group)
            used.add(i)

        # Only groups with more than one member need LLM arbitration.
        to_confirm = [g for g in groups if len(g) > 1]
        if not to_confirm:
            return candidates

        confirmed = await self._llm_json(
            prompts.WIKI_DEDUP_PROMPT.format(
                candidates_json=json.dumps(
                    [
                        {"group": idx + 1, "items": [c.to_prompt_dict() for c in g]}
                        for idx, g in enumerate(to_confirm)
                    ],
                    ensure_ascii=False,
                )
            )
        )
        merge_keep: Dict[str, str] = {}
        raw = confirmed.get("candidates", []) if isinstance(confirmed, dict) else []
        for item in raw:
            slugs = [
                self._norm_slug(x.get("slug"))
                for x in item.get("merged_from_slugs", []) or []
            ]
            keep = self._norm_slug(item.get("slug")) or self._norm_slug(
                item.get("name")
            )
            if keep:
                for s in slugs:
                    if s and s != keep:
                        merge_keep[s] = keep
        return self._apply_slug_merges(candidates, merge_keep, raw)

    @staticmethod
    def _norm_slug(value: Any) -> str:
        return str(value or "").strip().lower()

    def _apply_slug_merges(
        self,
        candidates: List[Candidate],
        merge_keep: Dict[str, str],
        raw_items: List[Dict[str, Any]],
    ) -> List[Candidate]:
        """Fold duplicate candidates into their kept slug."""
        raw_by_keep = {
            self._norm_slug(r.get("slug")): r for r in raw_items if r.get("slug")
        }
        result: Dict[str, Candidate] = {}
        for cand in candidates:
            target = merge_keep.get(cand.slug, cand.slug)
            alias_target = None
            for kept, raw in raw_by_keep.items():
                if cand.slug in [self._norm_slug(s) for s in raw.get("aliases", [])]:
                    alias_target = kept
                    break
            final_slug = alias_target or target or cand.slug
            if final_slug in result:
                kept = result[final_slug]
                kept.aliases = list(
                    dict.fromkeys(kept.aliases + cand.aliases + [cand.name])
                )
                kept.chunk_ids.extend(
                    c for c in cand.chunk_ids if c not in kept.chunk_ids
                )
            else:
                if final_slug != cand.slug:
                    cand.slug = final_slug
                if cand.name not in cand.aliases:
                    cand.aliases = list(dict.fromkeys(cand.aliases))
                result[cand.slug] = cand
        return list(result.values())

    # ------------------------------------------------------------------
    # TAXONOMY
    # ------------------------------------------------------------------
    async def _plan_taxonomy(self, candidates: List[Candidate]) -> Dict[str, List[str]]:
        pages, _ = self._page_dao.list_pages(self._cfg.space_id, page_size=1000)
        existing_paths: Set[str] = set()
        for p in pages:
            path = json.loads(p.category_path) if p.category_path else []
            if path:
                existing_paths.add("/".join(str(x) for x in path))
        assignments = await self._llm_json(
            prompts.WIKI_TAXONOMY_PROMPT.format(
                existing_tree="\n".join(f"- {p}" for p in sorted(existing_paths))
                or "（尚无目录）",
                candidates_json=json.dumps(
                    [c.to_prompt_dict() for c in candidates], ensure_ascii=False
                ),
            )
        )
        category_map: Dict[str, List[str]] = {}
        if isinstance(assignments, dict):
            for item in assignments.get("assignments", []) or []:
                slug = self._norm_slug(item.get("slug"))
                path = [
                    str(x).strip()
                    for x in item.get("category_path", []) or []
                    if str(x).strip()
                ]
                if slug:
                    category_map[slug] = path[:2]
        return category_map

    # ------------------------------------------------------------------
    # REDUCE
    # ------------------------------------------------------------------
    async def _reduce_pages(
        self,
        by_slug: Dict[str, Candidate],
        category_map: Dict[str, List[str]],
        all_slugs: Set[str],
        batch_document_ids: List[int],
    ) -> int:
        semaphore = asyncio.Semaphore(REDUCE_CONCURRENCY)
        updated = 0

        async def _reduce_one(agg: Candidate) -> None:
            nonlocal updated
            async with semaphore:
                try:
                    await self._reduce_single_page(
                        agg, category_map.get(agg.slug, []), all_slugs
                    )
                    updated += 1
                except Exception as exc:
                    logger.error(f"wiki reduce failed for {agg.slug}: {exc}")

        await asyncio.gather(*[_reduce_one(agg) for agg in by_slug.values()])
        return updated

    async def _reduce_single_page(
        self,
        agg: Candidate,
        category_path: List[str],
        all_slugs: Set[str],
        deleted_documents: Optional[str] = None,
    ) -> None:
        space_id = self._cfg.space_id
        page = self._page_dao.get_page_by_slug(space_id, agg.slug)
        self._ensure_writable_slug_set(agg, all_slugs)

        # build materials to feed the rewriter
        materials = []
        chunks_by_id = self._load_chunks(agg.chunk_ids)
        doc_names = {
            d["document_id"]: d["doc_name"]
            for d in self._load_doc_names(agg.document_ids)
        }
        for document_id in agg.document_ids:
            cited_ids = [cid for cid in agg.chunk_ids if cid in chunks_by_id]
            excerpts = [
                chunks_by_id[cid][:EXCERPT_CHARS]
                for cid in cited_ids[:MAX_EXCERPT_PER_DOC]
            ]
            if not excerpts:
                # citation pass didn't ground this document; fall back to the
                # document body so the rewriter still has real material
                doc_text, _chunks = self._load_document_content(document_id)
                if doc_text:
                    excerpts.append(doc_text[:EXCERPT_CHARS])
            materials.append(
                {
                    "document_id": document_id,
                    "doc_name": doc_names.get(document_id, f"document#{document_id}"),
                    "description": agg.description,
                    "excerpts": excerpts,
                }
            )

        llm_prompt = prompts.WIKI_PAGE_MODIFY_PROMPT.format(
            slug=agg.slug,
            page_type=agg.slug.rsplit("/", 1)[0].capitalize(),
            existing_content=(page.content if page else "(新页面，无既有内容)")[:8000],
            valid_links="\n".join(sorted(all_slugs - {agg.slug})) or "（无）",
            materials=json.dumps(materials, ensure_ascii=False),
            deleted_documents=deleted_documents or "（无）",
            content_instructions=self._cfg.content_instructions or "无额外要求",
        )
        llm_out = await self._llm_text(llm_prompt)
        summary_out, content = parse_summary_line(llm_out)
        summary_out = summary_out or agg.description
        source_ref = [
            {"document_id": d_id, "doc_name": doc_names.get(d_id, f"document#{d_id}")}
            for d_id in agg.document_ids
        ]

        aliases = list(dict.fromkeys([agg.name, *agg.aliases]))
        depth = len(category_path)
        common = dict(
            title=agg.name,
            summary=summary_out,
            content=content,
            aliases=aliases,
            category_path=category_path,
            depth=depth,
            out_links=parse_out_links(content),
        )
        if page is None:
            self._page_dao.create_page(
                dict(
                    space_id=space_id,
                    slug=agg.slug,
                    page_type=agg.slug.rsplit("/", 1)[0]
                    if "/" in agg.slug
                    else "concept",
                    source_refs=source_ref,
                    chunk_refs=agg.chunk_ids,
                    **common,
                )
            )
        else:
            old_source = json.loads(page.source_refs) if page.source_refs else []
            merged_source = {s["document_id"]: s for s in old_source}
            for ref in source_ref:
                merged_source[ref["document_id"]] = ref
            self._page_dao.update_with_revision(
                space_id,
                agg.slug,
                dict(
                    common,
                    source_refs=list(merged_source.values()),
                    chunk_refs=list(
                        dict.fromkeys(
                            (json.loads(page.chunk_refs) if page.chunk_refs else [])
                            + agg.chunk_ids
                        )
                    ),
                ),
                edit_source="pipeline",
            )
        self._apply_link_diff(space_id, agg.slug, page, common["out_links"])

    @staticmethod
    def _ensure_writable_slug_set(agg: Candidate, all_slugs: Set[str]) -> None:
        all_slugs.add(agg.slug)

    def _load_chunks(self, chunk_row_ids: List[int]) -> Dict[int, str]:
        if not chunk_row_ids:
            return {}
        from dbgpt_serve.rag.models.chunk_db import (
            DocumentChunkDao,
            DocumentChunkEntity,
        )

        dao = DocumentChunkDao()
        session = dao.get_raw_session()
        try:
            rows = (
                session.query(DocumentChunkEntity)
                .filter(DocumentChunkEntity.id.in_(chunk_row_ids))
                .all()
            )
            return {r.id: (r.content or "") for r in rows}
        finally:
            session.close()

    def _load_doc_names(self, document_ids: List[int]) -> List[Dict[str, Any]]:
        if not document_ids:
            return []
        from dbgpt_serve.rag.models.document_db import (
            KnowledgeDocumentDao,
            KnowledgeDocumentEntity,
        )

        dao = KnowledgeDocumentDao()
        session = dao.get_raw_session()
        try:
            rows = (
                session.query(KnowledgeDocumentEntity)
                .filter(KnowledgeDocumentEntity.id.in_(document_ids))
                .all()
            )
            return [{"document_id": r.id, "doc_name": r.doc_name} for r in rows]
        finally:
            session.close()

    def _apply_link_diff(
        self, space_id: int, slug: str, old_page: Any, new_out_links: List[str]
    ) -> None:
        old_out = (
            json.loads(old_page.out_links) if old_page and old_page.out_links else []
        )
        added, removed = compute_in_link_diff(old_out, new_out_links)
        for target in added:
            target_page = self._page_dao.get_page_by_slug(space_id, target)
            if target_page is not None:
                in_links = (
                    json.loads(target_page.in_links) if target_page.in_links else []
                )
                if slug not in in_links:
                    in_links.append(slug)
                    self._page_dao.update_with_revision(
                        space_id,
                        target,
                        {"in_links": in_links},
                        edit_source="pipeline",
                        touch_source=False,
                    )
        for target in removed:
            target_page = self._page_dao.get_page_by_slug(space_id, target)
            if target_page is not None:
                in_links = (
                    json.loads(target_page.in_links) if target_page.in_links else []
                )
                if slug in in_links:
                    in_links.remove(slug)
                    self._page_dao.update_with_revision(
                        space_id,
                        target,
                        {"in_links": in_links},
                        edit_source="pipeline",
                        touch_source=False,
                    )

    # ------------------------------------------------------------------
    # summary page
    # ------------------------------------------------------------------
    async def _write_summary_page(
        self,
        document_id: int,
        payload: Dict[str, Any],
        by_slug: Dict[str, Candidate],
        all_slugs: Set[str],
    ) -> None:
        space_id = self._cfg.space_id
        slug = f"summary/doc-{document_id}"
        # Only link slugs that actually exist after this batch
        valid_links = set(all_slugs)
        content = strip_dead_links(payload.get("content") or "", valid_links)
        doc = self._load_document(document_id)
        source_ref = (
            [{"document_id": document_id, "doc_name": doc.doc_name}]
            if doc
            else [{"document_id": document_id, "doc_name": f"document#{document_id}"}]
        )
        page = self._page_dao.get_page_by_slug(space_id, slug)
        common = dict(
            title=payload.get("title") or f"document#{document_id}",
            summary=payload.get("summary"),
            content=content,
            aliases=[],
            category_path=[],
            depth=0,
            out_links=parse_out_links(content),
        )
        if page is None:
            self._page_dao.create_page(
                dict(
                    space_id=space_id,
                    slug=slug,
                    page_type="summary",
                    source_refs=source_ref,
                    chunk_refs=[],
                    **common,
                )
            )
        else:
            self._page_dao.update_with_revision(
                space_id,
                slug,
                dict(common, source_refs=source_ref),
                edit_source="pipeline",
            )
        self._apply_link_diff(space_id, slug, page, common["out_links"])

    # ==================================================================
    # FINALIZE
    # ==================================================================
    async def run_finalize(self) -> Dict[str, Any]:
        space_id = self._cfg.space_id
        all_pages, _total = self._page_dao.list_pages(space_id, page_size=10000)
        if not all_pages:
            return {"pages": 0}
        all_slugs = {p.slug for p in all_pages}

        # 1. dead-link cleanup + rebuild in/out links globally
        in_map: Dict[str, List[str]] = {p.slug: [] for p in all_pages}
        for page in all_pages:
            out_links = parse_out_links(page.content or "")
            out_links = [s for s in out_links if s in all_slugs]
            clean = strip_dead_links(page.content or "", all_slugs)
            needs_content_update = clean != (page.content or "")
            needs_links_update = (
                json.loads(page.out_links) if page.out_links else []
            ) != out_links
            if needs_content_update or needs_links_update:
                updates: Dict[str, Any] = {"out_links": out_links}
                if needs_content_update:
                    updates["content"] = clean
                self._page_dao.update_with_revision(
                    space_id,
                    page.slug,
                    updates,
                    edit_source="pipeline",
                )
            for target in out_links:
                if target in in_map:
                    in_map[target].append(page.slug)

        # apply rebuilt in_links (link-cache maintenance: no source stamp)
        for page in all_pages:
            in_links = sorted(set(in_map.get(page.slug, [])))
            current = json.loads(page.in_links) if page.in_links else []
            if current != in_links:
                self._page_dao.update_with_revision(
                    space_id,
                    page.slug,
                    {"in_links": in_links},
                    edit_source="pipeline",
                    touch_source=False,
                )

        # 2. cross-link injection (mention scan, capped)
        await self._inject_cross_links(all_pages, all_slugs)

        # 3. index page
        await self._rebuild_index_page(all_pages)

        # 4. wiki chunk sync (P0 retrieval integration, best effort)
        self._sync_wiki_chunks(all_pages)

        return {"pages": len(all_pages)}

    async def _inject_cross_links(self, all_pages: Any, all_slugs: Set[str]) -> None:
        """Mention-scan cross-link injection (P0 heuristic).

        For each page, find other pages whose plain text mentions this
        page's title/aliases without linking it, and link the first
        occurrence. Capped per run; skips the index page as a target.
        """
        space_id = self._cfg.space_id
        injected = 0
        for page in all_pages:
            if injected >= 50:
                break
            if page.page_type == "index":
                continue
            tokens = [page.title] + (json.loads(page.aliases) if page.aliases else [])
            tokens = [t for t in tokens if t and len(t) >= 2]
            if not tokens:
                continue
            for other in all_pages:
                if injected >= 50 or other.slug == page.slug:
                    continue
                if other.slug in (json.loads(page.out_links) if page.out_links else []):
                    continue
                content = other.content or ""
                for token in tokens:
                    if content.count(token) == 0 or f"[[{page.slug}" in content:
                        continue
                    # do not hijack the other page's own identity words
                    if token in (
                        [other.title or ""]
                        + (json.loads(other.aliases) if other.aliases else [])
                    ):
                        continue
                    new_content = content.replace(token, f"[[{page.slug}|{token}]]", 1)
                    try:
                        self._page_dao.update_with_revision(
                            space_id,
                            other.slug,
                            {"content": new_content},
                            edit_source="pipeline",
                        )
                        injected += 1
                    except WikiVersionConflictError as exc:
                        logger.warning(f"cross-link skip {other.slug}: {exc}")
                    break
        if injected:
            logger.info(f"wiki finalize: injected {injected} cross link(s)")

    async def _rebuild_index_page(self, all_pages: Any) -> None:
        space_id = self._cfg.space_id
        content_pages = [p for p in all_pages if p.page_type != "index"]
        tree: Dict[Tuple[str, ...], List[Any]] = {}
        for p in sorted(content_pages, key=lambda x: x.title or ""):
            try:
                path = tuple(json.loads(p.category_path)) if p.category_path else ()
            except (TypeError, ValueError):
                path = ()
            tree.setdefault(path, []).append(p)

        def _tree_markdown() -> str:
            lines: List[str] = []
            for path in sorted(tree.keys()):
                header = " / ".join(path) if path else "(根目录)"
                lines.append(f"## {header}")
                for p in tree[path]:
                    summary = (p.summary or "").strip()
                    lines.append(f"- [[{p.slug}|{p.title}]] {summary[:60]}")
                lines.append("")
            return "\n".join(lines)

        tree_md = _tree_markdown()
        page = self._page_dao.get_page_by_slug(space_id, INDEX_SLUG)
        if page is None:
            llm_out = await self._llm_text(
                prompts.WIKI_INDEX_INTRO_PROMPT.format(tree_markdown=tree_md)
            )
            summary, content = parse_summary_line(llm_out)
            self._page_dao.create_page(
                dict(
                    space_id=space_id,
                    slug=INDEX_SLUG,
                    title="知识库索引",
                    page_type="index",
                    summary=summary or f"共 {len(content_pages)} 个知识页面",
                    content=content,
                    aliases=[],
                    category_path=[],
                    depth=0,
                    out_links=parse_out_links(content),
                    source_refs=[],
                    chunk_refs=[],
                )
            )
        else:
            llm_out = await self._llm_text(
                prompts.WIKI_INDEX_INTRO_UPDATE_PROMPT.format(
                    existing_intro=page.content or "", tree_markdown=tree_md
                )
            )
            summary, content = parse_summary_line(llm_out)
            self._page_dao.update_with_revision(
                space_id,
                INDEX_SLUG,
                {
                    "summary": summary or page.summary,
                    "content": content,
                    "out_links": parse_out_links(content),
                },
                edit_source="pipeline",
            )

    def _sync_wiki_chunks(self, all_pages: Any) -> None:
        """Best-effort wiki chunk retrieval sync (see chunk_sync.py)."""
        try:
            from dbgpt_serve.rag.service.wiki.chunk_sync import sync_space_wiki_chunks

            sync_space_wiki_chunks(self._system_app, self._space, all_pages)
        except Exception as exc:
            logger.warning(f"wiki chunk sync skipped: {exc}")

    # ==================================================================
    # RECONCILE (document deletion)
    # ==================================================================
    async def run_reconcile(self, deleted_document_id: int) -> Dict[str, Any]:
        space_id = self._cfg.space_id
        affected = self._page_dao.list_pages_by_source_document(
            space_id, str(deleted_document_id)
        )
        if not affected:
            return {"affected": 0}
        doc_name = f"document#{deleted_document_id}"
        doc = self._load_document(deleted_document_id)
        if doc is not None:
            doc_name = doc.doc_name
        deleted_note = f"- {doc_name} (id={deleted_document_id})"

        all_pages, _t = self._page_dao.list_pages(space_id, page_size=10000)
        all_slugs = {p.slug for p in all_pages}

        for page in affected:
            old_source = json.loads(page.source_refs) if page.source_refs else []
            remaining = [
                s
                for s in old_source
                if str(s.get("document_id")) != str(deleted_document_id)
            ]
            if not remaining and page.page_type == "summary":
                # orphan summary page: remove entirely
                self._page_dao.delete_page(space_id, page.slug)
                continue
            # rewrite the page removing traces of the deleted document
            agg = Candidate(
                name=page.title or page.slug,
                slug=page.slug,
                aliases=json.loads(page.aliases) if page.aliases else [],
                description=page.summary or "",
                document_ids=[
                    s.get("document_id") for s in remaining if s.get("document_id")
                ],
            )
            try:
                await self._reduce_single_page(
                    agg,
                    json.loads(page.category_path) if page.category_path else [],
                    all_slugs,
                    deleted_documents=deleted_note,
                )
            except Exception as exc:
                logger.error(f"wiki reconcile rewrite failed {page.slug}: {exc}")
                # at minimum drop the deleted source ref
                self._page_dao.update_with_revision(
                    space_id,
                    page.slug,
                    {"source_refs": remaining},
                    edit_source="pipeline",
                )
        return {"affected": len(affected)}


def by_slug_names(candidates: List[Candidate]) -> Set[str]:
    return {c.slug for c in candidates}
