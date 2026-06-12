from dbgpt_app.openapi.api_v1 import agentic_data_api


def test_bus_operation_question_uses_only_ads_schema_tables():
    table_names = [
        "ads_ope_summary_line_d",
        "ads_ope_summary_vehicle_d",
        "dwd_operate_driving_gps_mileage",
        "dim_resource_line",
        "ods_dispatch_log",
    ]
    table_info = """
CREATE TABLE ads_ope_summary_line_d (target_date DATE, line_code VARCHAR);
CREATE TABLE dwd_operate_driving_gps_mileage (target_date DATE, line_code VARCHAR);
CREATE TABLE dim_resource_line (line_code VARCHAR, line_name VARCHAR);
CREATE TABLE ads_ope_summary_vehicle_d (target_date DATE, vehicle_code VARCHAR);
CREATE TABLE ods_dispatch_log (id BIGINT);
"""

    context = agentic_data_api._build_database_context(
        database_name="bus_info",
        user_question="海通公交5月10日的运营日报",
        table_names=table_names,
        table_info=table_info,
    )

    assert "ads_ope_summary_line_d" in context
    assert "ads_ope_summary_vehicle_d" in context
    assert "dwd_operate_driving_gps_mileage" not in context
    assert "dim_resource_line" not in context
    assert "ods_dispatch_log" not in context
    assert "当前问题已识别为运营类问题" in context


def test_non_operation_question_keeps_full_schema_tables():
    table_names = ["ads_ope_summary_line_d", "dim_resource_line"]
    table_info = """
CREATE TABLE ads_ope_summary_line_d (target_date DATE);
CREATE TABLE dim_resource_line (line_code VARCHAR);
"""

    context = agentic_data_api._build_database_context(
        database_name="bus_info",
        user_question="这个库有哪些维表",
        table_names=table_names,
        table_info=table_info,
    )

    assert "ads_ope_summary_line_d" in context
    assert "dim_resource_line" in context
    assert "当前问题已识别为运营类问题" not in context


def test_bus_operation_sql_rejects_non_ads_tables():
    error = agentic_data_api._validate_bus_operation_sql_tables(
        database_name="bus_info",
        user_question="查询5月10日运营数据",
        sql=(
            "SELECT line_code FROM ads_ope_summary_line_d "
            "JOIN dim_resource_line USING (line_code)"
        ),
    )

    assert error is not None
    assert "运营类问题只能查询 ads_ 开头的汇总表" in error
    assert "dim_resource_line" in error


def test_bus_operation_sql_rejects_quoted_non_ads_tables():
    error = agentic_data_api._validate_bus_operation_sql_tables(
        database_name="bus_info",
        user_question="查询5月10日运营日报",
        sql=(
            'SELECT line_code FROM ads_ope_summary_line_d '
            'JOIN "dim_resource_line" d USING (line_code)'
        ),
    )

    assert error is not None
    assert "dim_resource_line" in error


def test_bus_operation_sql_allows_ads_tables():
    error = agentic_data_api._validate_bus_operation_sql_tables(
        database_name="bus_info",
        user_question="查询5月10日运营数据",
        sql=(
            "WITH s AS (SELECT * FROM ads_ope_summary_line_d) "
            "SELECT * FROM s JOIN ads_ope_summary_vehicle_d v "
            "ON s.vehicle_code = v.vehicle_code"
        ),
    )

    assert error is None


def test_sql_query_preview_names_saved_full_result_ref():
    rows = [[idx, f"line-{idx}"] for idx in range(55)]

    preview = agentic_data_api._format_sql_query_markdown(
        col_names=["idx", "line_name"],
        rows=rows,
        result_ref="SQL_RESULT_1",
    )

    assert "| 49 | line-49 |" in preview
    assert "| 50 | line-50 |" not in preview
    assert "仅显示前 50 行，共 55 行" in preview
    assert "SQL_RESULT_1" in preview
    assert "不要只依据上方预览行" in preview


