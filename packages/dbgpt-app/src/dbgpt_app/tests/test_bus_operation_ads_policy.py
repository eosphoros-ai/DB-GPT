import inspect
from types import SimpleNamespace

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


def test_resolve_skill_file_path_from_skill_name_when_missing(tmp_path):
    skills_dir = tmp_path / "skills"
    skill_file = skills_dir / "user" / "ops-report" / "SKILL.md"
    skill_file.parent.mkdir(parents=True)
    skill_file.write_text("# skill", encoding="utf-8")
    skill = SimpleNamespace(
        metadata=SimpleNamespace(name="运营报告", file_path=str(skill_file))
    )

    resolved = agentic_data_api._resolve_skill_file_path(
        skill_name="运营报告",
        file_path="",
        all_skills=[skill],
        skills_dir=str(skills_dir),
    )

    assert resolved == "user/ops-report/SKILL.md"


def test_resolve_skill_file_path_prefers_explicit_path(tmp_path):
    resolved = agentic_data_api._resolve_skill_file_path(
        skill_name="运营报告",
        file_path="user/custom/SKILL.md",
        all_skills=[],
        skills_dir=str(tmp_path),
    )

    assert resolved == "user/custom/SKILL.md"


def test_non_operation_question_keeps_full_schema_tables():
    table_names = ["ads_ope_summary_line_d", "dim_resource_line"]
    table_info = """
CREATE TABLE ads_ope_summary_line_d (target_date DATE);
CREATE TABLE dim_resource_line (line_code VARCHAR);
"""

    context = agentic_data_api._build_database_context(
        database_name="bus_info",
        user_question="这个库有哪些表",
        table_names=table_names,
        table_info=table_info,
    )

    assert "ads_ope_summary_line_d" in context
    assert "dim_resource_line" in context
    assert "当前问题已识别为运营类问题" not in context


def test_basic_resource_question_uses_only_dim_schema_tables():
    table_names = [
        "ads_ope_summary_line_d",
        "dim_resource_line",
        "dim_fleet_vehicle",
        "dim_driver",
        "dwd_driver_phone_detail",
    ]
    table_info = """
CREATE TABLE ads_ope_summary_line_d (target_date DATE, line_code VARCHAR);
CREATE TABLE dim_resource_line (line_code VARCHAR, line_name VARCHAR);
CREATE TABLE dim_fleet_vehicle (inner_code VARCHAR, license_plate VARCHAR);
CREATE TABLE dim_driver (driver_name VARCHAR, phone VARCHAR, id_card VARCHAR);
CREATE TABLE dwd_driver_phone_detail (phone VARCHAR);
"""

    context = agentic_data_api._build_database_context(
        database_name="bus_info",
        user_question="查询公司基础资源车辆和驾驶员档案",
        table_names=table_names,
        table_info=table_info,
    )

    assert "dim_resource_line" in context
    assert "dim_fleet_vehicle" in context
    assert "dim_driver" in context
    assert "ads_ope_summary_line_d" not in context
    assert "dwd_driver_phone_detail" not in context
    assert "当前问题已识别为公司基础资源类问题" in context


def test_basic_resource_sql_rejects_non_dim_tables():
    error = agentic_data_api._validate_bus_table_policy_sql(
        database_name="bus_info",
        user_question="查询公司基础资源线路清单",
        sql="SELECT line_code FROM ads_ope_summary_line_d",
    )

    assert error is not None
    assert "基础资源类问题只能查询 dim_ 开头的维表" in error
    assert "ads_ope_summary_line_d" in error


def test_basic_resource_sql_allows_dim_tables():
    error = agentic_data_api._validate_bus_table_policy_sql(
        database_name="bus_info",
        user_question="查询公司基础资源车辆清单",
        sql="SELECT inner_code, license_plate FROM dim_fleet_vehicle",
    )

    assert error is None


