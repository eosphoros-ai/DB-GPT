# Imported pytest fixtures are injected as arguments below.
# ruff: noqa: F811
import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from dbgpt_app.openapi.api_v1.dashboard.annotation_generation import (
    AnnotationGenerationRequest,
    generate_annotation_proposal,
    proposal_messages,
)
from dbgpt_app.openapi.api_v1.dashboard.collaboration import DashboardPatchError
from dbgpt_app.openapi.api_v1.dashboard.models import DashboardAccessDeniedError
from dbgpt_app.openapi.api_v1.dashboard.schemas import DashboardAnnotationCreateRequest

from .test_annotations import annotation_services  # noqa: F401


@pytest.fixture(autouse=True)
def threaded_metadata(tmp_path, monkeypatch):
    # Match production's file-backed SQLite across the generator's worker threads.
    from dbgpt.storage.metadata import DatabaseManager

    original = DatabaseManager.init_db

    def initialize(self, db_url, *args, **kwargs):
        if db_url == "sqlite:///:memory:":
            db_url = "sqlite:///" + (tmp_path / "metadata.db").as_posix()
        return original(self, db_url, *args, **kwargs)

    monkeypatch.setattr(DatabaseManager, "init_db", initialize)


def create(service, intent="modify", prompt="把标题改为会话总量"):
    return service.create_annotation(
        "annotation-dashboard",
        DashboardAnnotationCreateRequest(
            base_revision=1,
            target={"kind": "widget", "widget_id": "value-card", "label": "指标卡"},
            intent=intent,
            prompt=prompt,
        ),
        "alice",
    )


def output(path="/widgets/by-id/value-card/title", value="会话总量"):
    return SimpleNamespace(
        error_code=0,
        text=json.dumps(
            {
                "summary": "更新当前组件",
                "operations": [{"op": "replace", "path": path, "value": value}],
            },
            ensure_ascii=False,
        ),
    )


@pytest.mark.asyncio
async def test_repairs_real_validation_failure_and_only_persists_proposal(
    annotation_services,
):
    service, dashboards, _, _ = annotation_services
    current = create(service)
    client = SimpleNamespace(
        generate=AsyncMock(
            side_effect=[
                output("/widgets/by-id/missing/title"),
                output(),
            ]
        )
    )
    result = await generate_annotation_proposal(
        service,
        "annotation-dashboard",
        current.id,
        "alice",
        AnnotationGenerationRequest(model="chosen-model"),
        client,
    )
    assert result.status.value == "proposed"
    assert result.proposal.validation.valid
    assert result.proposal.preview_schema.widgets[0].title == "会话总量"
    assert (
        dashboards.get_dashboard("annotation-dashboard", "alice")
        .schema_payload.widgets[0]
        .title
        == "Original value"
    )
    assert client.generate.await_count == 2
    request = client.generate.call_args.args[0]
    assert request.model == "chosen-model"
    assert "validation_feedback" in request.messages[-1].content
    assert "missing" in request.messages[-1].content
    # A retry of a completed item must not generate another proposal.
    again = await generate_annotation_proposal(
        service,
        "annotation-dashboard",
        current.id,
        "alice",
        AnnotationGenerationRequest(model="chosen-model"),
        client,
    )
    assert again.id == result.id
    assert client.generate.await_count == 2


@pytest.mark.asyncio
async def test_failed_attempts_surface_detail_and_leave_annotation_pending(
    annotation_services,
):
    service, dashboards, _, _ = annotation_services
    current = create(service)
    client = SimpleNamespace(
        generate=AsyncMock(return_value=output("/widgets/by-id/missing/title"))
    )
    with pytest.raises(ValueError, match="missing"):
        await generate_annotation_proposal(
            service,
            "annotation-dashboard",
            current.id,
            "alice",
            AnnotationGenerationRequest(model="chosen-model"),
            client,
        )
    assert client.generate.await_count == 3
    assert (
        service.list_annotations("annotation-dashboard", "alice")[0].status.value
        == "pending"
    )
    assert (
        dashboards.get_dashboard("annotation-dashboard", "alice").current_revision == 1
    )


