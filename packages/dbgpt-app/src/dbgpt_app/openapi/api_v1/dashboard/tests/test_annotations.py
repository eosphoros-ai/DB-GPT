import json

import pytest

from dbgpt.storage.metadata import DatabaseManager, Model
from dbgpt_app.openapi.api_v1.dashboard.access import DashboardAuthorizationService
from dbgpt_app.openapi.api_v1.dashboard.annotations import DashboardAnnotationService
from dbgpt_app.openapi.api_v1.dashboard.collaboration import (
    DashboardCollaborationService,
    DashboardPatchError,
)
from dbgpt_app.openapi.api_v1.dashboard.models import (
    DashboardAccessDao,
    DashboardAuditDao,
    DashboardConflictError,
    DashboardDao,
)
from dbgpt_app.openapi.api_v1.dashboard.planner import DashboardPlannerService
from dbgpt_app.openapi.api_v1.dashboard.schemas import (
    DashboardAnnotationApplyRequest,
    DashboardAnnotationCreateRequest,
    DashboardAnnotationIntent,
    DashboardAnnotationStatus,
    DashboardChangeProposalRequest,
    DashboardCreateRequest,
    DashboardOperationRequest,
    DashboardPatchOperation,
    DashboardSchemaV1,
    DashboardSelectionKind,
    DashboardSelectionTarget,
    DashboardStablePatchOperation,
)
from dbgpt_app.openapi.api_v1.dashboard.service import DashboardService
from dbgpt_app.openapi.api_v1.tools.dashboard import make_dashboard_planner_tools


class _Connector:
    db_type = "sqlite"

    def __init__(self):
        self.calls = []

    def get_table_names(self):
        return ["sales"]

    def get_fields(self, *_args):
        return [("value", "number")]

    def query_ex(self, sql, params=None, timeout=None):
        self.calls.append((sql, params, timeout))
        return ["value"], [(1,)]


def _schema() -> DashboardSchemaV1:
    return DashboardSchemaV1.model_validate(
        {
            "schema_version": "1.3",
            "dashboard": {
                "id": "annotation-dashboard",
                "title": "Original dashboard",
                "data_source_id": "demo",
            },
            "filters": [
                {
                    "id": "region-filter",
                    "type": "select",
                    "label": "Region",
                    "field": "region",
                    "default": "all",
                    "options": [
                        {"label": "All", "value": "all"},
                        {"label": "North", "value": "north"},
                    ],
                }
            ],
            "widgets": [
                {
                    "id": "value-card",
                    "type": "kpi",
                    "title": "Original value",
                    "query": {
                        "data_source_id": "demo",
                        "sql": "SELECT 1 AS value",
                        "output_fields": [{"name": "value", "type": "number"}],
                    },
                    "encoding": {"value": "value"},
                    "presentation": {
                        "visualization": "kpi",
                        "precision": 0,
                    },
                }
            ],
            "layouts": {
                "desktop": [{"widget_id": "value-card", "x": 0, "y": 0, "w": 4, "h": 3}]
            },
        }
    )


@pytest.fixture
def annotation_services():
    manager = DatabaseManager()
    manager.init_db("sqlite:///:memory:", base=Model)
    Model.metadata.create_all(manager.engine)
    dao = DashboardDao(manager)
    authorization = DashboardAuthorizationService(
        dashboard_dao=dao,
        access_dao=DashboardAccessDao(manager),
        audit_dao=DashboardAuditDao(manager),
    )
    connector = _Connector()
    dashboard_service = DashboardService(
        dao=dao,
        authorization_service=authorization,
        connector_resolver=lambda _source_id: connector,
    )
    dashboard_service.create_dashboard(
        DashboardCreateRequest(schema=_schema()), "alice"
    )
    collaboration_service = DashboardCollaborationService(dashboard_service)
    return (
        DashboardAnnotationService(dashboard_service, collaboration_service),
        dashboard_service,
        collaboration_service,
        connector,
    )


def _target(kind=DashboardSelectionKind.WIDGET):
    if kind == DashboardSelectionKind.DASHBOARD:
        return DashboardSelectionTarget(kind=kind, label="整个看板")
    if kind == DashboardSelectionKind.FILTER:
        return DashboardSelectionTarget.model_validate(
            {
                "kind": kind,
                "filter_id": "region-filter",
                "label": "Region",
            }
        )
    payload = {
        "kind": kind,
        "widget_id": "value-card",
        "label": "Original value",
    }
    if kind in {DashboardSelectionKind.TABLE_COLUMN, DashboardSelectionKind.TABLE_CELL}:
        payload["column"] = "value"
    if kind == DashboardSelectionKind.TABLE_CELL:
        payload["row_key"] = {"value": 1}
        payload["value"] = 1
    if kind == DashboardSelectionKind.CHART_DATUM:
        payload["datum_key"] = {"value": 1}
        payload["value"] = 1
    if kind == DashboardSelectionKind.CHART_SERIES:
        payload["series"] = "value"
    return DashboardSelectionTarget.model_validate(payload)


