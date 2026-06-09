from dbgpt_app.openapi.api_v1 import agentic_data_api


def test_postgres_sql_rules_include_required_dialect_constraints():
    rules = agentic_data_api._postgres_sql_dialect_rules("bus_info")

    assert "当前数据库固定为 PostgreSQL" in rules
    assert "禁止使用 MySQL/SQLite/SQL Server 语法" in rules
    assert "禁止使用反引号 `identifier`" in rules
    assert "CURRENT_DATE - INTERVAL '7 days'" in rules
    assert "TO_CHAR(date_col, 'YYYY-MM-DD')" in rules
    assert "COALESCE(col, 0)" in rules
    assert "不要使用 IFNULL" in rules
    assert "STRING_AGG(col::text, ',')" in rules
    assert "不要使用 GROUP_CONCAT" in rules
    assert "LIMIT n OFFSET m" in rules
    assert "不要使用 LIMIT m,n" in rules
    assert "CAST(col AS type) 或 col::type" in rules
    assert "所有 SQL 必须是单条 SELECT / WITH ... SELECT" in rules


def test_postgres_sql_rules_include_observed_bus_info_failures():
    rules = agentic_data_api._postgres_sql_dialect_rules("bus_info")

    assert "ROUND((expr)::numeric, n)" in rules
    assert "bigdata_ticket_revenue 使用 revenue_date" in rules
    assert "dim_resource_line 不存在 delete_flag" in rules
    assert "ads_ope_ontime_assess_d 不存在 zd_cnt" in rules
    assert "ads_ope_summary_line_d 不存在 driver_number" in rules