@pytest.mark.asyncio
async def test_model_cannot_replay_old_annotation_id(annotation_services):
    service, _, _, _ = annotation_services
    old = create(service, prompt="旧批注")
    current = create(service, prompt="当前要求")
    invalid = output()
    payload = json.loads(invalid.text)
    payload["annotation_id"] = old.id
    invalid.text = json.dumps(payload)
    client = SimpleNamespace(generate=AsyncMock(side_effect=[invalid, output()]))
    result = await generate_annotation_proposal(
        service,
        "annotation-dashboard",
        current.id,
        "alice",
        AnnotationGenerationRequest(model="chosen-model"),
        client,
    )
    assert result.id == current.id
    assert service._get("annotation-dashboard", old.id).status == "pending"
    first_request = client.generate.call_args_list[0].args[0]
    assert "当前要求" in first_request.messages[1].content
    assert old.id not in first_request.messages[1].content


@pytest.mark.asyncio
async def test_explanations_and_unauthorized_requests_never_call_model(
    annotation_services,
):
    service, _, _, _ = annotation_services
    current = create(service, intent="explain")
    client = SimpleNamespace(generate=AsyncMock())
    with pytest.raises(DashboardPatchError):
        await generate_annotation_proposal(
            service,
            "annotation-dashboard",
            current.id,
            "alice",
            AnnotationGenerationRequest(model="chosen-model"),
            client,
        )
    with pytest.raises(DashboardAccessDeniedError):
        await generate_annotation_proposal(
            service,
            "annotation-dashboard",
            current.id,
            "mallory",
            AnnotationGenerationRequest(model="chosen-model"),
            client,
        )
    client.generate.assert_not_called()


@pytest.mark.asyncio
async def test_cancelled_generation_never_persists_a_proposal(annotation_services):
    service, _, _, _ = annotation_services
    current = create(service)
    client = SimpleNamespace(generate=AsyncMock(return_value=output()))
    with pytest.raises(asyncio.CancelledError):
        await generate_annotation_proposal(
            service,
            "annotation-dashboard",
            current.id,
            "alice",
            AnnotationGenerationRequest(model="chosen-model"),
            client,
            cancelled=AsyncMock(side_effect=[False, True]),
        )
    assert service._get("annotation-dashboard", current.id).status == "pending"


def test_loaded_skills_teach_publication_and_array_binding(annotation_services):
    service, dashboards, _, _ = annotation_services
    messages = proposal_messages(
        create(service),
        dashboards.get_dashboard("annotation-dashboard", "alice").schema_payload,
        {},
    )
    assert "output_columns" in messages[0].content
    assert "IN (:category)" in messages[0].content
    assert "空数组" in messages[0].content


@pytest.mark.asyncio
async def test_repair_cannot_report_success_while_leaving_placeholder_sql(
    annotation_services,
):
    from dbgpt_app.openapi.api_v1.dashboard.schemas import DashboardCreateRequest

    from .test_annotations import _schema

    service, dashboards, _, _ = annotation_services
    schema = _schema()
    schema.dashboard.id = "unconfigured"
    schema.widgets[0].query.sql = "SELECT NULL AS value WHERE 1 = 0"
    dashboards.create_dashboard(DashboardCreateRequest(schema=schema), "alice")
    current = service.create_annotation(
        "unconfigured",
        DashboardAnnotationCreateRequest(
            base_revision=1,
            target={"kind": "widget", "widget_id": "value-card", "label": "新图表"},
            prompt="配置新图表的查询和字段映射",
        ),
        "alice",
    )
    client = SimpleNamespace(
        generate=AsyncMock(
            side_effect=[
                # A title change used to pass despite the empty chart.
                output(),
                output(
                    "/widgets/by-id/value-card/query/sql", "SELECT value FROM sales"
                ),
            ]
        )
    )
    proposal = await generate_annotation_proposal(
        service,
        "unconfigured",
        current.id,
        "alice",
        AnnotationGenerationRequest(model="chosen-model"),
        client,
    )
    assert client.generate.await_count == 2
    assert "占位查询" in client.generate.call_args.args[0].messages[-1].content
    assert (
        proposal.proposal.preview_schema.widgets[0].query.sql
        == "SELECT value FROM sales"
    )


