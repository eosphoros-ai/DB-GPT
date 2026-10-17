import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from dbgpt_app.openapi.api_v1.dashboard import release_features
from dbgpt_app.openapi.api_v1.dashboard.layout_templates import (
    LAYOUT_TEMPLATES,
    template_layout,
)
from dbgpt_app.openapi.api_v1.dashboard.planner import (
    DashboardPlannerService,
    _merge_plan_revision_context,
)
from dbgpt_app.openapi.api_v1.dashboard.schemas import (
    DashboardLayoutTemplate,
    DashboardPlan,
)

CASES = json.loads(
    (Path(__file__).parent / "layout-template-cases.json").read_text(encoding="utf-8")
)


def plan_payload():
    return {
        "title": "Operating health",
        "business_theme": "Prioritize intervention",
        "metrics": ["Sales"],
        "widgets": [
            dict(
                item,
                title=item["id"],
                business_question="What changed?",
                metric="Sales",
            )
            for item in CASES["widgets"]
        ],
    }


def build(plan):
    return DashboardPlannerService(None)._build_schema(
        plan=plan,
        query_map={},
        data_source_id="sales",
        conversation_id="layout-test",
        prompt="Plan only",
        model_name="test",
    )


@pytest.mark.parametrize("template_id", LAYOUT_TEMPLATES)
def test_plan_template_matches_browser_fixture_and_preserves_queries(
    template_id, monkeypatch
):
    # Retained implementation coverage, not acceptance of an enabled feature.
    monkeypatch.setattr(release_features, "LAYOUT_TEMPLATES_ENABLED", True)
    custom = build(DashboardPlan.model_validate(plan_payload()))
    payload = dict(plan_payload(), layout_template=template_id)
    planned = DashboardPlan.model_validate(payload)
    schema = build(planned)
    assert [
        [item.widget_id, item.x, item.y, item.w, item.h]
        for item in schema.layouts.desktop
    ] == CASES["expected"][template_id]
    assert schema.widgets == custom.widgets
    assert schema.filters == custom.filters
    assert (
        schema.dashboard.theme.model_dump(mode="json", exclude_none=True)
        == LAYOUT_TEMPLATES[template_id]["theme"]
    )
    assert (
        schema.metadata.compatibility["dashboard_plan"]["layout_template"]
        == template_id
    )
    assert schema.schema_version == "1.4"


@pytest.mark.parametrize("template_id", LAYOUT_TEMPLATES)
def test_layout_degrades_for_missing_widget_types_without_overlap(template_id):
    base = build(DashboardPlan.model_validate(plan_payload())).widgets
    for count in range(25):
        for source in ([base[0]], [base[1]], [base[-1]], base):
            widgets = [
                source[i % len(source)].model_copy(update={"id": f"widget-{i}"})
                for i in range(count)
            ]
            items = template_layout(widgets, template_id).desktop
            assert len({item.widget_id for item in items}) == count
            for i, item in enumerate(items):
                assert item.x + item.w <= 12
                assert item.w >= item.min_w and item.h >= item.min_h
                for other in items[i + 1 :]:
                    assert not (
                        item.x < other.x + other.w
                        and other.x < item.x + item.w
                        and item.y < other.y + other.h
                        and other.y < item.y + item.h
                    )


def test_template_is_allowlisted_and_revision_can_keep_change_or_clear_it(monkeypatch):
    monkeypatch.setattr(release_features, "LAYOUT_TEMPLATES_ENABLED", True)
    assert {item.value for item in DashboardLayoutTemplate} == set(LAYOUT_TEMPLATES)
    original = DashboardPlan.model_validate(
        dict(plan_payload(), layout_template="trend-focus")
    )
    omitted = DashboardPlan.model_validate(plan_payload())
    changed = DashboardPlan.model_validate(
        dict(plan_payload(), layout_template="operations-detail")
    )
    cleared = DashboardPlan.model_validate(dict(plan_payload(), layout_template=None))
    assert (
        _merge_plan_revision_context(original, omitted).layout_template == "trend-focus"
    )
    assert (
        _merge_plan_revision_context(original, changed).layout_template
        == "operations-detail"
    )
    assert _merge_plan_revision_context(original, cleared).layout_template is None
    with pytest.raises(ValidationError):
        DashboardPlan.model_validate(dict(plan_payload(), layout_template="unknown"))


def test_released_plan_omits_layout_selection_and_does_not_apply_its_theme():
    assert not release_features.layout_templates_enabled()
    payload = dict(plan_payload(), layout_template="operations-detail")
    legacy = DashboardPlan.model_validate(payload)
    assert legacy.layout_template == "operations-detail"  # Still readable.
    assert "layout_template" not in legacy.model_dump(mode="json")
    assert "layout_template" not in legacy.model_dump_json()
    schema = build(legacy)
    baseline = build(DashboardPlan.model_validate(plan_payload()))
    assert schema.layouts == baseline.layouts
    assert schema.dashboard.theme == baseline.dashboard.theme
    assert "layout_template" not in schema.metadata.compatibility["dashboard_plan"]
    assert payload["layout_template"] == "operations-detail"  # Never rewrite input.


def test_released_plan_contract_does_not_offer_layout_families():
    from dbgpt_app.openapi.api_v1.tools.dashboard_contracts import (
        validation_model_contracts,
    )

    contract = validation_model_contracts([DashboardPlan])
    assert "layout_template" not in contract
    assert "DashboardLayoutTemplate" not in contract
    assert "layout?: DashboardPlanWidgetLayout" in contract
