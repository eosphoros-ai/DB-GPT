"""Bounded database schema-discovery tools for the ReAct agent."""

import json
from collections import OrderedDict
from typing import Any, Dict, List, Optional, Sequence

from dbgpt.agent.resource.tool.base import tool

from ..database_context import (
    format_table_names_bounded,
    get_database_table_names,
    truncate_text,
)
from .sql_query import make_sql_query

DATABASE_TOOL_OUTPUT_MAX_CHARS = 20_000
DATABASE_TABLE_LIST_LIMIT = 100
DATABASE_SCHEMA_CACHE_MAX_ENTRIES = 32


def _tool_response(content: str, output_type: str = "text") -> str:
    """Serialize one tool result chunk."""
    return json.dumps(
        {"chunks": [{"output_type": output_type, "content": content}]},
        ensure_ascii=False,
    )


def _resolve_table_name(
    requested_name: str, table_names: Sequence[str]
) -> Optional[str]:
    """Resolve an exact or unambiguous case-insensitive table name."""
    candidate = requested_name.strip().strip("`\"'")
    if candidate in table_names:
        return candidate

    if "." in candidate:
        unqualified = candidate.rsplit(".", 1)[1].strip().strip("`\"'")
        if unqualified in table_names:
            return unqualified
        candidate = unqualified

    case_insensitive_matches = [
        table_name
        for table_name in table_names
        if table_name.casefold() == candidate.casefold()
    ]
    if len(case_insensitive_matches) == 1:
        return case_insensitive_matches[0]
    return None


def make_list_database_tables(database_connector: Optional[Any]):
    """Create a bounded table-discovery tool."""

    @tool(
        description=(
            "List tables in the selected database. Use query for a case-insensitive "
            "substring search. Parameters: "
            '{"query": "optional table-name fragment", "limit": 50}'
        )
    )
    def list_database_tables(query: str = "", limit: int = 50) -> str:
        """List table names using a bounded optional substring filter."""
        if database_connector is None:
            return _tool_response("No database is selected.")

        try:
            table_names = get_database_table_names(database_connector)
            normalized_query = query.strip().casefold()
            matched = [
                table_name
                for table_name in table_names
                if not normalized_query or normalized_query in table_name.casefold()
            ]
            safe_limit = max(1, min(int(limit), DATABASE_TABLE_LIST_LIMIT))
            displayed = matched[:safe_limit]
            prefix = (
                f"Matched {len(matched)} of {len(table_names)} tables; "
                f"showing {len(displayed)}:\n"
            )
            formatted_names = format_table_names_bounded(
                displayed, DATABASE_TOOL_OUTPUT_MAX_CHARS - len(prefix)
            )
            return _tool_response(prefix + formatted_names, "markdown")
        except Exception as error:
            return _tool_response(f"Failed to list database tables: {error}")

    return list_database_tables


def make_get_table_schema(database_connector: Optional[Any]):
    """Create a validated, bounded, per-table schema lookup tool."""
    schema_cache: OrderedDict[str, str] = OrderedDict()

    @tool(
        description=(
            "Get the schema for one table in the selected database. The table must "
            "exist in list_database_tables. Parameters: "
            '{"table_name": "exact table name"}'
        )
    )
    def get_table_schema(table_name: str) -> str:
        """Return a bounded schema for one validated table name."""
        if database_connector is None:
            return _tool_response("No database is selected.")

        try:
            table_names = get_database_table_names(database_connector)
            resolved_name = _resolve_table_name(table_name, table_names)
            if resolved_name is None:
                return _tool_response(
                    f"Unknown or ambiguous table: {table_name}. "
                    "Use list_database_tables to find the exact name."
                )

            if resolved_name in schema_cache:
                schema_cache.move_to_end(resolved_name)
            else:
                schema_cache[resolved_name] = truncate_text(
                    database_connector.get_table_info_no_throw([resolved_name]),
                    DATABASE_TOOL_OUTPUT_MAX_CHARS,
                )
                if len(schema_cache) > DATABASE_SCHEMA_CACHE_MAX_ENTRIES:
                    schema_cache.popitem(last=False)
            return _tool_response(schema_cache[resolved_name], "markdown")
        except Exception as error:
            return _tool_response(f"Failed to load table schema: {error}")

    return get_table_schema


def make_database_tools(
    react_state: Dict[str, Any], database_connector: Optional[Any]
) -> List[Any]:
    """Build the database tools shared by skill and full ReAct modes."""
    return [
        make_sql_query(react_state, database_connector),
        make_list_database_tables(database_connector),
        make_get_table_schema(database_connector),
    ]