def test_database_context_contains_privacy_masking_rules():
    context = agentic_data_api._build_database_context(
        database_name="bus_info",
        user_question="查询驾驶员基础信息",
        table_names=["dim_driver"],
        table_info=(
            "CREATE TABLE dim_driver (driver_name VARCHAR, phone VARCHAR, "
            "id_card VARCHAR);"
        ),
    )

    assert "手机号" in context
    assert "身份证号" in context
    assert "***" in context
    assert "不得明文输出" in context


def test_database_context_marks_schema_as_internal_only():
    context = agentic_data_api._build_database_context(
        database_name="bus_info",
        user_question="查询车辆基础信息",
        table_names=["dim_fleet_vehicle"],
        table_info="CREATE TABLE dim_fleet_vehicle (inner_code VARCHAR);",
    )

    assert "表结构仅供内部生成 SQL 使用" in context
    assert "不得向客户展示" in context


def test_customer_facing_answer_suppresses_schema_details():
    answer = (
        "可用表: dim_driver\n"
        "表结构:\n"
        "CREATE TABLE dim_driver (driver_name VARCHAR, phone VARCHAR);"
    )

    sanitized = agentic_data_api._sanitize_customer_facing_answer(answer)

    assert "CREATE TABLE" not in sanitized
    assert "dim_driver" not in sanitized
    assert "phone" not in sanitized
    assert "表结构" not in sanitized
    assert "不展示" in sanitized


def test_customer_facing_answer_suppresses_natural_language_schema_details():
    answer = "dim_hr_employee 表共有 46个字段，字段名包括 mobile_phone 和 id_num。"

    sanitized = agentic_data_api._sanitize_customer_facing_answer(answer)

    assert "dim_hr_employee" not in sanitized
    assert "mobile_phone" not in sanitized
    assert "id_num" not in sanitized
    assert "字段" not in sanitized
    assert "不展示" in sanitized


def test_customer_facing_json_chunks_suppress_schema_details():
    answer = (
        '{"chunks":[{"output_type":"text","content":'
        '"CREATE TABLE dim_driver (phone VARCHAR);"}]}'
    )

    sanitized = agentic_data_api._sanitize_customer_facing_answer(answer)

    assert "CREATE TABLE" not in sanitized
    assert "phone" not in sanitized
    assert "不展示" in sanitized


def test_customer_facing_step_keeps_sql_input_but_suppresses_schema_thought():
    step = {
        "thought": (
            "dim_hr_employee 表包含字段 mobile_phone、id_num，"
            "SELECT column_name FROM information_schema.columns"
        ),
        "action": "sql_query",
        "action_input": (
            '{"sql": "SELECT column_name FROM information_schema.columns '
            "WHERE table_name = 'dim_hr_employee'\"}"
        ),
        "outputs": [
            {
                "output_type": "text",
                "content": "字段名包括 mobile_phone 和 id_num",
            }
        ],
    }

    sanitized = agentic_data_api._sanitize_customer_facing_step(step)

    assert "SELECT column_name FROM information_schema.columns" in sanitized[
        "action_input"
    ]

    visible_text = str(
        {
            "thought": sanitized.get("thought"),
            "outputs": sanitized.get("outputs"),
        }
    )
    assert "dim_hr_employee" not in visible_text
    assert "mobile_phone" not in visible_text
    assert "id_num" not in visible_text
    assert "information_schema" not in visible_text
    assert "SELECT" not in visible_text
    assert "不展示" in visible_text


def test_schema_inspection_question_has_direct_customer_facing_reply():
    reply = agentic_data_api._get_direct_customer_facing_reply(
        database_name="bus_info",
        user_question="看看dim_hr_employee表字段",
    )

    assert reply is not None
    assert "不展示" in reply
    assert "dim_hr_employee" not in reply
    assert "字段" not in reply


def test_schema_inspection_question_is_blocked_before_sql_execution():
    error = agentic_data_api._validate_bus_table_policy_sql(
        database_name="bus_info",
        user_question="看看dim_hr_employee表字段",
        sql="SELECT * FROM dim_hr_employee LIMIT 4",
    )

    assert error is not None
    assert "不展示" in error
    assert "字段" not in error