@pytest.mark.parametrize("kind", list(DashboardSelectionKind))
def test_all_selection_targets_are_persisted_without_editing_dashboard(
    annotation_services, kind
):
    annotations, dashboards, _collaboration, _connector = annotation_services
    created = annotations.create_annotation(
        "annotation-dashboard",
        DashboardAnnotationCreateRequest(
            base_revision=1,
            target=_target(kind),
            prompt="Make this easier to read.",
            conversation_id="conversation-1",
            source_turn_id="turn-1",
        ),
        "alice",
    )

    assert created.status == DashboardAnnotationStatus.PENDING
    assert created.target.kind == kind
    assert created.conversation_id == "conversation-1"
    current = dashboards.get_dashboard("annotation-dashboard", "alice")
    assert current.current_revision == 1
    assert current.schema_payload.widgets[0].title == "Original value"


def test_filter_proposal_uses_stable_filter_id_and_only_apply_persists(
    annotation_services,
):
    annotations, dashboards, _collaboration, _connector = annotation_services
    created = annotations.create_annotation(
        "annotation-dashboard",
        DashboardAnnotationCreateRequest(
            base_revision=1,
            target=_target(DashboardSelectionKind.FILTER),
            prompt="默认只看北区。",
        ),
        "alice",
    )

    proposed = annotations.propose_change(
        "annotation-dashboard",
        created.id,
        DashboardChangeProposalRequest(
            summary="Change the default region.",
            operations=[
                DashboardStablePatchOperation(
                    op="replace",
                    path="/filters/by-id/region-filter/default",
                    value="north",
                )
            ],
        ),
        "alice",
    )

    assert proposed.proposal.preview_schema.filters[0].default == "north"
    unchanged = dashboards.get_dashboard("annotation-dashboard", "alice")
    assert unchanged.schema_payload.filters[0].default == "all"

    applied = annotations.apply_annotation(
        "annotation-dashboard",
        created.id,
        DashboardAnnotationApplyRequest(
            expected_revision=1,
            operation_id="apply-region-default",
            client_id="browser-a",
        ),
        "alice",
    )
    assert applied.operation.dashboard.schema_payload.filters[0].default == "north"


@pytest.mark.parametrize(
    "intent",
    [DashboardAnnotationIntent.EXPLAIN, DashboardAnnotationIntent.ANOMALY],
)
def test_read_only_annotation_intents_are_persisted_and_cannot_propose_changes(
    annotation_services, intent
):
    annotations, _dashboards, _collaboration, _connector = annotation_services
    created = annotations.create_annotation(
        "annotation-dashboard",
        DashboardAnnotationCreateRequest(
            base_revision=1,
            target=_target(),
            prompt="Explain only from deterministic evidence.",
            intent=intent,
        ),
        "alice",
    )

    assert created.intent == intent
    persisted = annotations.list_annotations("annotation-dashboard", "alice")[0]
    assert persisted.intent == intent
    with pytest.raises(DashboardPatchError, match="read-only"):
        annotations.propose_change(
            "annotation-dashboard",
            created.id,
            DashboardChangeProposalRequest(
                summary="This must be rejected.",
                operations=[
                    DashboardStablePatchOperation(
                        op="replace",
                        path="/widgets/by-id/value-card/title",
                        value="Unauthorized change",
                    )
                ],
            ),
            "alice",
        )


def test_filter_binding_intent_requires_a_component_parameter_mapping(
    annotation_services,
):
    annotations, _dashboards, _collaboration, _connector = annotation_services
    created = annotations.create_annotation(
        "annotation-dashboard",
        DashboardAnnotationCreateRequest(
            base_revision=1,
            target=_target(DashboardSelectionKind.FILTER),
            prompt="请配置影响组件范围及 SQL 参数绑定。",
        ),
        "alice",
    )

    with pytest.raises(DashboardPatchError, match="did not modify"):
        annotations.propose_change(
            "annotation-dashboard",
            created.id,
            DashboardChangeProposalRequest(
                summary="Only change the visible default.",
                operations=[
                    DashboardStablePatchOperation(
                        op="replace",
                        path="/filters/by-id/region-filter/default",
                        value="north",
                    )
                ],
            ),
            "alice",
        )


