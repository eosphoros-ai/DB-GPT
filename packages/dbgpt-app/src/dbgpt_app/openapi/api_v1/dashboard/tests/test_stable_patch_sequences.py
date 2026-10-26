"""Regression coverage for ordered AI proposals with newly created objects."""

# Imported pytest fixtures are injected as arguments below.
# ruff: noqa: F811
import pytest

from dbgpt_app.openapi.api_v1.dashboard.annotations import (
    resolve_stable_patch_operations,
)
from dbgpt_app.openapi.api_v1.dashboard.collaboration import (
    DashboardPatchError,
    apply_dashboard_patch,
)
from dbgpt_app.openapi.api_v1.dashboard.schemas import (
    DashboardAnnotationApplyRequest,
    DashboardAnnotationCreateRequest,
    DashboardChangeProposalRequest,
    DashboardStablePatchOperation,
)

from .test_annotations import _schema, annotation_services  # noqa: F401


def _operations(items):
    return [DashboardStablePatchOperation.model_validate(item) for item in items]


def _filter():
    return {
        "id": "holiday_filter",
        "type": "select",
        "label": "Holiday",
        "field": "holiday_flag",
        "default": 1,
        "options": [{"label": "Holiday", "value": 1}, {"label": "Regular", "value": 0}],
    }


def _filter_operations(*, refine=True):
    operations = [{"op": "add", "path": "/filters/-", "value": _filter()}]
    if refine:
        operations.append(
            {
                "op": "replace",
                "path": "/filters/by-id/holiday_filter/label",
                "value": "节假日",
            }
        )
    operations.extend(
        [
            {
                "op": "replace",
                "path": "/widgets/by-id/value-card/query/sql",
                "value": "SELECT 1 AS value WHERE :holiday = 1",
            },
            {
                "op": "add",
                "path": (
                    "/widgets/by-id/value-card/query/filter_parameters/holiday_filter"
                ),
                "value": "holiday",
            },
        ]
    )
    return operations


def test_append_filter_and_bind_existing_widget_without_lookup_already_works():
    schema = _schema()
    operations = resolve_stable_patch_operations(
        schema, _operations(_filter_operations(refine=False))
    )
    patched = apply_dashboard_patch(schema.model_dump(), operations)
    assert patched["filters"][-1]["id"] == "holiday_filter"
    assert (
        patched["widgets"][0]["query"]["filter_parameters"]["holiday_filter"]
        == "holiday"
    )


@pytest.mark.parametrize("batch", [False, True])
def test_new_filter_can_be_refined_bound_reviewed_and_applied(
    annotation_services, batch
):
    annotations, dashboards, _, _ = annotation_services
    original = dashboards.get_dashboard("annotation-dashboard", "alice")
    annotation = annotations.create_annotation(
        original.id,
        DashboardAnnotationCreateRequest(
            base_revision=1,
            target={"kind": "dashboard", "label": "整个看板"},
            prompt="新增节假日筛选器并绑定指标",
        ),
        "alice",
    )
    proposed = annotations.propose_change(
        original.id,
        annotation.id,
        DashboardChangeProposalRequest(
            summary="新增并配置筛选器", operations=_filter_operations()
        ),
        "alice",
    )
    assert proposed.proposal.preview_schema.filters[-1].label == "节假日"
    unchanged = dashboards.get_dashboard(original.id, "alice")
    assert unchanged.current_revision == 1
    assert unchanged.schema_payload == original.schema_payload
    request = DashboardAnnotationApplyRequest(
        expected_revision=1, operation_id="create-filter-regression", client_id="test"
    )
    if batch:
        annotations.apply_batch(original.id, [annotation.id], request, "alice")
    else:
        annotations.apply_annotation(original.id, annotation.id, request, "alice")
    applied = dashboards.get_dashboard(original.id, "alice")
    assert applied.current_revision == 2
    assert applied.schema_payload.filters[-1].id == "holiday_filter"
    assert applied.schema_payload.filters[-1].label == "节假日"
    assert (
        applied.schema_payload.widgets[0].query.filter_parameters["holiday_filter"]
        == "holiday"
    )


