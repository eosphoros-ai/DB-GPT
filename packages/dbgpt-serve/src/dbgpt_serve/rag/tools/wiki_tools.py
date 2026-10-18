"""Wiki consumption tools for agents.

Read tools (any agent, mirror of WeKnora's wiki_search/read_page/index):
- kb_wiki_search    — full-text-ish search over wiki pages
- kb_wiki_read_page — page content with char budget
- kb_wiki_index     — grouped catalog overview

Write tools (for knowledge-base chat / maintainer agents, WeKnora
fixer-style): every write goes through the revision DAO with
``edit_source="agent"`` so history separates agent edits and stays
revertable — same provenance contract as pipeline/user edits.

All tools are **wiki-gated**: they resolve the space and refuse politely
when the space doesn't exist or the Wiki index method is not enabled.
"""

import json
import logging
from typing import Annotated, Any, Tuple

from dbgpt.agent.resource.tool.base import tool

logger = logging.getLogger(__name__)

READ_BUDGET_CHARS = 8000
PAGE_BODY_CHARS = 9000

_TYPE_LABELS = {
    "summary": "摘要",
    "entity": "实体",
    "concept": "概念",
    "synthesis": "综合",
    "comparison": "对比",
    "index": "索引",
}


def _resolve_space(space: Any) -> Tuple[Any, Any, str]:
    """Resolve a space by id or name; return (space, wiki_cfg, gate_msg).

    ``gate_msg`` is non-empty when the wiki consumption is not available —
    callers return it verbatim to the agent instead of raising, so the
    model can de-grade gracefully.
    """
    from ..models.models import KnowledgeSpaceDao, KnowledgeSpaceEntity
    from ..service.wiki.config import WikiSpaceConfig

    dao = KnowledgeSpaceDao()
    key = str(space).strip()
    if key.isdigit():
        rows = dao.get_knowledge_space_by_ids([int(key)])
    else:
        rows = dao.get_knowledge_space(KnowledgeSpaceEntity(name=key))
    if not rows:
        return None, None, f"knowledge space '{space}' does not exist"
    cfg = WikiSpaceConfig.from_space(rows[0])
    if not cfg.enabled:
        return (
            rows[0],
            cfg,
            f"space '{rows[0].name}' has no Wiki index method enabled; "
            "enable Wiki for the space first",
        )
    return rows[0], cfg, ""


def _page_dao():
    from ..models.wiki_db import KnowledgeWikiPageDao

    return KnowledgeWikiPageDao()


# --------------------------------------------------------------------------
# Read tools
# --------------------------------------------------------------------------
@tool(
    "kb_wiki_search",
    description=(
        "Search the knowledge space's LLM-Wiki pages (titles, aliases, "
        "summaries, content). Use when the space has a wiki and you need "
        "the curated/synthesized view of its documents."
    ),
)
async def kb_wiki_search(
    knowledge_id: Annotated[str, "Knowledge space ID or name"],
    query: Annotated[str, "Search keywords (title/alias/summary/content)"],
    top_k: Annotated[int, "Max results (1-10)"] = 5,
) -> str:
    top_k = max(1, min(int(top_k or 5), 10))
    try:
        space, cfg, gate = _resolve_space(knowledge_id)
    except Exception as e:  # noqa: BLE001
        return f"wiki search unavailable: {e}"
    if gate:
        return gate
    page_dao = _page_dao()
    rows, _total = page_dao.list_pages(space.id, query=query, page_size=top_k)
    if not rows:
        return f"No wiki pages match '{query}' in '{space.name}'."
    lines = [f"Wiki pages in '{space.name}' matching '{query}':"]
    budget = READ_BUDGET_CHARS
    for r in rows:
        label = _TYPE_LABELS.get(r.page_type, r.page_type)
        summary = (r.summary or "").strip()[:200]
        entry = (
            f"\n---\n### [{label}] {r.title} (slug: {r.slug}, v{r.version})\n{summary}"
        )
        if len(entry) > budget:
            lines.append("\n... budget exceeded, results truncated.")
            break
        budget -= len(entry)
        lines.append(entry)
    return "\n".join(lines)


@tool(
    "kb_wiki_read_page",
    description=(
        "Read one page of the knowledge space's LLM-Wiki by slug (from "
        "kb_wiki_search / kb_wiki_index results). Use slug 'index' for "
        "the auto-generated catalog page."
    ),
)
async def kb_wiki_read_page(
    knowledge_id: Annotated[str, "Knowledge space ID or name"],
    slug: Annotated[str, "Wiki page slug, e.g. 'entity/dbgpt' or 'index'"],
) -> str:
    try:
        space, cfg, gate = _resolve_space(knowledge_id)
    except Exception as e:  # noqa: BLE001
        return f"wiki read unavailable: {e}"
    if gate:
        return gate
    page = _page_dao().get_page_by_slug(space.id, slug)
    if page is None:
        return f"Wiki page '{slug}' not found in '{space.name}'."
    in_links = json.loads(page.in_links) if page.in_links else []
    content = (page.content or "").strip()[:PAGE_BODY_CHARS]
    truncated = (
        " \n... (content truncated)"
        if len(page.content or "") > PAGE_BODY_CHARS
        else ""
    )
    head = (
        f"[{_TYPE_LABELS.get(page.page_type, page.page_type)}] {page.title} "
        f"(slug: {page.slug}, v{page.version})\nSummary: {page.summary or ''}\n"
    )
    body = f"\n{content}{truncated}"
    tail_lines = []
    if in_links:
        tail_lines.append("Linked from: " + ", ".join(in_links[:8]))
    if page.source_refs:
        try:
            refs = json.loads(page.source_refs)
            names = [r.get("doc_name", "") for r in refs][:5]
            if names:
                tail_lines.append("Source docs: " + ", ".join(n for n in names if n))
        except (TypeError, ValueError):
            pass
    return head + body + ("\n\n" + "\n".join(tail_lines) if tail_lines else "")