def test_raw_personnel_detail_question_is_allowed_with_masking():
    error = agentic_data_api._validate_bus_table_policy_sql(
        database_name="bus_info",
        user_question="返回人员表前四行数据",
        sql=(
            "SELECT id, name, sex, department_name "
            "FROM dim_hr_employee LIMIT 4"
        ),
    )

    assert error is None


def test_sensitive_sql_result_columns_are_masked_before_display_and_memory():
    rows = [
        [
            "张三",
            "13812345678",
            "320701199001011234",
            "13987654321",
            "zhang@example.com",
            "海州区测试路1号",
            "D001",
        ]
    ]

    masked_rows = agentic_data_api._mask_sensitive_sql_rows(
        [
            "name",
            "mobile_phone",
            "id_num",
            "urgent_phone",
            "email",
            "home_address",
            "driver_code",
        ],
        rows,
    )

    assert masked_rows == [["张三", "***", "***", "***", "***", "***", "D001"]]


def test_customer_facing_answer_masks_labeled_sensitive_values():
    answer = "手机号: 13812345678，身份证号: 320701199001011234，姓名: 张三"

    sanitized = agentic_data_api._sanitize_customer_facing_answer(answer)

    assert "13812345678" not in sanitized
    assert "320701199001011234" not in sanitized
    assert "手机号: ***" in sanitized
    assert "身份证号: ***" in sanitized
    assert "张三" in sanitized


def test_sql_preview_uses_customer_facing_column_labels():
    preview = agentic_data_api._format_sql_query_markdown(
        col_names=["id", "name", "mobile_phone", "id_num"],
        rows=[["1", "张三", "***", "***"]],
        result_ref="SQL_RESULT_1",
    )

    assert "mobile_phone" not in preview
    assert "id_num" not in preview
    assert "编号" in preview
    assert "姓名" in preview
    assert "手机号" in preview
    assert "身份证号" in preview


