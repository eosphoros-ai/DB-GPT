"""Explain SQL structure without executing the query or inventing metric semantics."""

import sqlglot
from pydantic import Field
from sqlglot import exp

from .schemas import StrictModel


class QueryLogicRequest(StrictModel):
    sql: str = Field(min_length=1, max_length=100000)
    data_source_id: str = Field(min_length=1, max_length=255)


def describe_query_logic(sql: str, dialect=None):
    statements = sqlglot.parse(sql, read=dialect)
    if len(statements) != 1 or not isinstance(statements[0], exp.Query):
        raise ValueError("仅支持单条查询的计算逻辑。")
    query = statements[0]
    stages = []
    for index, select in enumerate(query.find_all(exp.Select)):
        parent = select.parent
        alias = parent.alias if isinstance(parent, (exp.Subquery, exp.CTE)) else None
        stages.append(
            {
                "label": "最终结果" if index == 0 else (alias or f"子查询 {index}"),
                "expressions": [
                    item.sql(dialect=dialect) for item in select.expressions
                ],
                "group_by": [
                    item.sql(dialect=dialect)
                    for item in (
                        select.args.get("group").expressions
                        if select.args.get("group")
                        else []
                    )
                ],
                "where": select.args["where"].this.sql(dialect=dialect)
                if select.args.get("where")
                else None,
                "having": select.args["having"].this.sql(dialect=dialect)
                if select.args.get("having")
                else None,
                "joins": [
                    item.sql(dialect=dialect) for item in select.args.get("joins", [])
                ],
                "order_by": select.args["order"].sql(dialect=dialect)
                if select.args.get("order")
                else None,
                "limit": select.args["limit"].sql(dialect=dialect)
                if select.args.get("limit")
                else None,
            }
        )
    cte_names = {cte.alias for cte in query.find_all(exp.CTE)}
    return {
        "tables": list(
            dict.fromkeys(
                table.sql(dialect=dialect)
                for table in query.find_all(exp.Table)
                if table.name not in cte_names
            )
        ),
        "stages": stages,
        "set_operations": [
            operation.key.upper()
            + (" ALL" if operation.args.get("distinct") is False else "")
            for operation in query.find_all(exp.SetOperation)
        ],
    }