def test_serialize_sql_results_for_code_keeps_full_rows_and_refs():
    serialized = agentic_data_api._serialize_sql_results_for_code(
        [
            agentic_data_api.SqlResult(
                columns=["idx"],
                rows=[[idx] for idx in range(3)],
                row_count=3,
                sql="SELECT idx FROM ads_ope_summary_line_d",
            )
        ]
    )

    assert serialized == [
        {
            "ref": "SQL_RESULT_1",
            "columns": ["idx"],
            "rows": [[0], [1], [2]],
            "row_count": 3,
            "sql": "SELECT idx FROM ads_ope_summary_line_d",
        }
    ]


def test_sql_backed_report_code_requires_saved_sql_results_reference():
    sql_results = [
        agentic_data_api.SqlResult(
            columns=["total"],
            rows=[[1936.5]],
            row_count=1,
            sql="SELECT SUM(plan_trip) FROM ads_ope_summary_line_d",
        )
    ]

    assert agentic_data_api._code_uses_saved_sql_results(
        "total = SQL_QUERY_RESULTS[0]['rows'][0][0]",
        sql_results,
    )
    assert agentic_data_api._code_uses_saved_sql_results(
        "with open(SQL_RESULTS_PATH) as f: data = f.read()",
        sql_results,
    )
    assert not agentic_data_api._code_uses_saved_sql_results(
        "total = 1936.5",
        sql_results,
    )
    assert not agentic_data_api._code_uses_saved_sql_results(
        "total = SQL_QUERY_RESULTS[0]['rows'][0][0]",
        [],
    )


def test_validate_saved_sql_result_code_rejects_guessed_result_index():
    sql_results = [
        agentic_data_api.SqlResult(
            columns=["total_plan_trip"],
            rows=[[1499.5]],
            row_count=1,
            sql="SELECT total_plan_trip",
        ),
        agentic_data_api.SqlResult(
            columns=["department_name", "plan_trip"],
            rows=[["一车队", 282.0]],
            row_count=1,
            sql="SELECT department_name, plan_trip",
        ),
    ]

    error = agentic_data_api._validate_saved_sql_result_code(
        "data = SQL_QUERY_RESULTS\nresult = data[0]\n",
        sql_results,
    )

    assert error is not None
    assert "get_sql_result" in error
    assert "find_sql_result_by_columns" in error


def test_validate_saved_sql_result_code_rejects_silent_zero_defaults():
    sql_results = [
        agentic_data_api.SqlResult(
            columns=["department_name", "plan_trip"],
            rows=[["一车队", 282.0]],
            row_count=1,
            sql="SELECT department_name, plan_trip",
        )
    ]

    error = agentic_data_api._validate_saved_sql_result_code(
        'plan = float(row.get("plan_trip") or 0)\n',
        sql_results,
    )

    assert error is not None
    assert "require_value" in error
    assert "不能默认置 0" in error


def test_validate_saved_sql_result_code_allows_helper_based_access():
    sql_results = [
        agentic_data_api.SqlResult(
            columns=["total_plan_trip", "total_real_trip"],
            rows=[[1499.5, 1480.5]],
            row_count=1,
            sql="SELECT total_plan_trip, total_real_trip",
        )
    ]

    error = agentic_data_api._validate_saved_sql_result_code(
        """
result = find_sql_result_by_columns(["total_plan_trip", "total_real_trip"])
rows = sql_result_rows(result)
total_plan = to_float(require_value(rows[0], "total_plan_trip"))
""",
        sql_results,
    )

    assert error is None


def test_extract_literal_html_output_paths_from_code(tmp_path):
    work_dir = str(tmp_path / "work")
    code = """
with open('/tmp/report.html', 'w', encoding='utf-8') as f:
    f.write(html)
Path("nested/report.htm").write_text(html)
"""

    paths = agentic_data_api._extract_literal_html_paths_from_code(code, work_dir)

    assert "/tmp/report.html" in paths
    assert str(tmp_path / "work" / "nested" / "report.htm") in paths


def test_select_existing_sql_backed_report_file_uses_latest(tmp_path):
    first = tmp_path / "first.html"
    second = tmp_path / "second.html"
    missing = tmp_path / "missing.html"
    first.write_text("<html>first</html>", encoding="utf-8")
    second.write_text("<html>second</html>", encoding="utf-8")

    selected = agentic_data_api._select_existing_sql_backed_report_file(
        [str(missing), str(first), str(second)]
    )

    assert selected == str(second)


