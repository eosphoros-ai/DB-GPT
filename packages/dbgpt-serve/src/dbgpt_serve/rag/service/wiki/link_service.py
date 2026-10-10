"""Wiki link parsing / maintenance utilities.

Ports WeKnora's ``parseOutLinks`` / ``stripDeadWikiLinks`` /
cross-link helpers. Wiki link syntax: ``[[slug|display]]`` (display part
optional).
"""

from __future__ import annotations

import re
from typing import Iterable, List, Optional, Set, Tuple

WIKI_LINK_PATTERN = re.compile(r"\[\[([^\[\]|#]+)(?:\|([^\[\]|#]*))?\]\]")


def parse_out_links(content: str) -> List[str]:
    """Extract the ordered, de-duplicated slug list from ``[[slug|...]]``."""
    if not content:
        return []
    seen: List[str] = []
    for match in WIKI_LINK_PATTERN.finditer(content):
        slug = match.group(1).strip()
        if slug and slug not in seen:
            seen.append(slug)
    return seen


def strip_dead_links(content: str, valid_slugs: Set[str]) -> str:
    """Rewrite links pointing to nonexistent slugs back into plain text."""
    if not content:
        return content

    def _replace(match: "re.Match[str]") -> str:
        slug = match.group(1).strip()
        display = (match.group(2) or "").strip() or slug.rsplit("/", 1)[-1]
        if slug in valid_slugs:
            return match.group(0)
        return display

    return WIKI_LINK_PATTERN.sub(_replace, content)


def valid_link_allow_list(
    all_slugs: List[str], extra_slugs: Optional[List[str]] = None
) -> Set[str]:
    valid = set(all_slugs)
    if extra_slugs:
        valid.update(s for s in extra_slugs if s)
    return valid


def parse_summary_line(text: str) -> Tuple[Optional[str], str]:
    """Split a pipeline LLM output into (summary, content).

    The contract is a first line ``SUMMARY: ...``; when missing the whole
    text is treated as content and the summary stays untouched.
    """
    if not text:
        return None, ""
    lines = text.lstrip().splitlines()
    if lines and lines[0].strip().upper().startswith("SUMMARY:"):
        summary = lines[0].split(":", 1)[1].strip()
        content = "\n".join(lines[1:]).lstrip("\n")
        return summary, content
    return None, text


def find_cross_link_candidates(
    page_title: str,
    page_aliases: List[str],
    page_linkeds: Set[str],
    others: Iterable[Tuple[str, str, List[str]]],
    max_candidates: int = 3,
) -> List[str]:
    """Find (slug, content of others) mention candidates for cross-linking.

    Returns slugs of pages whose de-linked plain text mentions this page's
    title / aliases but does not link it yet.
    """
    tokens = [t for t in [page_title, *page_aliases] if t and len(t) >= 2]
    if not tokens:
        return []
    candidates: List[str] = []
    for slug, content, in_links in others:
        if len(candidates) >= max_candidates:
            break
        if slug in page_linkeds:
            continue
        if slug in candidates:
            continue
        if any(token in content for token in tokens):
            candidates.append(slug)
    return candidates


def compute_in_link_diff(
    old_out_links: List[str], new_out_links: List[str]
) -> Tuple[List[str], List[str]]:
    """Return (added_targets, removed_targets) between two out-link states."""
    old, new = set(old_out_links), set(new_out_links)
    return sorted(new - old), sorted(old - new)


def category_display_path(category_path: List[str]) -> str:
    return "/".join(category_path) if category_path else "/"


def build_slug(hint_slug: str, name: str = "") -> str:
    """Build a page slug, preferring the explicit ``hint_slug``.

    All call sites pass (desired_slug, source_title): an explicit slug
    round-trips with only structural cleanup — multi-segment values like
    ``concept/annual-leave`` must survive unchanged (regression fix: the
    old signature treated the title as the hint and silently derived
    CJK-only slugs from it).

    When no slug is provided, derive from ``name`` (CJK/ascii letters,
    digits, hyphens; whitespace → hyphens).
    """
    hint = (hint_slug or "").strip().lower()
    if hint:
        raw = re.sub(r"\s+", "-", hint)
        raw = re.sub(r"-{2,}", "-", raw).strip("-/")
    else:
        raw = (name or "").strip().lower()
        raw = re.sub(r"\s+", "-", raw)
        raw = re.sub(r"[^0-9a-z一-鿿/-]", "", raw)
        raw = re.sub(r"-{2,}", "-", raw).strip("-/")
    if not raw.startswith(("entity/", "concept/", "synthesis/", "comparison/")):
        raw = f"concept/{raw}"
    return raw[:240]


def title_to_display(content: str, slug: str) -> Optional[str]:
    """Find the display alias used for ``slug`` in content (for renames)."""
    for match in WIKI_LINK_PATTERN.finditer(content or ""):
        if match.group(1).strip() == slug:
            display = (match.group(2) or "").strip()
            return display or slug.rsplit("/", 1)[-1]
    return None
