# ruff: noqa: F811
import copy
from types import SimpleNamespace

import pytest

from dbgpt_app.openapi.api_v1.dashboard.catalog import (
    TEMPLATES,
    build_template,
    preview_template,
)
from dbgpt_app.openapi.api_v1.dashboard.catalog_ai import (
    TemplateAdaptRequest,
    adapt_template,
    validate_adaptation_promises,
)
from dbgpt_app.openapi.api_v1.dashboard.catalog_identity import IDENTITIES
from dbgpt_app.openapi.api_v1.dashboard.chart_semantics import validate_stacked_measures
from dbgpt_app.openapi.api_v1.dashboard.schemas import DashboardSchemaV1

from .test_catalog_ai import Model, plan
from .test_catalog_workspace import mapped_source  # noqa: F401
from .test_feedback import real_service  # noqa: F401


def chart(sql, visual="stacked_column"):
    return SimpleNamespace(
        title="渠道构成",
        presentation=SimpleNamespace(
            stacked=False, visualization=SimpleNamespace(value=visual)
        ),
        query=SimpleNamespace(sql=sql),
        encoding=SimpleNamespace(y="value"),
    )


@pytest.mark.parametrize(
    "measure", ["SUM(amount)", "SUM(amount)/COUNT(id)", "AVG(amount)"]
)
def test_rejects_incompatible_measures_in_actual_union_projections(measure):
    sql = (
        f"SELECT channel, '收入' AS kind, {measure} AS val"
        f"ue FROM sales GROUP BY channel UNION ALL SELECT "
        f"channel, '记录数', COUNT(id) AS value FROM sales"
        f" GROUP BY channel"
    )
    with pytest.raises(ValueError, match="不能相加"):
        validate_stacked_measures(chart(sql), "sqlite")


def test_accepts_comparable_series_and_separate_chart_axes():
    sql = (
        "SELECT month, '社群' AS kind, SUM(amount) AS val"
        "ue FROM sales GROUP BY month UNION ALL SELECT mo"
        "nth, '门店', SUM(amount) AS value FROM sales GRO"
        "UP BY month"
    )
    validate_stacked_measures(chart(sql), "sqlite")
    validate_stacked_measures(
        chart(sql.replace("SUM(amount)", "COUNT(id)", 1), "dual_axis"), "sqlite"
    )


@pytest.mark.parametrize(
    "prompt,changes",
    [
        ("添加渠道单选筛选器", []),
        ("生成销售看板", ["新增渠道单选全局筛选器 channel_filter，已绑定所有组件"]),
    ],
)
def test_empty_filters_cannot_satisfy_request_or_model_claim(
    mapped_source, prompt, changes
):
    service, _, mapping = mapped_source
    schema = DashboardSchemaV1.model_validate(
        preview_template(
            service, "retail-overview", "renamed", "alice", mapping("retail-overview")
        )["schema"]
    )
    schema.filters = []
    schema.metadata.compatibility["template_adaptation"] = {
        "prompt": prompt,
        "changes": changes,
    }
    with pytest.raises(ValueError, match="filters 为空"):
        validate_adaptation_promises(schema)


def test_filter_claims_must_refer_to_real_bound_objects(mapped_source):
    service, _, mapping = mapped_source
    schema = DashboardSchemaV1.model_validate(
        preview_template(
            service, "retail-overview", "renamed", "alice", mapping("retail-overview")
        )["schema"]
    )
    schema.metadata.compatibility["template_adaptation"] = {
        "changes": ["新增筛选器 channel_filter"]
    }
    with pytest.raises(ValueError, match="不存在"):
        validate_adaptation_promises(schema)
    schema.metadata.compatibility["template_adaptation"] = {}
    for widget in schema.widgets:
        widget.query.filter_parameters = {}
    with pytest.raises(ValueError, match="没有绑定"):
        validate_adaptation_promises(schema)
    schema.filters = []
    schema.metadata.compatibility["template_adaptation"] = {
        "prompt": "不要添加任何筛选器",
        "changes": ["未添加筛选器"],
    }
    validate_adaptation_promises(schema)


@pytest.mark.asyncio
async def test_model_must_repair_omitted_filter_before_preview_is_accepted(
    mapped_source,
):
    service, _, mapping = mapped_source
    valid = plan(
        preview_template(
            service, "retail-overview", "renamed", "alice", mapping("retail-overview")
        )
    )
    invalid = copy.deepcopy(valid)
    invalid["filters"] = []
    model = Model([invalid, valid])
    before = service.list_dashboard_page("alice").total
    result = await adapt_template(
        service,
        "retail-overview",
        "alice",
        TemplateAdaptRequest(
            data_source_id="renamed",
            model="test",
            prompt="请保留全局筛选器并使用真实数据",
        ),
        model,
    )
    assert len(model.calls) == 2
    assert "filters 为空" in model.calls[1].messages[-1].content
    assert result["schema"]["filters"]
    assert service.list_dashboard_page("alice").total == before


def test_template_identities_keep_all_slots_and_avoid_overlap():
    for template in TEMPLATES:
        if template["id"] not in IDENTITIES:
            continue
        schema = build_template(template["id"], template["source"])
        assert schema.metadata.compatibility["catalog_visual_revision"] == 2
        assert schema.dashboard.theme.overrides.primary_color
        layouts = schema.layouts.desktop
        assert {b.widget_id for b in layouts} == {w.id for w in schema.widgets}
        for i, box in enumerate(layouts):
            assert box.x >= 0 and box.x + box.w <= 12
            for other in layouts[i + 1 :]:
                assert (
                    box.x + box.w <= other.x
                    or other.x + other.w <= box.x
                    or box.y + box.h <= other.y
                    or other.y + other.h <= box.y
                )


@pytest.mark.asyncio
async def test_filtered_adaptation_must_repair_missing_share_binding(mapped_source):
    service, _, mapping = mapped_source
    valid = plan(
        preview_template(
            service, "retail-overview", "renamed", "alice", mapping("retail-overview")
        )
    )
    broken = copy.deepcopy(valid)
    broken["widgets"][0]["publication"] = None
    model = Model([broken, valid])
    result = await adapt_template(
        service,
        "retail-overview",
        "alice",
        TemplateAdaptRequest(
            data_source_id="renamed", model="test", prompt="保留全局筛选器"
        ),
        model,
    )
    assert len(model.calls) == 2
    assert "frozen-data publication binding" in model.calls[-1].messages[-1].content
    assert result["schema"]["widgets"][0]["publication"]