def test_update_sql_backed_report_files_clears_stale_file_on_failure(tmp_path):
    report = tmp_path / "report.html"
    report.write_text("<html>old</html>", encoding="utf-8")
    signature = agentic_data_api._file_signature(str(report))

    trusted = agentic_data_api._updated_sql_backed_report_files(
        existing_files=[str(report)],
        candidate_paths=[str(report)],
        signatures_before={str(report): signature},
        uses_saved_sql_results=True,
        return_code=1,
    )

    assert trusted == []


def test_update_sql_backed_report_files_keeps_changed_file_on_success(tmp_path):
    report = tmp_path / "report.html"
    report.write_text("<html>old</html>", encoding="utf-8")
    before = agentic_data_api._file_signature(str(report))
    report.write_text("<html>new</html>", encoding="utf-8")

    trusted = agentic_data_api._updated_sql_backed_report_files(
        existing_files=[],
        candidate_paths=[str(report)],
        signatures_before={str(report): before},
        uses_saved_sql_results=True,
        return_code=0,
    )

    assert trusted == [str(report)]


def test_sql_query_results_example_uses_column_names_not_guessed_indexes():
    example = agentic_data_api._sql_query_results_access_example()

    assert "find_sql_result_by_columns" in example
    assert "sql_result_rows(result)" in example
    assert "require_columns" in example
    assert "data[0]" not in example
    assert 'row.get("total_value")' not in example
    assert "row[col_idx]" not in example


def test_sql_query_results_helpers_reject_missing_report_columns():
    namespace: dict = {}
    exec(agentic_data_api._sql_query_results_helper_preamble(), namespace)

    result = {
        "columns": ["total_plan_trip"],
        "rows": [[1499.5]],
    }

    try:
        namespace["require_columns"](
            result,
            ["total_plan_trip", "total_real_trip"],
        )
    except KeyError as exc:
        assert "total_real_trip" in str(exc)
    else:
        raise AssertionError("missing SQL result columns should raise KeyError")


def test_sql_query_results_helpers_read_required_values_by_column_name():
    namespace: dict = {}
    exec(agentic_data_api._sql_query_results_helper_preamble(), namespace)

    result = {
        "columns": ["total_plan_trip", "total_real_trip"],
        "rows": [[1499.5, 1480.5]],
    }

    namespace["require_columns"](
        result,
        ["total_plan_trip", "total_real_trip"],
    )
    rows = namespace["sql_result_rows"](result)

    assert namespace["require_value"](rows[0], "total_plan_trip") == 1499.5
    assert namespace["require_value"](rows[0], "total_real_trip") == 1480.5


def test_sql_query_results_helpers_find_result_by_ref_and_columns():
    namespace: dict = {
        "SQL_QUERY_RESULTS": [
            {
                "ref": "SQL_RESULT_1",
                "columns": ["total_plan_trip", "total_real_trip"],
                "rows": [[1499.5, 1480.5]],
            },
            {
                "ref": "SQL_RESULT_2",
                "columns": ["department_name", "plan_trip", "real_trip"],
                "rows": [["一车队", 282.0, 282.0]],
            },
        ]
    }
    exec(agentic_data_api._sql_query_results_helper_preamble(), namespace)

    by_ref = namespace["get_sql_result"]("SQL_RESULT_2")
    by_columns = namespace["find_sql_result_by_columns"](
        ["department_name", "plan_trip", "real_trip"]
    )

    assert by_ref["columns"] == ["department_name", "plan_trip", "real_trip"]
    assert by_columns["ref"] == "SQL_RESULT_2"


def test_sql_query_results_helpers_raise_when_result_not_found():
    namespace: dict = {
        "SQL_QUERY_RESULTS": [
            {
                "ref": "SQL_RESULT_1",
                "columns": ["total_plan_trip"],
                "rows": [[1499.5]],
            }
        ]
    }
    exec(agentic_data_api._sql_query_results_helper_preamble(), namespace)

    try:
        namespace["find_sql_result_by_columns"](["plan_trip", "real_trip"])
    except KeyError as exc:
        assert "plan_trip" in str(exc)
        assert "real_trip" in str(exc)
    else:
        raise AssertionError("missing SQL result should raise KeyError")