def test_filter_binding_intent_requires_the_mapped_parameter_in_sql(
    annotation_services,
):
    annotations, _dashboards, _collaboration, _connector = annotation_services
    created = annotations.create_annotation(
        "annotation-dashboard",
        DashboardAnnotationCreateRequest(
            base_revision=1,
            target=_target(DashboardSelectionKind.FILTER),
            prompt="Bind this filter to the component with a parameter mapping.",
        ),
        "alice",
    )

    with pytest.raises(DashboardPatchError, match=":region"):
        annotations.propose_change(
            "annotation-dashboard",
            created.id,
            DashboardChangeProposalRequest(
                summary="Add a mapping without changing SQL.",
                operations=[
                    DashboardStablePatchOperation(
                        op="add",
                        path=(
                            "/widgets/by-id/value-card/query/filter_parameters/"
                            "region-filter"
                        ),
                        value="region",
                    )
                ],
            ),
            "alice",
        )


def test_filter_binding_intent_accepts_mapping_and_matching_sql(
    annotation_services,
):
    annotations, _dashboards, _collaboration, _connector = annotation_services
    created = annotations.create_annotation(
        "annotation-dashboard",
        DashboardAnnotationCreateRequest(
            base_revision=1,
            target=_target(DashboardSelectionKind.FILTER),
            prompt="请配置影响组件范围及 SQL 参数绑定。",
        ),
        "alice",
    )

    proposed = annotations.propose_change(
        "annotation-dashboard",
        created.id,
        DashboardChangeProposalRequest(
            summary="Bind the region filter.",
            operations=[
                DashboardStablePatchOperation(
                    op="replace",
                    path="/widgets/by-id/value-card/query/sql",
                    value=(
                        "SELECT 1 AS value WHERE (:region = 'all' OR :region = :region)"
                    ),
                ),
                DashboardStablePatchOperation(
                    op="add",
                    path=(
                        "/widgets/by-id/value-card/query/filter_parameters/"
                        "region-filter"
                    ),
                    value="region",
                ),
            ],
        ),
        "alice",
    )

    assert proposed.status == DashboardAnnotationStatus.PROPOSED
    assert (
        proposed.proposal.preview_schema.widgets[0].query.filter_parameters[
            "region-filter"
        ]
        == "region"
    )


def test_proposal_is_validated_in_memory_and_only_apply_persists(annotation_services):
    annotations, dashboards, _collaboration, connector = annotation_services
    created = annotations.create_annotation(
        "annotation-dashboard",
        DashboardAnnotationCreateRequest(
            base_revision=1,
            target=_target(),
            prompt="Rename this to Verified value.",
        ),
        "alice",
    )

    proposed = annotations.propose_change(
        "annotation-dashboard",
        created.id,
        DashboardChangeProposalRequest(
            summary="Rename the selected KPI.",
            operations=[
                DashboardStablePatchOperation(
                    op="replace",
                    path="/widgets/by-id/value-card/title",
                    value="Verified value",
                )
            ],
            before=["Original value"],
            after=["Verified value"],
        ),
        "alice",
    )

    assert proposed.status == DashboardAnnotationStatus.PROPOSED
    assert proposed.proposal.preview_schema.widgets[0].title == "Verified value"
    assert connector.calls
    unchanged = dashboards.get_dashboard("annotation-dashboard", "alice")
    assert unchanged.current_revision == 1
    assert unchanged.schema_payload.widgets[0].title == "Original value"

    applied = annotations.apply_annotation(
        "annotation-dashboard",
        created.id,
        DashboardAnnotationApplyRequest(
            expected_revision=1,
            operation_id="annotation-apply-1",
            client_id="browser-a",
        ),
        "alice",
    )
    assert applied.annotation.status == DashboardAnnotationStatus.APPLIED
    assert applied.operation.dashboard.current_revision == 2
    assert applied.operation.dashboard.schema_payload.widgets[0].title == (
        "Verified value"
    )
    version = dashboards.dao.get_edit_version("annotation-dashboard", 2)
    assert version.source == "ai_annotation"
    assert version.operation_id == "annotation-apply-1"


def test_stale_annotation_is_invalidated_before_a_proposal_can_be_saved(
    annotation_services,
):
    annotations, _dashboards, collaboration, _connector = annotation_services
    created = annotations.create_annotation(
        "annotation-dashboard",
        DashboardAnnotationCreateRequest(
            base_revision=1,
            target=_target(),
            prompt="Rename this KPI.",
        ),
        "alice",
    )
    collaboration.apply_operation(
        "annotation-dashboard",
        DashboardOperationRequest(
            operation_id="other-edit-1",
            client_id="browser-b",
            expected_revision=1,
            operations=[
                DashboardPatchOperation(
                    op="replace", path="/dashboard/title", value="New dashboard"
                )
            ],
        ),
        "alice",
    )

    with pytest.raises(DashboardConflictError, match="changed"):
        annotations.propose_change(
            "annotation-dashboard",
            created.id,
            DashboardChangeProposalRequest(
                summary="Rename the selected KPI.",
                operations=[
                    DashboardStablePatchOperation(
                        op="replace",
                        path="/widgets/by-id/value-card/title",
                        value="Stale title",
                    )
                ],
            ),
            "alice",
        )
    listed = annotations.list_annotations("annotation-dashboard", "alice")
    assert listed[0].status == DashboardAnnotationStatus.INVALIDATED