@pytest.mark.asyncio
async def test_publication_columns_are_checked_against_executed_query(
    annotation_services,
):
    service, dashboards, _, _ = annotation_services
    current = create(service)
    publication = {
        "query": {
            "data_source_id": "demo",
            "sql": "SELECT value FROM sales",
            "output_fields": [
                {"name": "value", "type": "number"},
                {"name": "region", "type": "string"},
            ],
        },
        "filter_fields": {"region-filter": "region"},
        "group_by": [],
        "measures": [
            {"source_field": "value", "output_field": "value", "aggregation": "sum"}
        ],
        "output_columns": ["value"],
    }
    client = SimpleNamespace(
        generate=AsyncMock(
            side_effect=[
                output("/widgets/by-id/value-card/publication", publication),
                output(),
            ]
        )
    )
    proposal = await generate_annotation_proposal(
        service,
        "annotation-dashboard",
        current.id,
        "alice",
        AnnotationGenerationRequest(model="chosen-model"),
        client,
    )
    assert proposal.status.value == "proposed"
    assert client.generate.await_count == 2
    feedback = client.generate.call_args.args[0].messages[-1].content
    assert "发布查询验证失败" in feedback and "region" in feedback


def test_equivalent_metric_views_keep_the_same_filter_scope(annotation_services):
    from dbgpt_app.openapi.api_v1.dashboard.annotation_generation import (
        _validate_configuration,
    )
    from dbgpt_app.openapi.api_v1.dashboard.schemas import (
        DashboardChangeProposalRequest,
    )

    service, dashboards, _, _ = annotation_services
    current = service.create_annotation(
        "annotation-dashboard",
        DashboardAnnotationCreateRequest(
            base_revision=1,
            target={"kind": "filter", "filter_id": "region-filter", "label": "地区"},
            prompt="为全局筛选配置数据字段与组件绑定",
        ),
        "alice",
    )
    schema = dashboards.get_dashboard("annotation-dashboard", "alice").schema_payload
    second = schema.widgets[0].model_copy(deep=True)
    second.id = "same-metric-gauge"
    schema.widgets.append(second)
    layout = schema.layouts.desktop[0].model_copy(deep=True)
    layout.widget_id = second.id
    layout.x = 4
    schema.layouts.desktop.append(layout)
    proposal = DashboardChangeProposalRequest(
        summary="只改一个展示",
        operations=[
            {
                "op": "add",
                "path": (
                    "/widgets/by-id/value-card/query/filter_parameters/region-filter"
                ),
                "value": "region",
            }
        ],
    )
    with pytest.raises(DashboardPatchError, match="同一查询"):
        _validate_configuration(
            dashboards, "annotation-dashboard", "alice", schema, current, proposal
        )


def test_new_global_filter_cannot_inherit_planners_invented_scope_limit(
    annotation_services,
):
    from dbgpt_app.openapi.api_v1.dashboard.annotation_generation import (
        _validate_configuration,
    )
    from dbgpt_app.openapi.api_v1.dashboard.schemas import (
        DashboardChangeProposalRequest,
    )

    service, dashboards, _, _ = annotation_services
    current = service.create_annotation(
        "annotation-dashboard",
        DashboardAnnotationCreateRequest(
            base_revision=1,
            target={"kind": "filter", "filter_id": "region-filter", "label": "地区"},
            # An unsupported restriction introduced by the planner.
            prompt="只绑定环形图",
        ),
        "alice",
    )
    schema = dashboards.get_dashboard("annotation-dashboard", "alice").schema_payload
    schema.widgets[0].query.sql = "SELECT SUM(value) AS value FROM sales"
    proposal = DashboardChangeProposalRequest(
        summary="配置地区",
        operations=[
            {
                "op": "replace",
                "path": "/filters/by-id/region-filter/label",
                "value": "地区",
            }
        ],
    )
    context = {
        "data_source_id": "demo",
        "dialect": "sqlite",
        "tables": [
            {
                "name": "sales",
                "columns": [{"name": "value"}, {"name": "region"}],
            }
        ],
    }
    with pytest.raises(DashboardPatchError, match="value-card"):
        _validate_configuration(
            dashboards,
            "annotation-dashboard",
            "alice",
            schema,
            current,
            proposal,
            context,
            "新增全局筛选按地区来",
        )
    # A restriction actually supplied by the user must still be respected.
    _validate_configuration(
        dashboards,
        "annotation-dashboard",
        "alice",
        schema,
        current,
        proposal,
        context,
        "只联动环形图，不影响指标卡",
    )
