"""sql_query tool — read-only SQL query against the selected database."""

import asyncio
import json
import time
from functools import wraps
from threading import Event
from typing import Any, Dict, Optional

from dbgpt.agent.resource.tool.base import tool
from dbgpt.core.interface.report_capture import (
    capture_sql_execution,
    connector_database_name,
)
from dbgpt.datasource.rdbms.base import RDBMSConnector

from .sql_read_only import ReadOnlySqlError, read_only_sql


def _supports_cooperative_query(connector: Any) -> bool:
    """Return whether ``query_ex`` is the connector's real SQLite adapter.

    ``ClickhouseConnector`` and other dedicated-client subclasses inherit
    ``query_ex`` from ``RDBMSConnector`` but do not own its SQLAlchemy session
    pool.  They must use their own ``run`` implementation instead.
    """
    return (
        isinstance(connector, RDBMSConnector)
        and type(connector).run is RDBMSConnector.run
        and type(connector).query_ex is RDBMSConnector.query_ex
        and connector.dialect == "sqlite"
    )


def make_sql_query(
    react_state: Dict[str, Any],
    database_connector: Optional[Any],
    *,
    max_output_chars: Optional[int] = 20_000,
    query_timeout_seconds: float = 30,
    max_calls: Optional[int] = None,
):
    call_count = 0
    limit_description = (
        f" Dashboard planning allows at most {max_calls} discovery calls; "
        "after that, use the collected observations and call plan_dashboard."
        if max_calls is not None
        else ""
    )

    @tool(
        description=(
            "对用户选择的数据库执行 SQL 查询（仅支持 SELECT）。"
            '参数: {"sql": "SELECT 语句"}。单次查询默认最多 30 秒，超时后先查看 '
            "EXPLAIN QUERY PLAN 与关联索引，优化查询；不要原样反复提交超时 SQL。"
            + limit_description
        )
    )
    async def sql_query(sql: str) -> str:
        """Execute a read-only SQL query against the selected database."""

        nonlocal call_count
        if max_calls is not None and call_count >= max_calls:
            return json.dumps(
                {
                    "chunks": [
                        {
                            "output_type": "text",
                            "content": (
                                "Dashboard discovery limit reached after "
                                f"{max_calls} SQL queries. Do not call sql_query "
                                "again in this turn. Use the observations already "
                                "collected and call plan_dashboard now. If plan "
                                "validation rejects a field or default, correct the "
                                "plan from that validation feedback instead of "
                                "restarting discovery."
                            ),
                        }
                    ],
                    "dashboard_discovery_limit_reached": True,
                },
                ensure_ascii=False,
            )
        call_count += 1

        artifact_sink = react_state.get("_report_artifact_sink")
        if database_connector is None:
            return json.dumps(
                {
                    "success": False,
                    "error_code": "SQL_DATASOURCE_REQUIRED",
                    "chunks": [
                        {
                            "output_type": "text",
                            "content": "未选择数据库，请先在左侧面板选择一个数据源。",
                        }
                    ],
                },
                ensure_ascii=False,
            )

        try:
            sql_stripped = read_only_sql(sql)
        except ReadOnlySqlError:
            return json.dumps(
                {
                    "success": False,
                    "error_code": "SQL_READ_ONLY_REQUIRED",
                    "chunks": [
                        {
                            "output_type": "text",
                            "content": (
                                "仅支持单条只读 SELECT / WITH 查询及其 EXPLAIN。"
                            ),
                        }
                    ],
                },
                ensure_ascii=False,
            )
        started = time.perf_counter()
        cancel_event = Event()
        try:
            if _supports_cooperative_query(database_connector):

                async def execute():
                    columns, rows = await asyncio.to_thread(
                        database_connector.query_ex,
                        sql_stripped,
                        timeout=query_timeout_seconds,
                        cancel_event=cancel_event,
                    )
                    return [columns, *(rows or [])]
            else:

                async def execute():
                    return await asyncio.to_thread(database_connector.run, sql_stripped)

            result = await asyncio.wait_for(execute(), timeout=query_timeout_seconds)
            if not result:
                artifact_id = capture_sql_execution(
                    sql=sql_stripped,
                    database=connector_database_name(database_connector, artifact_sink),
                    duration_ms=int((time.perf_counter() - started) * 1000),
                    columns=[],
                    rows=[],
                    artifact_sink=artifact_sink,
                )
                return json.dumps(
                    {
                        "artifact_id": artifact_id,
                        "chunks": [
                            {"output_type": "text", "content": "查询返回空结果。"}
                        ],
                    },
                    ensure_ascii=False,
                )

            columns = result[0]
            col_names = [str(c[0]) if isinstance(c, tuple) else str(c) for c in columns]
            rows = result[1:]

            artifact_id = capture_sql_execution(
                sql=sql_stripped,
                database=connector_database_name(database_connector, artifact_sink),
                duration_ms=int((time.perf_counter() - started) * 1000),
                columns=col_names,
                rows=rows,
                artifact_sink=artifact_sink,
            )

            header = "| " + " | ".join(col_names) + " |"
            separator = "| " + " | ".join(["---"] * len(col_names)) + " |"
            md_rows = []
            for row in rows[:50]:
                md_rows.append("| " + " | ".join(str(v) for v in row) + " |")
            table = "\n".join([header, separator] + md_rows)
            if len(rows) > 50:
                table += f"\n\n（仅显示前 50 行，共 {len(rows)} 行）"

            # Cap total output size so a single wide query can't blow out the
            # LLM context window. The full result remains available via the
            # ToolResultStorage persistence layer if it exceeds the threshold.
            if max_output_chars is not None and len(table) > max_output_chars:
                table = (
                    table[:max_output_chars]
                    + f"\n\n... [Output truncated at {max_output_chars} chars. "
                    f"Total rows: {len(rows)}]"
                )

            return json.dumps(
                {
                    "artifact_id": artifact_id,
                    "chunks": [{"output_type": "markdown", "content": table}],
                },
                ensure_ascii=False,
            )
        except asyncio.CancelledError:
            cancel_event.set()
            capture_sql_execution(
                sql=sql_stripped,
                database=connector_database_name(database_connector, artifact_sink),
                duration_ms=int((time.perf_counter() - started) * 1000),
                error="SQL_QUERY_CANCELLED: upper-level task cancelled the query",
                artifact_sink=artifact_sink,
            )
            raise
        except Exception as e:
            if str(e).startswith("ARTIFACT_CAPTURE_FAILED:"):
                return json.dumps(
                    {
                        "success": False,
                        "error_code": "ARTIFACT_CAPTURE_FAILED",
                        "chunks": [{"output_type": "text", "content": str(e)}],
                    },
                    ensure_ascii=False,
                )
            cancel_event.set()
            timed_out = isinstance(e, TimeoutError)
            code = "SQL_QUERY_TIMEOUT" if timed_out else "SQL_QUERY_FAILED"
            message = (
                f"{code}: 查询超过 {query_timeout_seconds:g} 秒，已请求中断。"
                "先检查 EXPLAIN QUERY PLAN 与关联索引，优化查询；不要原样重试。"
                if timed_out
                else f"{code}: SQL 执行失败: {e}"
            )
            capture_sql_execution(
                sql=sql_stripped,
                database=connector_database_name(database_connector, artifact_sink),
                duration_ms=int((time.perf_counter() - started) * 1000),
                error=message,
                artifact_sink=artifact_sink,
            )
            return json.dumps(
                {
                    "chunks": [
                        {
                            "output_type": "text",
                            "content": message,
                        }
                    ],
                    "error_code": code,
                    "success": False,
                },
                ensure_ascii=False,
            )

    @wraps(sql_query)
    def invoke_sql_query(*args, **kwargs):
        # Preserve direct synchronous callers while agents use the asynchronous
        # FunctionTool copied by wraps. Its coroutine keeps timeout/cancellation.
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(sql_query(*args, **kwargs))
        return sql_query(*args, **kwargs)

    return invoke_sql_query
