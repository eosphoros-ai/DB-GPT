from copy import deepcopy

from dbgpt_app.openapi.api_v1.dashboard.gallery_templates import (
    design_skill_root,
    gallery_plan_context,
)
from dbgpt_app.openapi.api_v1.dashboard.skill_context import (
    confirmed_gallery_context,
    confirmed_skill_instructions,
    planning_skill_instructions,
)


def test_confirmed_skill_keeps_shared_sql_and_business_safeguards():
    skill = (design_skill_root().parents[1] / "SKILL.md").read_text("utf-8")
    focused = confirmed_skill_instructions(skill)
    assert "## New dashboard: plan first" not in focused
    assert "## Selection-aware annotation" not in focused
    assert "## Confirmed plan: generate queries" in focused
    assert "## Preconditions" in focused
    assert "## Completion checks" in focused
    # These rules must survive prompt reduction, including frozen filters and
    # genuinely empty periods rather than silently substituting available data.
    assert "never truncate source" in focused
    assert "or average averages" in focused
    assert "Never concatenate user values into SQL" in focused
    assert "expected_data_points: 0" in focused
    assert "Preserve successful widgets" in focused
    assert "ownership" in focused


def test_planning_keeps_scope_and_data_checks_without_query_payload_instructions():
    skill = (design_skill_root().parents[1] / "SKILL.md").read_text("utf-8")
    focused = planning_skill_instructions(skill)
    assert "## New dashboard: plan first" in focused
    assert "## Confirmed plan: generate queries" not in focused
    assert "## Selection-aware annotation" not in focused
    assert "distinct-key overlap, unmatched rows" in focused
    assert "expected_data_points: 0" in focused
    assert "Never call `create_dashboard_draft` in the planning turn" in focused
    assert "## Filter rules" in focused
    assert "## Completion checks" in focused


def test_new_shared_rules_are_not_dropped_by_phase_selection():
    skill = (
        "Custom preamble\n## New dashboard: plan first\nDiscovery only.\n"
        "## Confirmed plan: generate queries\nGenerate SQL.\n"
        "## New access rule\nAlways enforce data scope.\n"
    )
    focused = confirmed_skill_instructions(skill)
    assert focused.startswith("Custom preamble\n")
    assert "Discovery only" not in focused
    assert "Always enforce data scope" in focused


def test_unrecognized_custom_skill_keeps_complete_instructions():
    skill = "## New dashboard: plan first\nCustom generation and safety rules.\n"
    assert confirmed_skill_instructions(skill) == skill


def test_confirmed_gallery_does_not_repeat_reference_metrics_or_mutate_selection():
    context = gallery_plan_context("catalog:store-marketing")
    original = deepcopy(context)
    focused = confirmed_gallery_context(context)
    assert focused["selection"] == "catalog:store-marketing"
    assert focused["skill"] == "dashboard-design"
    assert "widgets" not in focused
    assert "confirmed plan" in focused["instruction"]
    assert "preserves its layout and colors" in focused["instruction"]
    assert context == original