def test_new_widget_and_layout_can_be_referenced_later_in_the_same_proposal():
    schema = _schema()
    before = schema.model_dump()
    widget = {**before["widgets"][0], "id": "new-card"}
    operations = _operations(
        [
            {"op": "add", "path": "/widgets/-", "value": widget},
            {
                "op": "replace",
                "path": "/widgets/by-id/new-card/title",
                "value": "新指标",
            },
            {
                "op": "add",
                "path": "/layouts/desktop/-",
                "value": {"widget_id": "new-card", "x": 4, "y": 0, "w": 4, "h": 3},
            },
            {
                "op": "replace",
                "path": "/layouts/desktop/by-widget-id/new-card/w",
                "value": 6,
            },
        ]
    )
    resolved = resolve_stable_patch_operations(schema, operations)
    patched = apply_dashboard_patch(before, resolved)
    assert patched["widgets"][1]["title"] == "新指标"
    assert patched["layouts"]["desktop"][1]["w"] == 6
    assert schema.model_dump() == before
    assert operations[0].value["title"] == "Original value"


@pytest.mark.parametrize("collection", ["filters", "widgets"])
def test_removing_items_does_not_shift_a_later_stable_target(collection):
    schema = _schema()
    items = getattr(schema, collection)
    first_id = items[0].id
    items.extend(
        [
            items[0].model_copy(update={"id": "second"}, deep=True),
            items[0].model_copy(update={"id": "third"}, deep=True),
        ]
    )
    field = "label" if collection == "filters" else "title"
    operations = _operations(
        [
            {"op": "remove", "path": f"/{collection}/by-id/{first_id}"},
            {"op": "remove", "path": f"/{collection}/by-id/second"},
            {
                "op": "replace",
                "path": f"/{collection}/by-id/third/{field}",
                "value": "Survivor",
            },
        ]
    )
    resolved = resolve_stable_patch_operations(schema, operations)
    patched = apply_dashboard_patch(schema.model_dump(), resolved)
    assert [(item["id"], item[field]) for item in patched[collection]] == [
        ("third", "Survivor")
    ]


def test_referencing_a_removed_object_fails_without_changing_the_input():
    schema = _schema()
    before = schema.model_dump()
    operations = _operations(
        [
            {"op": "remove", "path": "/filters/by-id/region-filter"},
            {
                "op": "replace",
                "path": "/filters/by-id/region-filter/label",
                "value": "Wrong object",
            },
        ]
    )
    with pytest.raises(DashboardPatchError, match="no longer exists"):
        resolve_stable_patch_operations(schema, operations)
    assert schema.model_dump() == before


@pytest.mark.parametrize("collection", ["filters", "widgets"])
def test_invalid_creation_path_explains_how_to_append_a_new_object(collection):
    schema = _schema()
    with pytest.raises(DashboardPatchError, match=f"/{collection}/-"):
        resolve_stable_patch_operations(
            schema,
            _operations(
                [
                    {
                        "op": "add",
                        "path": f"/{collection}/by-id/new-item",
                        "value": {"id": "new-item"},
                    },
                ]
            ),
        )


def test_late_invalid_patch_never_persists_the_earlier_new_filter(annotation_services):
    annotations, dashboards, _, _ = annotation_services
    original = dashboards.get_dashboard("annotation-dashboard", "alice")
    annotation = annotations.create_annotation(
        original.id,
        DashboardAnnotationCreateRequest(
            base_revision=1,
            target={"kind": "dashboard", "label": "整个看板"},
            prompt="新增筛选器",
        ),
        "alice",
    )
    with pytest.raises(DashboardPatchError, match="cannot be patched"):
        annotations.propose_change(
            original.id,
            annotation.id,
            DashboardChangeProposalRequest(
                summary="包含非法修改",
                operations=[
                    *_filter_operations(refine=False),
                    {
                        "op": "replace",
                        "path": "/dashboard/id",
                        "value": "other-dashboard",
                    },
                ],
            ),
            "alice",
        )
    after = dashboards.get_dashboard(original.id, "alice")
    assert after.current_revision == original.current_revision
    assert after.schema_payload == original.schema_payload
    assert (
        annotations.list_annotations(original.id, "alice")[0].status.value == "pending"
    )


