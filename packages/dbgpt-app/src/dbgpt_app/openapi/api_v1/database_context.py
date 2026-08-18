"""Build bounded database context for the ReAct agent."""

import logging
import re
from typing import Any, Iterable, List, Sequence, Tuple

logger = logging.getLogger(__name__)

DATABASE_CONTEXT_MAX_CHARS = 12_000
DATABASE_SCHEMA_CONTEXT_MAX_CHARS = 8_000
DATABASE_TABLE_PREVIEW_LIMIT = 40
DATABASE_TABLE_PREVIEW_MAX_CHARS = 2_000
DATABASE_MENTIONED_TABLE_LIMIT = 5
DATABASE_MENTIONED_TABLES_MAX_CHARS = 1_000
DATABASE_NAME_MAX_CHARS = 256


def build_database_tools_prompt(tool_mode: str, section_number: int) -> str:
    """Describe database tools only when the current mode registers them."""
    if tool_mode == "knowledge":
        return ""
    return f"""
{section_number}. **sql_query**: Execute a read-only SQL query against the selected
database.
Parameters: {{"sql": "SELECT statement"}}
{section_number}.1. **list_database_tables**: List or search table names without
loading schemas.
Parameters: {{"query": "optional name fragment", "limit": 50}}
{section_number}.2. **get_table_schema**: Load one table schema on demand.
Parameters: {{"table_name": "exact table name"}}
""".strip()


def truncate_text(text: str, max_chars: int) -> str:
    """Truncate text to a strict character budget."""
    if len(text) <= max_chars:
        return text
    suffix = f"\n... [truncated at {max_chars} characters]"
    return text[: max_chars - len(suffix)] + suffix


def get_database_table_names(database_connector: Any) -> List[str]:
    """Return stable, unique table names exposed by a connector."""
    names: Iterable[Any] = database_connector.get_table_names()
    return sorted({str(name) for name in names}, key=str.casefold)


def find_mentioned_tables(
    user_input: str,
    table_names: Sequence[str],
    limit: int = DATABASE_MENTIONED_TABLE_LIMIT,
) -> List[str]:
    """Find explicitly named tables using identifier-safe, exact matching."""
    matches: List[Tuple[int, str]] = []
    for table_name in table_names:
        pattern = rf"(?<![\w$]){re.escape(table_name)}(?![\w$])"
        match = re.search(pattern, user_input, flags=re.IGNORECASE)
        if match:
            matches.append((match.start(), table_name))
    matches.sort(key=lambda item: (item[0], item[1].casefold()))
    return [table_name for _, table_name in matches[: max(0, limit)]]


def format_table_names(table_names: Sequence[str]) -> str:
    """Format table names as escaped inline code for prompt/tool output."""
    escaped_names = [
        str(name).replace("`", "``").replace("\r", " ").replace("\n", " ")
        for name in table_names
    ]
    return ", ".join(f"`{name}`" for name in escaped_names)


def format_table_names_bounded(table_names: Sequence[str], max_chars: int) -> str:
    """Format a prefix of whole table names within a strict character budget."""
    if max_chars <= 0 or not table_names:
        return ""

    formatted_names = [format_table_names([name]) for name in table_names]
    for included_count in range(len(formatted_names), -1, -1):
        parts = formatted_names[:included_count]
        omitted_count = len(formatted_names) - included_count
        if omitted_count:
            noun = "table name" if omitted_count == 1 else "table names"
            parts.append(f"... [{omitted_count} {noun} omitted]")
        candidate = ", ".join(parts)
        if len(candidate) <= max_chars:
            return candidate

    omitted_marker = f"... [{len(formatted_names)} table names omitted]"
    return omitted_marker[:max_chars]


def build_database_context(
    database_name: str,
    user_input: str,
    database_connector: Any,
    database_tools_enabled: bool = True,
) -> Tuple[str, List[str], List[str]]:
    """Build a bounded prompt context without dumping the whole database schema."""
    table_names = get_database_table_names(database_connector)
    mentioned_tables = find_mentioned_tables(user_input, table_names)

    preview_tables = list(mentioned_tables)
    for table_name in table_names:
        if table_name not in preview_tables:
            preview_tables.append(table_name)
        if len(preview_tables) >= DATABASE_TABLE_PREVIEW_LIMIT:
            break

    if database_tools_enabled:
        tool_guidance = """
- The `list_database_tables`, `get_table_schema`, and `sql_query` tools are already
  registered. Call them directly when database information is needed.
- Do not terminate or claim that database tools are unavailable merely because a
  table schema is not embedded below.
""".strip()
    else:
        tool_guidance = (
            "- Database tools are disabled because this request is in knowledge-only "
            "mode."
        )

    if mentioned_tables:
        try:
            schema = database_connector.get_table_info_no_throw(mentioned_tables)
        except Exception as error:
            logger.warning(
                "Failed to load schemas for explicitly mentioned tables",
                exc_info=error,
            )
            schema = f"Schema lookup failed: {error}"
        schema = truncate_text(schema, DATABASE_SCHEMA_CONTEXT_MAX_CHARS)
        formatted_mentioned_tables = format_table_names_bounded(
            mentioned_tables,
            DATABASE_MENTIONED_TABLES_MAX_CHARS,
        )
        schema_section = (
            f"- Tables detected in the user request: "
            f"{formatted_mentioned_tables}\n"
            f"- Schemas for detected tables:\n{schema}"
        )
    else:
        schema_section = (
            "- Tables detected in the user request: none\n"
            "- No schema is embedded. Discover tables and request schemas on demand."
        )

    safe_database_name = (str(database_name).replace("\r", " ").replace("\n", " "))[
        :DATABASE_NAME_MAX_CHARS
    ]
    formatted_preview = format_table_names_bounded(
        preview_tables, DATABASE_TABLE_PREVIEW_MAX_CHARS
    )
    context = f"""
## Database
{tool_guidance}
- Only run read-only SELECT statements. Never run write or DDL statements.
- Name: {safe_database_name}
- Total tables: {len(table_names)}
- Table preview (up to {DATABASE_TABLE_PREVIEW_LIMIT}): {formatted_preview}
{schema_section}
""".strip()
    return (
        truncate_text(context, DATABASE_CONTEXT_MAX_CHARS),
        table_names,
        mentioned_tables,
    )
