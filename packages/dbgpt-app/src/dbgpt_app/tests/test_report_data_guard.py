from dbgpt_app.openapi.api_v1.report_data_guard import (
    SqlResult,
    validate_html_report_data,
)


def test_validate_html_report_data_rejects_untraceable_kpis():
    sql_results = [
        SqlResult(
            columns=[
                "department_name",
                "plan_trip",
                "real_trip",
                "plan_mileage",
                "real_mileage",
            ],
            rows=[
                ["一车队", 282.0, 282.0, 11194.9, 11194.9],
                ["三车队", 260.5, 260.0, 10370.4, 10333.8],
                ["二车队", 333.0, 333.0, 13792.8, 13792.8],
                ["五车队", 211.5, 211.5, 7704.8, 7704.8],
            ],
            row_count=4,
            sql="SELECT ...",
        )
    ]
    html = """
    <html><body>
      <div>2026年5月10日</div>
      <div>实际班次 320</div>
      <div>班次完成率 92.2%</div>
      <div>实际里程 12,398 km</div>
    </body></html>
    """

    validation = validate_html_report_data(html, sql_results)

    assert not validation.ok
    assert "320" in validation.untraceable_values
    assert "92.2%" in validation.untraceable_values
    assert "12,398" in validation.untraceable_values


def test_validate_html_report_data_allows_sql_values_and_derived_totals():
    sql_results = [
        SqlResult(
            columns=["department_name", "plan_trip", "real_trip", "real_mileage"],
            rows=[
                ["一车队", 282.0, 282.0, 11194.9],
                ["二车队", 333.0, 333.0, 13792.8],
            ],
            row_count=2,
            sql="SELECT ...",
        )
    ]
    html = """
    <html><body>
      <div>计划班次 615</div>
      <div>实际班次 615</div>
      <div>完成率 100.0%</div>
      <div>实际里程 24,987.70</div>
    </body></html>
    """

    validation = validate_html_report_data(html, sql_results)

    assert validation.ok