def test_batch_allows_ordered_updates_within_one_proposal(annotation_services):
    annotations, dashboards, _, _ = annotation_services
    annotation = annotations.create_annotation(
        "annotation-dashboard",
        DashboardAnnotationCreateRequest(
            base_revision=1,
            target={"kind": "dashboard", "label": "整个看板"},
            prompt="调整组件查询",
        ),
        "alice",
    )
    query = _schema().widgets[0].query.model_dump()
    annotations.propose_change(
        "annotation-dashboard",
        annotation.id,
        DashboardChangeProposalRequest(
            summary="更新查询及参数",
            operations=[
                {
                    "op": "replace",
                    "path": "/widgets/by-id/value-card/query",
                    "value": query,
                },
                {
                    "op": "add",
                    "path": (
                        "/widgets/by-id/value-card/query/default_parameters/holiday"
                    ),
                    "value": 1,
                },
            ],
        ),
        "alice",
    )
    annotations.apply_batch(
        "annotation-dashboard",
        [annotation.id],
        DashboardAnnotationApplyRequest(
            expected_revision=1, operation_id="ordered-batch-apply", client_id="test"
        ),
        "alice",
    )
    assert dashboards.get_dashboard(
        "annotation-dashboard", "alice"
    ).schema_payload.widgets[0].query.default_parameters == {"holiday": 1}


def test_dashboard_request_cannot_create_an_unbound_global_filter(annotation_services):
    from dbgpt_app.openapi.api_v1.dashboard.annotation_generation import (
        _validate_configuration,
    )

    annotations, dashboards, _, _ = annotation_services
    schema = _schema()
    schema.widgets[0].query.sql = "SELECT SUM(value) AS value FROM sales"
    annotation = annotations.create_annotation(
        "annotation-dashboard",
        DashboardAnnotationCreateRequest(
            base_revision=1,
            target={"kind": "dashboard", "label": "整个看板"},
            prompt="新增一个全局筛选器",
        ),
        "alice",
    )
    proposal = DashboardChangeProposalRequest(
        summary="新增筛选器",
        operations=[{"op": "add", "path": "/filters/-", "value": _filter()}],
    )
    context = {
        "data_source_id": "demo",
        "dialect": "sqlite",
        "tables": [
            {"name": "sales", "columns": [{"name": "value"}, {"name": "holiday_flag"}]}
        ],
    }
    with pytest.raises(DashboardPatchError, match="遗漏了可联动组件.*value-card"):
        _validate_configuration(
            dashboards,
            "annotation-dashboard",
            "alice",
            schema,
            annotation,
            proposal,
            context,
        )


def test_new_multiselect_checks_empty_single_and_multiple_values(
    annotation_services, monkeypatch
):
    from dbgpt_app.openapi.api_v1.dashboard.annotation_generation import (
        _validate_configuration,
    )

    annotations, dashboards, _, _ = annotation_services
    annotation = annotations.create_annotation(
        "annotation-dashboard",
        DashboardAnnotationCreateRequest(
            base_revision=1,
            target={"kind": "dashboard", "label": "整个看板"},
            prompt="新增一个全局筛选器",
        ),
        "alice",
    )
    new_filter = {**_filter(), "type": "multi_select", "default": []}
    proposal = DashboardChangeProposalRequest(
        summary="新增多选筛选器",
        operations=[
            {"op": "add", "path": "/filters/-", "value": new_filter},
            {
                "op": "replace",
                "path": "/widgets/by-id/value-card/query/sql",
                "value": "SELECT 1 AS value WHERE 1 IN (:holiday)",
            },
            {
                "op": "add",
                "path": (
                    "/widgets/by-id/value-card/query/filter_parameters/holiday_filter"
                ),
                "value": "holiday",
            },
        ],
    )
    original_validate = dashboards.validate_schema
    selections = []

    def observe(schema, **kwargs):
        selections.append(kwargs.get("filters"))
        return original_validate(schema, **kwargs)

    monkeypatch.setattr(dashboards, "validate_schema", observe)
    _validate_configuration(
        dashboards, "annotation-dashboard", "alice", _schema(), annotation, proposal
    )
    assert selections == [
        {"holiday_filter": []},
        {"holiday_filter": [1]},
        {"holiday_filter": [1, 0]},
    ]