def test_bus_operation_sql_rejects_non_ads_tables():
    error = agentic_data_api._validate_bus_table_policy_sql(
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
    error = agentic_data_api._validate_bus_table_policy_sql(
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
    error = agentic_data_api._validate_bus_table_policy_sql(
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
    assert agentic_data_api._code_uses_saved_sql_results(
        "result = get_sql_result('SQL_RESULT_1')",
        sql_results,
    )
    assert agentic_data_api._code_uses_saved_sql_results(
        "result = get_only_sql_result()",
        sql_results,
    )
    assert agentic_data_api._code_uses_saved_sql_results(
        'result = find_sql_result_by_columns(["plan_trip", "real_trip"])',
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


def test_validate_saved_sql_result_code_rejects_unknown_sql_helper():
    sql_results = [
        agentic_data_api.SqlResult(
            columns=["target_date", "plan_trip"],
            rows=[["2026-05-10", 1087.0]],
            row_count=1,
            sql="SELECT target_date, plan_trip FROM ads_ope_summary_driver_d",
        )
    ]

    error = agentic_data_api._validate_saved_sql_result_code(
        'result = find_sql_result_by_target_date("2026-05-10")',
        sql_results,
    )

    assert error is not None
    assert "find_sql_result_by_target_date" in error
    assert "get_sql_result" in error
    assert "find_sql_result_by_columns" in error


def test_validate_saved_sql_result_code_rejects_missing_sql_result_ref():
    sql_results = [
        agentic_data_api.SqlResult(
            columns=["total_plan_trip"],
            rows=[[1499.5]],
            row_count=1,
            sql="SELECT total_plan_trip",
        )
    ]

    error = agentic_data_api._validate_saved_sql_result_code(
        "result = get_sql_result('SQL_RESULT_6')\n",
        sql_results,
    )

    assert error is not None
    assert "SQL_RESULT_6" in error
    assert "SQL_RESULT_1" in error
    assert "不存在" in error


def test_validate_saved_sql_result_code_rejects_dynamic_sql_result_ref():
    sql_results = [
        agentic_data_api.SqlResult(
            columns=["total_plan_trip"],
            rows=[[1499.5]],
            row_count=1,
            sql="SELECT total_plan_trip",
        )
    ]

    error = agentic_data_api._validate_saved_sql_result_code(
        "ref = 'SQL_RESULT_1'\nresult = get_sql_result(ref)\n",
        sql_results,
    )

    assert error is not None
    assert "get_sql_result('SQL_RESULT_n')" in error
    assert "find_sql_result_by_columns" in error


def test_validate_saved_sql_result_code_rejects_missing_helper_imports():
    sql_results = [
        agentic_data_api.SqlResult(
            columns=["total_plan_trip"],
            rows=[[1499.5]],
            row_count=1,
            sql="SELECT total_plan_trip",
        )
    ]

    error = agentic_data_api._validate_saved_sql_result_code(
        "from utils import get_sql_result\nresult = get_sql_result('SQL_RESULT_1')\n",
        sql_results,
    )

    assert error is not None
    assert "utils" in error
    assert "helper 已自动注入" in error

    error = agentic_data_api._validate_saved_sql_result_code(
        "from utils.helpers import get_sql_result\n"
        "result = get_sql_result('SQL_RESULT_1')\n",
        sql_results,
    )

    assert error is not None
    assert "utils" in error

    error = agentic_data_api._validate_saved_sql_result_code(
        "from dbgpt_tools import get_sql_result\n"
        "result = get_sql_result('SQL_RESULT_1')\n",
        sql_results,
    )

    assert error is not None
    assert "dbgpt_tools" in error

    error = agentic_data_api._validate_saved_sql_result_code(
        "from sql_result_helpers import get_sql_result\n"
        "result = get_sql_result('SQL_RESULT_1')\n",
        sql_results,
    )

    assert error is not None
    assert "sql_result_helpers" in error


def test_validate_saved_sql_result_code_rejects_unknown_conversion_helper():
    sql_results = [
        agentic_data_api.SqlResult(
            columns=["dept_cnt"],
            rows=[[3]],
            row_count=1,
            sql="SELECT dept_cnt",
        )
    ]

    error = agentic_data_api._validate_saved_sql_result_code(
        """
result = get_sql_result('SQL_RESULT_1')
rows = sql_result_rows(result)
dept_cnt = to_int(require_value(rows[0], "dept_cnt"))
""",
        sql_results,
    )

    assert error is not None
    assert "to_int" in error
    assert "to_float" in error


def test_validate_saved_sql_result_code_rejects_legacy_save_helper():
    sql_results = [
        agentic_data_api.SqlResult(
            columns=["line_name", "not_disp_rate"],
            rows=[["32", 9.52]],
            row_count=1,
            sql="SELECT line_name, not_disp_rate",
        )
    ]

    error = agentic_data_api._validate_saved_sql_result_code(
        """
result = get_sql_result('SQL_RESULT_1')
rows = sql_result_rows(result)
_save(tag='report_facts', data={'top_lines': rows})
""",
        sql_results,
    )

    assert error is not None
    assert "_save" in error
    assert "save_report_facts" in error


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


def test_validate_saved_sql_result_code_allows_single_result_helper_access():
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
result = get_only_sql_result()
require_columns(result, ["total_plan_trip", "total_real_trip"])
rows = sql_result_rows(result)
total_plan = to_float(require_value(rows[0], "total_plan_trip"))
""",
        sql_results,
    )

    assert error is None


def test_validate_saved_sql_result_code_rejects_get_only_with_multiple_results():
    sql_results = [
        agentic_data_api.SqlResult(
            columns=["total_plan_trip", "total_real_trip"],
            rows=[[1499.5, 1480.5]],
            row_count=1,
            sql="SELECT total_plan_trip, total_real_trip",
        ),
        agentic_data_api.SqlResult(
            columns=["department_name", "plan_trip", "real_trip"],
            rows=[["一车队", 100, 98]],
            row_count=1,
            sql="SELECT department_name, plan_trip, real_trip",
        ),
    ]

    error = agentic_data_api._validate_saved_sql_result_code(
        """
result = get_only_sql_result()
rows = sql_result_rows(result)
total_plan = to_float(require_value(rows[0], "total_plan_trip"))
""",
        sql_results,
    )

    assert error is not None
    assert "get_only_sql_result" in error
    assert "多个 SQL_RESULT" in error


def test_validate_saved_sql_result_code_rejects_direct_row_column_access():
    sql_results = [
        agentic_data_api.SqlResult(
            columns=["department_name", "plan_trip", "real_trip"],
            rows=[["一车队", 100, 98]],
            row_count=1,
            sql="SELECT department_name, plan_trip, real_trip",
        )
    ]

    error = agentic_data_api._validate_saved_sql_result_code(
        """
result = get_sql_result('SQL_RESULT_1')
rows = sql_result_rows(result)
report_facts = {
    'department_name': rows[0]['部门名称'],
    'plan_trip': rows[0]['plan_trip'],
}
""",
        sql_results,
    )

    assert error is not None
    assert "require_value" in error
    assert "row['字段名']" in error


def test_report_scope_revision_questions_require_data_backed_render():
    assert agentic_data_api._is_report_scope_revision_question(
        "车队-东部不属于海通公交"
    )
    assert agentic_data_api._is_report_scope_revision_question("排除车队-东部")
    assert not agentic_data_api._is_report_scope_revision_question("你好")

    assert agentic_data_api._requires_data_backed_final_html(
        "车队-东部不属于海通公交"
    )
    assert agentic_data_api._requires_data_backed_final_html(
        "生成海通公交5月10日运营报告"
    )
    assert not agentic_data_api._requires_data_backed_final_html("写一个欢迎页HTML")


def test_auto_final_html_render_requires_current_data_steps_for_scope_revision():
    history_steps = [
        {
            "action": "html_interpreter",
            "outputs": [{"output_type": "html", "content": "<html></html>"}],
        }
    ]

    assert not agentic_data_api._can_auto_render_final_html(
        user_question="车队-东部不属于海通公交",
        history_steps=history_steps,
        sql_report_path="",
    )

    assert agentic_data_api._can_auto_render_final_html(
        user_question="车队-东部不属于海通公交",
        history_steps=[{"action": "sql_query", "outputs": []}],
        sql_report_path="",
    )
    assert agentic_data_api._can_auto_render_final_html(
        user_question="写一个欢迎页HTML",
        history_steps=[],
        sql_report_path="",
    )


def test_classify_html_render_chunks_rejects_text_only_validation_failure():
    chunks = [
        {
            "output_type": "text",
            "content": "报告数据未通过真实性校验，已阻止渲染。",
        }
    ]

    success, final_content = agentic_data_api._classify_html_render_chunks(chunks)

    assert not success
    assert final_content == "报告数据未通过真实性校验，已阻止渲染。"


def test_classify_html_render_chunks_accepts_html_output():
    chunks = [
        {"output_type": "html", "content": "<html><body>ok</body></html>"}
    ]

    success, final_content = agentic_data_api._classify_html_render_chunks(chunks)

    assert success
    assert final_content == "HTML运营报告已生成，请在右侧预览或下载。"


def test_format_available_columns_hint_lists_columns_for_each_ref():
    sql_results = [
        agentic_data_api.SqlResult(
            columns=["total_plan_trip", "total_real_trip"],
            rows=[[1499.5, 1480.5]],
            row_count=1,
            sql="SELECT total_plan_trip, total_real_trip",
        ),
        agentic_data_api.SqlResult(
            columns=["department_name", "plan_trip", "real_trip"],
            rows=[["一车队", 100, 98]],
            row_count=1,
            sql="SELECT department_name, plan_trip, real_trip",
        ),
    ]

    hint = agentic_data_api._format_available_columns_hint(sql_results)

    assert "当前可用 SQL 结果及其原始列名" in hint
    assert "require_value(row, '<列名>')" in hint
    assert "SQL_RESULT_1: total_plan_trip, total_real_trip" in hint
    assert (
        "SQL_RESULT_2: department_name, plan_trip, real_trip" in hint
    )


def test_format_available_columns_hint_accepts_dict_results_and_masks_sensitive():
    sql_results = [
        {
            "ref": "SQL_RESULT_1",
            "columns": ["driver_name", "mobile_phone", "id_card_no"],
            "rows": [["张三", "13800000000", "110101"]],
        }
    ]

    hint = agentic_data_api._format_available_columns_hint(sql_results)

    assert "SQL_RESULT_1" in hint
    assert "driver_name" in hint
    assert "mobile_phone" not in hint
    assert "id_card_no" not in hint
    assert hint.count("<敏感>") == 2


def test_format_available_columns_hint_truncates_after_max_columns():
    columns = [f"col_{i}" for i in range(35)]
    sql_results = [
        agentic_data_api.SqlResult(
            columns=columns,
            rows=[[0] * 35],
            row_count=1,
            sql="SELECT *",
        )
    ]

    hint = agentic_data_api._format_available_columns_hint(
        sql_results, max_columns=30
    )

    assert "col_0" in hint
    assert "col_29" in hint
    assert "col_30" not in hint
    assert "...还有 5 列" in hint


def test_format_available_columns_hint_skips_results_without_columns():
    sql_results = [
        agentic_data_api.SqlResult(
            columns=[], rows=[], row_count=0, sql="SELECT 1"
        )
    ]

    assert agentic_data_api._format_available_columns_hint(sql_results) == ""
    assert agentic_data_api._format_available_columns_hint([]) == ""


def test_validate_saved_sql_result_code_error_includes_columns_hint():
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
result = get_sql_result('SQL_RESULT_1')
rows = sql_result_rows(result)
report_facts = {
    'plan': rows[0]['total_plan_trip'],
}
""",
        sql_results,
    )

    assert error is not None
    assert "当前可用 SQL 结果及其原始列名" in error
    assert "SQL_RESULT_1: total_plan_trip, total_real_trip" in error


def test_sql_query_results_helpers_expose_sql_result_columns():
    namespace: dict = {
        "SQL_QUERY_RESULTS": [
            {
                "ref": "SQL_RESULT_1",
                "columns": ["department_name", "plan_trip", "real_trip"],
                "rows": [["一车队", 282.0, 282.0]],
            }
        ]
    }
    exec(agentic_data_api._sql_query_results_helper_preamble(), namespace)

    result = namespace["get_only_sql_result"]()
    columns = namespace["sql_result_columns"](result)

    assert columns == ["department_name", "plan_trip", "real_trip"]
    assert namespace["sql_result_columns"]({}) == []
    assert namespace["sql_result_columns"]({"columns": None}) == []


def test_validate_saved_sql_result_code_rejects_direct_sql_html_write():
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
html = "<div>建议加强驾驶员管理</div>"
with open("/tmp/report.html", "w", encoding="utf-8") as f:
    f.write(html)
""",
        sql_results,
    )

    assert error is not None
    assert "write_sql_report_html" in error
    assert "report_facts" in error


def test_validate_saved_sql_result_code_allows_fact_pack_report_writer():
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
report_facts = {
    "total_plan_trip": to_float(require_value(rows[0], "total_plan_trip")),
    "total_real_trip": to_float(require_value(rows[0], "total_real_trip")),
}
html = "<div>" + str(report_facts["total_plan_trip"]) + "</div>"
write_sql_report_html("/tmp/report.html", html, report_facts)
""",
        sql_results,
    )

    assert error is None


def test_validate_saved_sql_result_code_rejects_saving_facts_without_sql_source():
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
report_facts = {"total_plan_trip": 1499.5, "total_real_trip": 1480.5}
save_report_facts(report_facts)
""",
        sql_results,
    )

    assert error is not None
    assert "save_report_facts" in error
    assert "SQL_RESULT" in error


def test_validate_saved_sql_result_code_allows_loading_saved_report_facts():
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
report_facts = load_report_facts()
html = "<div>" + str(report_facts["total_plan_trip"]) + "</div>"
write_sql_report_html("/tmp/report.html", html, report_facts)
""",
        sql_results,
    )

    assert error is None


def test_validate_saved_sql_result_code_rejects_report_facts_used_before_load():
    sql_results = [
        agentic_data_api.SqlResult(
            columns=["total_plan_trip"],
            rows=[[1499.5]],
            row_count=1,
            sql="SELECT total_plan_trip",
        )
    ]

    error = agentic_data_api._validate_saved_sql_result_code(
        """
html = "<div>" + str(report_facts["total_plan_trip"]) + "</div>"
write_sql_report_html("/tmp/report.html", html, report_facts)
""",
        sql_results,
    )

    assert error is not None
    assert "report_facts" in error
    assert "load_report_facts" in error


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

    (tmp_path / "report.html.facts.json").write_text("{}", encoding="utf-8")

    trusted = agentic_data_api._updated_sql_backed_report_files(
        existing_files=[],
        candidate_paths=[str(report)],
        signatures_before={str(report): before},
        uses_saved_sql_results=True,
        return_code=0,
    )

    assert trusted == [str(report)]


def test_update_sql_backed_report_files_requires_report_facts_sidecar(tmp_path):
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

    assert trusted == []


def test_sql_query_results_example_uses_column_names_not_guessed_indexes():
    example = agentic_data_api._sql_query_results_access_example()

    assert "find_sql_result_by_columns" in example
    assert "sql_result_rows(result)" in example
    assert "require_columns" in example
    assert "data[0]" not in example
    assert 'row.get("total_value")' not in example
    assert "row[col_idx]" not in example


def test_sql_query_results_example_uses_fact_pack_report_writer():
    example = agentic_data_api._sql_query_results_access_example()

    assert "report_facts" in example
    assert "write_sql_report_html" in example


def test_sql_report_prompts_do_not_encourage_raw_sql_query_results_access():
    source = inspect.getsource(agentic_data_api)

    assert "读取 SQL_QUERY_RESULTS" not in source
    assert "data = SQL_QUERY_RESULTS" not in source
    assert "get_only_sql_result()" in source


def test_workflow_prompt_report_facts_example_escapes_fstring_braces():
    source = inspect.getsource(agentic_data_api)

    assert "report_facts = {{" in source
    assert (
        '"scope_note": "HTML conclusions may only use these facts.",\n      }}'
        in source
    )


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


def test_sql_query_results_helpers_get_only_result_for_single_sql_result():
    namespace: dict = {
        "SQL_QUERY_RESULTS": [
            {
                "ref": "SQL_RESULT_1",
                "columns": ["total_plan_trip", "total_real_trip"],
                "rows": [[1499.5, 1480.5]],
            }
        ]
    }
    exec(agentic_data_api._sql_query_results_helper_preamble(), namespace)

    result = namespace["get_only_sql_result"]()

    assert result["ref"] == "SQL_RESULT_1"


def test_sql_query_results_helpers_get_only_result_rejects_multiple_results():
    namespace: dict = {
        "SQL_QUERY_RESULTS": [
            {"ref": "SQL_RESULT_1", "columns": ["total_plan_trip"], "rows": [[1]]},
            {"ref": "SQL_RESULT_2", "columns": ["plan_trip"], "rows": [[1]]},
        ]
    }
    exec(agentic_data_api._sql_query_results_helper_preamble(), namespace)

    try:
        namespace["get_only_sql_result"]()
    except ValueError as exc:
        assert "Multiple SQL results" in str(exc)
    else:
        raise AssertionError("multiple SQL results should require explicit selection")


def test_sql_query_results_helpers_save_and_load_report_facts(tmp_path):
    namespace: dict = {
        "SQL_QUERY_RESULTS": [
            {
                "ref": "SQL_RESULT_1",
                "columns": ["total_plan_trip"],
                "rows": [[1499.5]],
            }
        ],
        "PLOT_DIR": str(tmp_path),
        "os": __import__("os"),
        "json": __import__("json"),
    }
    exec(agentic_data_api._sql_query_results_helper_preamble(), namespace)

    facts = {"total_plan_trip": 1499.5}
    saved_path = namespace["save_report_facts"](facts)
    loaded = namespace["load_report_facts"]()

    assert loaded == facts
    payload = __import__("json").loads(
        __import__("pathlib").Path(saved_path).read_text(encoding="utf-8")
    )
    assert payload["source_refs"] == ["SQL_RESULT_1"]


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
