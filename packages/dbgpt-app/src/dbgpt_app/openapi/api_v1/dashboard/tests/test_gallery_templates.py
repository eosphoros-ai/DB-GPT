import pytest

from dbgpt_app.openapi.api_v1.dashboard.gallery_templates import (
    design_skill_root,
    gallery_plan_context,
    is_internal_dashboard_skill,
    load_gallery_reference,
    resolve_gallery_selection,
)
from dbgpt_app.openapi.api_v1.dashboard.planner import DashboardPlannerService
from dbgpt_app.openapi.api_v1.dashboard.schemas import (
    DashboardLayouts,
    DashboardPlan,
    DashboardQueryDraftRequest,
    DashboardVisualTheme,
)

from .test_feedback import real_service as _real_service_fixture

real_service = _real_service_fixture

ACTIVE_SELECTIONS = (
    "design:brutal-viz-design",
    "design:serenityspa-viz-design",
    "catalog:voice-observatory",
    "catalog:store-marketing",
    "catalog:national-command",
    "catalog:brand-revenue",
    "catalog:northwind-revenue",
    "catalog:retail-overview",
)


def test_reference_files_are_exactly_the_eight_retained_templates():
    assert {p.name for p in (design_skill_root() / "references").glob("*.md")} == {
        "index.md",
        *(selection.replace(":", "-") + ".md" for selection in ACTIVE_SELECTIONS),
    }


def test_removed_templates_cannot_be_loaded_by_legacy_ids():
    from dbgpt_app.openapi.api_v1.dashboard.catalog import TEMPLATES

    removed = {"catalog:" + item["id"] for item in TEMPLATES} - set(ACTIVE_SELECTIONS)
    removed.update(
        "design:" + name
        for name in (
            "antv-g2-chart",
            "datapulse-viz-design",
            "learnhub-viz-design",
            "nexusai-viz-design",
            "pawspa-viz-design",
        )
    )
    assert len(removed) == 33
    for selection in removed:
        with pytest.raises(ValueError, match="Unknown gallery"):
            gallery_plan_context(selection)


@pytest.mark.parametrize("name", ["../../private", "学习", "unknown style"])
def test_style_names_do_not_fuzzily_select_another_reference(name):
    with pytest.raises(ValueError):
        resolve_gallery_selection(name)


def test_ambiguous_style_name_requires_explicit_selection(monkeypatch):
    from dbgpt_app.openapi.api_v1.dashboard import gallery_templates

    monkeypatch.setattr(
        gallery_templates,
        "available_gallery_styles",
        lambda: "- `catalog:one` — [Same](one.md)\n- `catalog:two` — [Same](two.md)",
    )
    with pytest.raises(ValueError, match="ambiguous"):
        resolve_gallery_selection("Same")
    assert resolve_gallery_selection("catalog:one") == "catalog:one"


def selected_plan(selection):
    return DashboardPlan.model_validate(
        {
            "title": "Actual sales",
            "business_theme": "Sales",
            "metrics": ["Revenue"],
            "widgets": [
                {
                    "id": item["id"],
                    "type": "kpi",
                    "title": "Revenue " + item["id"],
                    "business_question": "How much revenue?",
                    "metric": "Revenue",
                }
                for item in gallery_plan_context(selection)["widgets"]
            ],
        }
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "selection,retired",
    [(selection, False) for selection in ACTIVE_SELECTIONS]
    + [("design:serenityspa-viz-design", True)],
)
async def test_gallery_survives_plan_revision_and_confirmed_generation(
    real_service, selection, retired
):
    service, _, _ = real_service
    planner = DashboardPlannerService(service)
    plan = selected_plan(selection)
    reference = load_gallery_reference(selection)
    pending = await planner.create_plan_draft(
        plan=plan,
        data_source_id="test",
        owner_id="alice",
        conversation_id="gallery",
        prompt="Use this template",
        model_name="test",
        request_token="plan",
        gallery_template=selection,
    )
    if retired:
        # Reproduce an old persisted plan whose reference no longer ships.
        selection = "design:pawspa-viz-design"
        saved = pending.schema_payload.model_copy(deep=True)
        saved.metadata.compatibility["gallery_template"] = selection
        pending = service.update_agent_dashboard(
            pending.id, saved, pending.current_revision, "alice"
        )
        with pytest.raises(ValueError, match="Unknown gallery"):
            load_gallery_reference(selection)
    original_layout = pending.schema_payload.layouts.model_dump()
    original_theme = pending.schema_payload.dashboard.theme.model_dump()
    plan.title = "Revised sales"
    revised = await planner.revise_plan_draft(
        dashboard_id=pending.id,
        plan=plan,
        expected_revision=pending.current_revision,
        owner_id="alice",
        request_token="revise",
        prompt="Change title",
        model_name="test",
    )
    assert revised.schema_payload.layouts.model_dump() == original_layout
    request = DashboardQueryDraftRequest.model_validate(
        {
            "expected_revision": revised.current_revision,
            "widgets": [
                {
                    "widget_id": w.id,
                    "sql": "SELECT SUM(amount) AS value FROM sales",
                    "output_fields": [{"name": "value", "type": "number"}],
                    "encoding": {"value": "value"},
                }
                for w in plan.widgets
            ],
        }
    )
    generated, results = await planner.complete_plan_draft(
        dashboard_id=revised.id,
        query_request=request,
        owner_id="alice",
        request_token="confirm",
    )
    reopened = service.get_dashboard(generated.id, "alice").schema_payload
    assert reopened.layouts.model_dump() == original_layout
    assert reopened.dashboard.theme.model_dump() == original_theme
    assert reopened.dashboard.title == "Revised sales"
    assert reopened.metadata.compatibility["gallery_template"] == selection
    assert all(
        result.rows == [[30]] and not result.error for result in results.values()
    )
    assert all(widget.query.data_source_id == "test" for widget in reopened.widgets)
    assert all("target" not in widget.style for widget in reopened.widgets)
    repaired, _ = await planner.repair_draft(
        dashboard_id=generated.id,
        plan=plan,
        query_request=request.model_copy(update={"widgets": request.widgets[:1]}),
        owner_id="alice",
    )
    assert repaired.schema_payload.layouts == reopened.layouts
    assert repaired.schema_payload.widgets[0].style == reopened.widgets[0].style
    assert (
        repaired.schema_payload.widgets[0].presentation.colors
        == reopened.widgets[0].presentation.colors
    )
    assert reopened.layouts == DashboardLayouts.model_validate(reference["layouts"])
    assert reopened.dashboard.theme == DashboardVisualTheme.model_validate(
        reference["theme"]
    )
    assert reopened.metadata.compatibility["gallery_skill"] == "dashboard-design"


