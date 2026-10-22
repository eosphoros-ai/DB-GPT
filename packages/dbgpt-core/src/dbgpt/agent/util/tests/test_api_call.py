"""Tests for parsing <api-call> blocks in ApiCall."""

from dbgpt.agent.util.api_call import ApiCall


def _llm_text(sql: str) -> str:
    return (
        "Here is the chart.\n<api-call><name>response_bar_chart</name>"
        f"<args><sql>{sql}</sql></args></api-call>"
    )


def test_update_from_context_with_trailing_sql_comment():
    """A trailing "--" comment must not swallow the closing api-call tags."""
    api_call = ApiCall()
    api_call.update_from_context(
        _llm_text("SELECT region, SUM(sales) FROM orders GROUP BY region -- totals")
    )

    statuses = list(api_call.plugin_status_map.values())
    assert len(statuses) == 1
    assert statuses[0].name == "response_bar_chart"
    assert statuses[0].args["sql"].strip() == (
        "SELECT region, SUM(sales) FROM orders GROUP BY region"
    )


def test_update_from_context_with_sql_comment_lines():
    api_call = ApiCall()
    api_call.update_from_context(
        _llm_text(
            "SELECT region, SUM(sales) FROM orders\n"
            "-- totals per region\n"
            "/* grouped */ GROUP BY region"
        )
    )

    statuses = list(api_call.plugin_status_map.values())
    assert len(statuses) == 1
    assert statuses[0].args["sql"] == (
        "SELECT region, SUM(sales) FROM orders  GROUP BY region"
    )
