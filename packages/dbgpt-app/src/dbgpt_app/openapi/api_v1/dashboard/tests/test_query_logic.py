import pytest

from dbgpt_app.openapi.api_v1.dashboard.query_logic import describe_query_logic


def test_reports_formula_grouping_and_filters_including_inner_calculation():
    logic = describe_query_logic(
        """
        SELECT country, category, SUM(amount) AS value FROM (
          SELECT country, category, quantity * unit_price * (1 - discount) AS amount
          FROM order_details WHERE year = :year
        ) AS sales
        GROUP BY country, category HAVING SUM(amount) > 0
        ORDER BY value DESC LIMIT 20
    """,
        "sqlite",
    )
    outer, inner = logic["stages"]
    assert outer["expressions"][-1] == "SUM(amount) AS value"
    assert outer["group_by"] == ["country", "category"]
    assert outer["having"] == "SUM(amount) > 0"
    assert "DESC" in outer["order_by"]
    assert "20" in outer["limit"]
    assert inner["label"] == "sales"
    assert "quantity * unit_price * (1 - discount)" in inner["expressions"][-1]
    assert ":year" in inner["where"]
    assert logic["tables"] == ["order_details"]


def test_cte_and_union_remain_visible_without_claiming_cte_is_a_source_table():
    logic = describe_query_logic(
        "WITH totals AS (SELECT SUM(amount) AS total FROM sales) "
        "SELECT total FROM totals UNION ALL SELECT 0"
    )
    assert logic["tables"] == ["sales"]
    assert logic["set_operations"] == ["UNION ALL"]
    assert any(stage["label"] == "totals" for stage in logic["stages"])


@pytest.mark.parametrize(
    "sql", ["DELETE FROM sales", "SELECT 1; SELECT 2", "UPDATE sales SET value = 1"]
)
def test_only_describes_a_single_query(sql):
    with pytest.raises(ValueError):
        describe_query_logic(sql)