def test_template_slots_cannot_be_silently_replaced():
    plan = selected_plan("design:serenityspa-viz-design")
    plan.widgets.pop()
    with pytest.raises(ValueError, match="slot ids"):
        DashboardPlannerService(None)._build_schema(
            plan=plan,
            query_map={},
            data_source_id="test",
            conversation_id=None,
            prompt=None,
            model_name=None,
            compatibility={"gallery_template": "design:serenityspa-viz-design"},
        )


@pytest.mark.parametrize(
    "selection", ["catalog:missing", "design:missing", "../../secret"]
)
def test_unknown_template_is_rejected(selection):
    with pytest.raises(ValueError, match="Unknown gallery"):
        gallery_plan_context(selection)


def test_every_active_catalog_style_has_a_reference_without_data_queries():
    from dbgpt_app.openapi.api_v1.dashboard.catalog import build_template

    for selection in ACTIVE_SELECTIONS:
        if not selection.startswith("catalog:"):
            continue
        reference = load_gallery_reference(selection)
        original = build_template(selection.removeprefix("catalog:"), "test")
        assert DashboardLayouts.model_validate(reference["layouts"]) == original.layouts
        assert [w["id"] for w in reference["widgets"]] == [
            w.id for w in original.widgets
        ]
        assert all(
            "query" not in w and "target" not in w["style"]
            for w in reference["widgets"]
        )
        assert "demo_source" not in reference["compatibility"]["catalog_presentation"]


def test_loading_style_reads_only_its_skill_guidance_and_no_other_reference(
    monkeypatch,
):
    from pathlib import Path

    reads = []
    original_read = Path.read_text

    def tracked_read(path, *args, **kwargs):
        reads.append(path)
        return original_read(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", tracked_read)
    context = gallery_plan_context("design:serenityspa-viz-design")
    assert context["skill"] == "dashboard-design"
    assert "美业预约管理" in context["instruction"]
    assert len(reads) == 4  # The active index, chosen reference and its two guides.
    assert all("brutal" not in str(path) for path in reads)
    assert context["reference"] == "references/design-serenityspa-viz-design.md"


def test_internal_skills_remain_loadable_without_being_standalone_tasks():
    from dbgpt.agent.skill.loader import SkillLoader

    root = design_skill_root().parents[2]
    skills = SkillLoader().load_skills_from_directory(str(root))
    internal = [
        s for s in skills if is_internal_dashboard_skill(s._config.get("file_path", ""))
    ]
    assert {s.metadata.name for s in internal} == {
        "dashboard-design",
        "antv-g2-chart",
        "brutal-viz-design",
        "serenityspa-viz-design",
        "dashboard-chart-configuration",
        "dashboard-filter-configuration",
        "dashboard-collaboration",
    }
    assert not is_internal_dashboard_skill("skills/csv-data-analysis/SKILL.md")