def test_failed_agent_proposal_stops_waiting(annotation_services):
    annotations, _dashboards, _collaboration, _connector = annotation_services
    created = annotations.create_annotation(
        "annotation-dashboard",
        DashboardAnnotationCreateRequest(
            base_revision=1,
            target=_target(),
            prompt="Configure this widget.",
        ),
        "alice",
    )

    failed = annotations.invalidate_pending_proposal(
        "annotation-dashboard",
        created.id,
        "alice",
        reason="The proposed Patch path was invalid.",
    )

    assert failed.status == DashboardAnnotationStatus.INVALIDATED
    assert failed.resolved_at is not None


@pytest.mark.asyncio
async def test_invalid_agent_patch_is_invalidated_by_the_proposal_tool(
    annotation_services,
):
    annotations, dashboards, _collaboration, connector = annotation_services
    created = annotations.create_annotation(
        "annotation-dashboard",
        DashboardAnnotationCreateRequest(
            base_revision=1,
            target=_target(),
            prompt="Configure this widget.",
        ),
        "alice",
    )

    async def capture(_event_type, _payload):
        return None

    tools = {
        item._tool.name: item
        for item in make_dashboard_planner_tools(
            react_state={"conv_id": "conversation-1"},
            database_connector=connector,
            database_name="demo",
            owner_id="alice",
            user_prompt=(
                f"[[dashboard-annotation:annotation-dashboard:{created.id}]] "
                "update dashboard annotation-dashboard"
            ),
            model_name="mock-model",
            stream_callback=capture,
            planner_service=DashboardPlannerService(dashboards),
        )
    }

    result = await tools["propose_dashboard_change"](
        dashboard_id="annotation-dashboard",
        annotation_id=created.id,
        summary="Use an illegal numeric widget path.",
        operations=json.dumps(
            [{"op": "replace", "path": "/widgets/0/title", "value": "Updated"}]
        ),
    )

    assert "proposal rejected" in result
    failed = annotations.list_annotations("annotation-dashboard", "alice")[0]
    assert failed.status == DashboardAnnotationStatus.INVALIDATED
    assert failed.resolved_at is not None


def test_agent_must_use_stable_widget_ids(annotation_services):
    annotations, _dashboards, _collaboration, _connector = annotation_services
    created = annotations.create_annotation(
        "annotation-dashboard",
        DashboardAnnotationCreateRequest(
            base_revision=1,
            target=_target(),
            prompt="Rename this KPI.",
        ),
        "alice",
    )
    with pytest.raises(DashboardPatchError, match="by-id"):
        annotations.propose_change(
            "annotation-dashboard",
            created.id,
            DashboardChangeProposalRequest(
                summary="Unsafe index based edit.",
                operations=[
                    DashboardStablePatchOperation(
                        op="replace",
                        path="/widgets/0/title",
                        value="Index based title",
                    )
                ],
            ),
            "alice",
        )


@pytest.mark.parametrize(
    "legacy_path",
    [
        "/widgets/by-id/value-card/parameters",
        "/widgets/0/parameters",
    ],
)
def test_legacy_widget_parameters_are_resolved_to_query_defaults(
    annotation_services, legacy_path
):
    annotations, _dashboards, _collaboration, _connector = annotation_services
    created = annotations.create_annotation(
        "annotation-dashboard",
        DashboardAnnotationCreateRequest(
            base_revision=1,
            target=_target(),
            prompt="Configure the widget query parameters.",
        ),
        "alice",
    )

    proposed = annotations.propose_change(
        "annotation-dashboard",
        created.id,
        DashboardChangeProposalRequest(
            summary="Configure query defaults.",
            operations=[
                DashboardStablePatchOperation(
                    op="replace",
                    path=legacy_path,
                    value={"region": "north"},
                )
            ],
        ),
        "alice",
    )

    assert proposed.status == DashboardAnnotationStatus.PROPOSED
    assert proposed.proposal is not None
    assert proposed.proposal.operations[0].path == (
        "/widgets/0/query/default_parameters"
    )
    assert proposed.proposal.preview_schema.widgets[0].query.default_parameters == {
        "region": "north"
    }
