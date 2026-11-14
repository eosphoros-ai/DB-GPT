from pathlib import Path

from dbgpt.agent.claude_skill import FileBasedSkill
from dbgpt_app.openapi.api_v1.agentic_data_api import (
    DASHBOARD_BUILDER_SKILL_NAME,
    _is_dashboard_workflow_request,
    _is_read_only_dashboard_annotation_request,
)
from dbgpt_app.openapi.api_v1.suite_binder import SuiteBinding, bind_command
from dbgpt_serve.plugins.loader import load_suite_dir


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[5]


def test_dashboard_intent_recognizes_requests_and_confirmation_markers():
    assert _is_dashboard_workflow_request("请根据当前数据库生成经营看板")
    assert _is_dashboard_workflow_request("生成 Apple 财务看板")
    assert _is_dashboard_workflow_request("Create a sales dashboard")
    assert _is_dashboard_workflow_request("[[confirm-dashboard:dashboard-1]] 确认生成")
    assert _is_dashboard_workflow_request(
        "[[dashboard-annotation:annotation-1]] 请只修改选中的图表"
    )
    assert not _is_dashboard_workflow_request("查询本月总销售额")
    assert not _is_dashboard_workflow_request("解释这个仪表盘里的收入为什么下降")
    assert not _is_dashboard_workflow_request("Query sales data for the dashboard")
    assert _is_dashboard_workflow_request("展示年度收入", creation_mode="dashboard")


def test_read_only_annotation_intent_is_distinct_from_modification():
    assert _is_read_only_dashboard_annotation_request(
        "[[dashboard-annotation:dash-1:a-1]] [异常分析] 收入趋势"
    )
    assert _is_read_only_dashboard_annotation_request(
        "[[dashboard-annotation:dash-1:a-2]] 本批次没有修改类批注，不要修改看板。"
    )
    assert not _is_read_only_dashboard_annotation_request(
        "[[dashboard-annotation:dash-1:a-3]] [修改组件] 右边那个改一下"
    )
    assert not _is_read_only_dashboard_annotation_request("请解释本月收入")


def test_native_analysis_dashboard_command_selects_workflow_and_preloads_evidence():
    root = _repository_root() / "assets/suites/db-analysis"
    package = load_suite_dir(root)
    binding = SuiteBinding(
        name=package.name,
        version=package.version,
        package_path=str(root),
        package_format=package.manifest["package_format"],
        commands=package.manifest["commands"],
        skills=package.manifest["skills"],
    )
    bind_command(binding, "/dashboard")
    assert binding.command_skill == "build-dashboard"
    assert not binding.command_error
    assert _is_dashboard_workflow_request(
        "按周监控销售与门店表现", suite_binding=binding
    )
    assert {item["path"] for item in binding.loaded_documents} == {
        "skills/build-dashboard/SKILL.md",
        "skills/build-dashboard/references/connector-readiness.md",
        "skills/build-dashboard/references/data-quality.md",
        "skills/build-dashboard/references/evidence-card.md",
    }
    bind_command(binding, "/build-dashboard")
    assert binding.command == "/dashboard"
    binding.command_error = "required skill missing"
    assert not _is_dashboard_workflow_request(
        "按周监控销售与门店表现", suite_binding=binding
    )
    bind_command(binding, "/analyze")
    assert not _is_dashboard_workflow_request("生成销售分析报告", suite_binding=binding)


def test_analysis_examples_have_explicit_valid_commands_and_dashboard_gate():
    package = load_suite_dir(_repository_root() / "assets/suites/db-analysis")
    commands = {command["name"] for command in package.manifest["commands"]}
    questions = package.snapshot["recommended_questions"]
    assert all(question.get("command") in commands for question in questions)
    dashboard_example = next(q for q in questions if q["command"] == "/dashboard")
    assert dashboard_example["database_name"] == "Walmart_Sales"
    assert dashboard_example["text_en"]
    allowed = set(package.snapshot["tools"]["allow"])
    assert {
        "plan_dashboard",
        "create_dashboard_draft",
        "repair_dashboard_draft",
        "revise_dashboard_plan",
        "load_dashboard_draft",
        "modify_dashboard_draft",
        "propose_dashboard_change",
    } <= allowed


def test_dashboard_builder_skill_declares_orchestration_contract():
    skill_file = (
        _repository_root() / "skills" / DASHBOARD_BUILDER_SKILL_NAME / "SKILL.md"
    )
    content = skill_file.read_text(encoding="utf-8")
    skill = FileBasedSkill(str(skill_file))

    assert skill.metadata.name == DASHBOARD_BUILDER_SKILL_NAME
    assert "orchestrates" in skill.instructions
    assert f"name: {DASHBOARD_BUILDER_SKILL_NAME}" in content
    assert "plan_dashboard" in content
    assert "create_dashboard_draft" in content
    assert "repair_dashboard_draft" in content
    assert "modify_dashboard_draft" in content
    assert "propose_dashboard_change" in content
    assert content.index("plan_dashboard") < content.index("create_dashboard_draft")
    assert "Never call `create_dashboard_draft` in the planning turn" in content
    assert "Never replace this\nworkflow with a one-off HTML report" in content
    assert "inventory every\n   source table" in content
    assert "candidate keys with distinct-key overlap, unmatched rows" in content
    assert "one-to-one/one-to-many/many-to-many cardinality checks" in content
    assert "join diagnostics show no unexplained fan-out" in content
    assert "Selection-aware annotation" in content
    assert "For `[指标解释]` or `[异常分析]`" in content
    assert "never run SQL" in content
