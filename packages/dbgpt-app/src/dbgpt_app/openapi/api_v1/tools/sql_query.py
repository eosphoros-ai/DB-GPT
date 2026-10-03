"""sql_query tool — read-only SQL query against the selected database."""

import json
from typing import Any, Dict, Optional

from dbgpt.agent.resource.tool.base import tool


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
        sql_upper = sql_stripped.upper().lstrip()
        forbidden = [
            "INSERT",
            "UPDATE",
            "DELETE",
            "DROP",
            "ALTER",
            "TRUNCATE",
            "CREATE",
            "GRANT",
            "REVOKE",
        ]
        for kw in forbidden:
            if sql_upper.startswith(kw):
                return json.dumps(
                    {
                        "chunks": [
                            {
                                "output_type": "text",
                                "content": f"安全限制: 不允许执行 {kw} 语句，"
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

            columns = result[0]
            col_names = [str(c[0]) if isinstance(c, tuple) else str(c) for c in columns]
            rows = result[1:]

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
            MAX_SQL_OUTPUT_CHARS = 20_000
            if len(table) > MAX_SQL_OUTPUT_CHARS:
                table = (
                    table[:MAX_SQL_OUTPUT_CHARS]
                    + f"\n\n... [Output truncated at {MAX_SQL_OUTPUT_CHARS} chars. "
                    f"Total rows: {len(rows)}]"
                )

            return json.dumps(
                {"chunks": [{"output_type": "markdown", "content": table}]},
                ensure_ascii=False,
            )
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