@tool(
    "kb_wiki_index",
    description=(
        "List the knowledge space's LLM-Wiki catalog: folders and pages "
        "grouped two levels deep with one-line summaries. Call this first "
        "when exploring a wiki-enabled space."
    ),
)
async def kb_wiki_index(
    knowledge_id: Annotated[str, "Knowledge space ID or name"],
) -> str:
    try:
        space, cfg, gate = _resolve_space(knowledge_id)
    except Exception as e:  # noqa: BLE001
        return f"wiki index unavailable: {e}"
    if gate:
        return gate
    pages, _t = _page_dao().list_pages(space.id, page_size=1000)
    if not pages:
        return f"Space '{space.name}' has no wiki pages yet."
    groups: dict = {}
    for p in pages:
        try:
            path = tuple(json.loads(p.category_path)) if p.category_path else ()
        except (TypeError, ValueError):
            path = ()
        groups.setdefault(path, []).append(p)
    lines = [f"Wiki catalog of '{space.name}' ({len(pages)} pages):"]
    budget = READ_BUDGET_CHARS
    for path in sorted(groups.keys(), key=lambda t: (len(t), t)):
        header = " > ".join(path) if path else "(root)"
        block = [f"\n## {header}"]
        for p in groups[path]:
            summary = (p.summary or "").strip()[:80]
            block.append(f"- {p.title} (slug: {p.slug}) {summary}")
        text = "\n".join(block)
        if len(text) > budget:
            lines.append("\n... budget exceeded, catalogs truncated.")
            break
        budget -= len(text)
        lines.append(text)
    return "\n".join(lines)


# --------------------------------------------------------------------------
# Write tools (KB chat / maintainer agents) — provenance: edit_source=agent
# --------------------------------------------------------------------------
@tool(
    "kb_wiki_write_page",
    description=(
        "Create or fully rewrite one wiki page of a wiki-enabled knowledge "
        "space. Content is Markdown; link to other pages with "
        "[[slug|display]]. The write is recorded as an agent edit and can "
        "be reverted from revision history. Prefer smaller, factual pages."
    ),
)
async def kb_wiki_write_page(
    knowledge_id: Annotated[str, "Knowledge space ID or name"],
    slug: Annotated[str, "Page slug like 'concept/xx' (created if absent)"],
    title: Annotated[str, "Page title"],
    content: Annotated[str, "Full Markdown content of the page"],
    summary: Annotated[str, "One-line summary shown in lists"] = "",
) -> str:
    from ..service.wiki.link_service import build_slug, parse_out_links

    try:
        space, cfg, gate = _resolve_space(knowledge_id)
    except Exception as e:  # noqa: BLE001
        logger.exception("wiki write resolve failed")
        return f"wiki write unavailable: {e}"
    if gate:
        return gate
    norm = build_slug(slug or "", title)
    page_dao = _page_dao()
    existing = page_dao.get_page_by_slug(space.id, norm)
    out_links = parse_out_links(content)
    if existing is None:
        page = page_dao.create_page(
            {
                "space_id": space.id,
                "slug": norm,
                "title": title,
                "page_type": norm.rsplit("/", 1)[0] if "/" in norm else "concept",
                "content": content,
                "summary": summary or title,
                "last_edit_source": "agent",
            }
        )
        action = "created"
        version = 1
    else:
        page = page_dao.update_with_revision(
            space.id,
            norm,
            {
                "title": title,
                "content": content,
                "summary": summary or existing.summary,
                "out_links": out_links,
            },
            edit_source="agent",
        )
        action = "updated"
        version = page.version
    return (
        f"Wiki page {action}: {title} (slug: {norm}, version v{version}). "
        "The edit is recorded as an agent edit in revision history."
    )


@tool(
    "kb_wiki_replace_text",
    description=(
        "Precisely replace the first occurrence of old_text with new_text "
        "inside one wiki page (safer than rewriting the whole page). "
        "Recorded as an agent edit; pass the page's current version when "
        "you know it to avoid concurrent overwrites."
    ),
)
async def kb_wiki_replace_text(
    knowledge_id: Annotated[str, "Knowledge space ID or name"],
    slug: Annotated[str, "Existing page slug"],
    old_text: Annotated[str, "Exact text to replace (first occurrence)"],
    new_text: Annotated[str, "Replacement text"],
    version: Annotated[int, "Current page version (optimistic lock)"] = 0,
) -> str:
    from ..service.wiki.link_service import parse_out_links

    try:
        space, cfg, gate = _resolve_space(knowledge_id)
    except Exception as e:  # noqa: BLE001
        return f"wiki write unavailable: {e}"
    if gate:
        return gate
    page = _page_dao().get_page_by_slug(space.id, slug)
    if page is None:
        return f"Wiki page '{slug}' not found in '{space.name}'."
    content = page.content or ""
    if content.count(old_text) == 0:
        return (
            f"old_text not found in '{slug}'. Read kb_wiki_read_page first "
            "and pass an exact snippet."
        )
    new_content = content.replace(old_text, new_text, 1)
    from ..models.wiki_db import WikiVersionConflictError

    updates: dict = {"content": new_content, "out_links": parse_out_links(new_content)}
    try:
        updated = _page_dao().update_with_revision(
            space.id,
            slug,
            updates,
            edit_source="agent",
            expected_version=int(version) if version else None,
        )
    except WikiVersionConflictError as exc:
        return (
            f"version conflict on '{slug}': server is at v{exc.current_version}; "
            "re-read the page and retry with the new version."
        )
    return f"Replaced 1 occurrence in '{slug}' (now v{updated.version})."
