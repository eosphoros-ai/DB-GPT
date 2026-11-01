from dbgpt_app.openapi.api_v1.dashboard.lineage import (
    enrich_schema_lineage,
    extract_query_lineage,
)
from dbgpt_app.openapi.api_v1.dashboard.schemas import DashboardSchemaV1

from .test_schema import valid_schema_dict


def test_lineage_ignores_cte_name_and_keeps_physical_table_columns():
    lineage = extract_query_lineage(
        """
        WITH monthly AS (
          SELECT store_id, SUM(weekly_sales) AS sales
          FROM sales
          GROUP BY store_id
        )
        SELECT store_id, sales FROM monthly
        """,
        "walmart",
    )

    assert lineage.data_source_id == "walmart"
    assert lineage.tables == ["sales"]
    assert "store_id" in lineage.columns
    assert "weekly_sales" in lineage.columns


def test_server_replaces_untrusted_lineage_with_ast_derived_metadata():
    payload = valid_schema_dict()
    payload["schema_version"] = "1.2"
    payload["widgets"][0]["query"]["lineage"] = {
        "sources": [
            {
                "data_source_id": "forged",
                "tables": ["hidden_payroll"],
                "columns": ["salary"],
            }
        ]
    }
    schema = DashboardSchemaV1.model_validate(payload)

    enrich_schema_lineage(schema)

    assert len(schema.widgets[0].query.lineage.sources) == 1
    source = schema.widgets[0].query.lineage.sources[0]
    assert source.data_source_id == "walmart"
    assert source.tables == ["sales"]
    assert "weekly_sales" in source.columns
