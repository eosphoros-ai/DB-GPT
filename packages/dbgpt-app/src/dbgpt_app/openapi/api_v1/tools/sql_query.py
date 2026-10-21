"""sql_query tool — read-only SQL query against the selected database."""

import json
from typing import Any, Dict, Optional

from dbgpt.agent.resource.tool.base import tool

from .query_artifact import (
    build_query_chunk,
    check_read_only,
    markdown_table,
    normalize_result,
)


def make_sql_query(
    react_state: Dict[str, Any],
    database_connector: Optional[Any],
    *,
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
            '参数: {"sql": "SELECT 语句"}' + limit_description
        )
    )
    def sql_query(sql: str) -> str:
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

        if database_connector is None:
            return json.dumps(
                {
                    "chunks": [
                        {
                            "output_type": "text",
                            "content": "未选择数据库，请先在左侧面板选择一个数据源。",
                        }
                    ]
                },
                ensure_ascii=False,
            )

        sql_stripped = sql.strip().rstrip(";")
        forbidden_kw = check_read_only(sql_stripped)
        if forbidden_kw:
            return json.dumps(
                {
                    "chunks": [
                        {
                            "output_type": "text",
                            "content": f"安全限制: 不允许执行 {forbidden_kw} 语句，"
                            "仅支持 SELECT 查询。",
                        }
                    ]
                },
                ensure_ascii=False,
            )

        try:
            result = database_connector.run(sql_stripped)
            if not result:
                return json.dumps(
                    {
                        "chunks": [
                            {"output_type": "text", "content": "查询返回空结果。"}
                        ]
                    },
                    ensure_ascii=False,
                )

            col_names, rows = normalize_result(result)
            # First-class query artifact (SQL + capped full result set) rides
            # alongside the markdown observation: the client renders it as a
            # data artifact with CSV / Excel export, the model only sees the
            # compact markdown table.  db_name travels with the payload so
            # the edit & re-run endpoint can re-resolve the connector.
            chunks = [
                build_query_chunk(
                    sql_stripped,
                    col_names,
                    rows,
                    db_name=(react_state or {}).get("database_name"),
                ),
                {
                    "output_type": "markdown",
                    "content": markdown_table(col_names, rows),
                },
            ]
            return json.dumps({"chunks": chunks}, ensure_ascii=False)
        except Exception as e:
            return json.dumps(
                {
                    "chunks": [
                        {
                            "output_type": "text",
                            "content": f"SQL 执行失败: {str(e)}",
                        }
                    ]
                },
                ensure_ascii=False,
            )

    return sql_query
