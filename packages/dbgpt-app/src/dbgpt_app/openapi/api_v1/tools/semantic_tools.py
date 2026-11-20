"""Agent tools for the structured semantic center, independent of ordinary KBs."""

import asyncio
import json
from typing import TYPE_CHECKING, List, Optional

from dbgpt.agent.resource.tool.base import tool

if TYPE_CHECKING:
    from dbgpt_serve.semantic.reader import SemanticReader


def make_semantic_tools(
    database_name: Optional[str], reader: Optional["SemanticReader"] = None
) -> List:
    """Bind semantic reads to the caller's authorized database connection."""
    if not database_name:
        return []

    async def read(method: str, **kwargs) -> str:
        from dbgpt_serve.semantic.reader import SemanticReader

        scoped_reader = reader or SemanticReader(database_name)
        result = await asyncio.to_thread(getattr(scoped_reader, method), **kwargs)
        return json.dumps(result, ensure_ascii=False)

    @tool(
        "semantic_get_metadata",
        description=(
            "Read current database's semantic-center table/column snapshots, types, "
            "comments, PK/FK flags, enums, whitelist and sensitivity flags. "
            "table_name is an exact table name; query is a keyword; limit is 1-50. "
            "Check last_sync_at; this is metadata, not a published business caliber."
        ),
    )
    async def metadata(table_name: str = "", query: str = "", limit: int = 20) -> str:
        return await read("metadata", table_name=table_name, query=query, limit=limit)

    @tool(
        "semantic_search_business",
        description=(
            "Find published business definitions, field meanings and synonyms in "
            "the current database's structured semantic center. query is a business "
            "term/keyword; table_name optionally filters an exact table; limit 1-50. "
            "Returns source IDs, table/column targets, definitions and versions. "
            "Drafts/stale entries are excluded. "
            "Empty results are not governed semantics."
        ),
    )
    async def business(query: str = "", table_name: str = "", limit: int = 20) -> str:
        return await read(
            "business_semantics", query=query, table_name=table_name, limit=limit
        )

    @tool(
        "semantic_search_metrics",
        description=(
            "Find published metrics in the current database by name, business "
            "description or definition keyword (query, limit 1-50). "
            "Returns caliber snapshots and metric IDs/versions. Resolve ambiguity "
            "and call semantic_get_metric before generating SQL."
        ),
    )
    async def metrics(query: str = "", limit: int = 10) -> str:
        return await read("search_metrics", query=query, limit=limit)

    @tool(
        "semantic_get_metric",
        description=(
            "Read an authoritative published metric caliber from the current database. "
            "Provide exactly one of metric_id (integer) or metric_name (exact name). "
            "version optionally selects an exact positive integer version; omitted "
            "means latest published snapshot. "
            "Returns definition, formula, base_metrics, "
            "dimensions and version citation. No draft or version fallback. Reuse the "
            "returned version for subsequent steps. Do not invent missing fields."
        ),
    )
    async def metric(
        metric_id: Optional[int] = None,
        metric_name: str = "",
        version: Optional[int] = None,
    ) -> str:
        return await read(
            "get_metric", metric_id=metric_id, metric_name=metric_name, version=version
        )

    return [metadata, business, metrics, metric]
