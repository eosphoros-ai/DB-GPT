"""Query artifact helpers — structured SQL-result payloads.

The ``query`` output type carries the executed SQL plus the (capped) result
set so the web client can render a first-class data artifact — SQL block +
result table with CSV / Excel export — without re-running the query.

Both SQL tool implementations (the react-agent ``sql_query`` tool and the
TaskFlow multi-datasource variant) and the SQL re-run endpoint build their
payloads through :func:`build_query_chunk` so every surface agrees on shape
and caps.
"""

from typing import Any, Dict, List, Optional, Sequence, Tuple

#: Output type key understood by the web client's artifact pipeline.
QUERY_OUTPUT_TYPE = "query"

#: Maximum rows carried inside a query artifact payload.  Larger results are
#: truncated for the artifact (``truncated=True``); the LLM observation keeps
#: its own tighter markdown cap.
QUERY_ARTIFACT_MAX_ROWS = 2000

#: Maximum columns carried inside a query artifact payload.
QUERY_ARTIFACT_MAX_COLS = 64

#: Row / char caps for the markdown observation fed back to the model.
QUERY_MD_MAX_ROWS = 50
QUERY_MD_MAX_CHARS = 20_000

#: Write statements rejected up-front; read-only SELECT is the only shape
#: every SQL surface in this repo is allowed to execute.
FORBIDDEN_SQL_PREFIXES = (
    "INSERT",
    "UPDATE",
    "DELETE",
    "DROP",
    "ALTER",
    "TRUNCATE",
    "CREATE",
    "GRANT",
    "REVOKE",
)


def check_read_only(sql: str) -> Optional[str]:
    """Return the forbidden keyword prefixing ``sql``, or None when allowed."""
    sql_upper = sql.strip().rstrip(";").upper().lstrip()
    for kw in FORBIDDEN_SQL_PREFIXES:
        if sql_upper.startswith(kw):
            return kw
    return None


def _jsonable(value: Any) -> Any:
    """Coerce connector cell values into JSON-safe primitives."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (bytes, bytearray)):
        return value.hex()
    return str(value)


def normalize_result(
    result: Sequence[Any],
) -> Tuple[List[str], List[List[Any]]]:
    """Split a connector result (header row + data rows) into names/rows."""
    columns = [
        str(c[0]) if isinstance(c, tuple) else str(c) for c in (result[0] or [])
    ]
    rows = [list(row) for row in result[1:]]
    return columns, rows


def build_query_chunk(
    sql: str,
    columns: Sequence[Any],
    rows: Sequence[Sequence[Any]],
    *,
    db_name: Optional[str] = None,
    max_rows: int = QUERY_ARTIFACT_MAX_ROWS,
) -> Dict[str, Any]:
    """Build the ``query`` output chunk for a SQL result set."""
    col_names = [str(c) for c in columns][:QUERY_ARTIFACT_MAX_COLS]
    kept = list(rows)[:max_rows]
    payload: Dict[str, Any] = {
        "sql": sql,
        "columns": col_names,
        "rows": [
            [_jsonable(v) for v in list(row)[: len(col_names)]] for row in kept
        ],
        "row_count": len(rows),
        "truncated": len(rows) > max_rows,
    }
    if db_name:
        payload["db_name"] = db_name
    return {"output_type": QUERY_OUTPUT_TYPE, "content": payload}


def markdown_table(
    columns: Sequence[str],
    rows: Sequence[Sequence[Any]],
    *,
    max_rows: int = QUERY_MD_MAX_ROWS,
    max_chars: int = QUERY_MD_MAX_CHARS,
) -> str:
    """Compact markdown table for the model observation (row/char capped)."""
    col_names = [str(c) for c in columns]
    header = "| " + " | ".join(col_names) + " |"
    separator = "| " + " | ".join(["---"] * len(col_names)) + " |"
    md_rows = [
        "| " + " | ".join(str(v) for v in list(row)[: len(col_names)]) + "|"
        for row in list(rows)[:max_rows]
    ]
    table = "\n".join([header, separator] + md_rows)
    if len(rows) > max_rows:
        table += f"\n\n（仅显示前 {max_rows} 行，共 {len(rows)} 行）"
    if len(table) > max_chars:
        table = (
            table[:max_chars]
            + f"\n\n... [Output truncated at {max_chars} chars. "
            f"Total rows: {len(rows)}]"
        )
    return table
