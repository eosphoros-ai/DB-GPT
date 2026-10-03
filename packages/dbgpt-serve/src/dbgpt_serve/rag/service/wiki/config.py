"""Wiki space-level configuration helpers.

The wiki switch lives in ``knowledge_space.index_methods`` (value ``Wiki``)
and the tuning knobs in ``knowledge_space.context`` under ``wiki_config``
— both fields already flow through the existing space CRUD without any
schema change.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

WIKI_INDEX_METHOD = "Wiki"

GRANULARITY_MAX_PAGES = {
    "focused": 4,
    "standard": 8,
    "exhaustive": 16,
}


@dataclass
class WikiSpaceConfig:
    space_id: int
    enabled: bool
    granularity: str = "standard"
    synthesis_model: Optional[str] = None
    max_pages_per_ingest: int = 8
    content_instructions: str = ""
    extraction_instructions: str = ""

    @classmethod
    def from_space(cls, space: Any) -> "WikiSpaceConfig":
        index_methods: List[str] = []
        if space.index_methods:
            try:
                loaded = (
                    json.loads(space.index_methods)
                    if isinstance(space.index_methods, str)
                    else space.index_methods
                )
                if isinstance(loaded, list):
                    index_methods = [str(m) for m in loaded]
            except (TypeError, ValueError):
                index_methods = []
        enabled = any(m.lower() == WIKI_INDEX_METHOD.lower() for m in index_methods)

        context: Dict[str, Any] = {}
        if space.context:
            try:
                loaded = (
                    json.loads(space.context)
                    if isinstance(space.context, str)
                    else space.context
                )
                if isinstance(loaded, dict):
                    context = loaded
            except (TypeError, ValueError):
                context = {}

        wiki_cfg = context.get("wiki_config") or {}
        if not isinstance(wiki_cfg, dict):
            wiki_cfg = {}
        granularity = wiki_cfg.get("granularity") or "standard"
        if granularity not in GRANULARITY_MAX_PAGES:
            granularity = "standard"
        try:
            max_pages = int(wiki_cfg.get("max_pages_per_ingest") or 0)
        except (TypeError, ValueError):
            max_pages = 0
        return cls(
            space_id=space.id,
            enabled=enabled,
            granularity=granularity,
            synthesis_model=wiki_cfg.get("synthesis_model") or None,
            max_pages_per_ingest=max_pages or GRANULARITY_MAX_PAGES[granularity],
            content_instructions=wiki_cfg.get("content_instructions") or "",
            extraction_instructions=wiki_cfg.get("extraction_instructions") or "",
        )


def wiki_enabled(space: Any) -> bool:
    return WikiSpaceConfig.from_space(space).enabled
