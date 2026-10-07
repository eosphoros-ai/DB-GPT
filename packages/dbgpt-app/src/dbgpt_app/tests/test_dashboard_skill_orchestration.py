from pathlib import Path

from dbgpt.agent.claude_skill import FileBasedSkill
from dbgpt_app.openapi.api_v1.agentic_data_api import (
    DASHBOARD_BUILDER_SKILL_NAME,
    _is_dashboard_workflow_request,
    _is_read_only_dashboard_annotation_request,
)


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
