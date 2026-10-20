# Imported pytest fixtures are injected as arguments below.
# ruff: noqa: F811
import pytest

from dbgpt_app.openapi.api_v1.dashboard.collaboration import DashboardPatchError
from dbgpt_app.openapi.api_v1.dashboard.models import DashboardConflictError
from dbgpt_app.openapi.api_v1.dashboard.schemas import (
    DashboardAnnotationApplyRequest,
    DashboardAnnotationCreateRequest,
    DashboardChangeProposalRequest,
)

from .test_annotations import annotation_services  # noqa: F401


def propose(service, path, value):
    item = service.create_annotation(
        "annotation-dashboard",
        DashboardAnnotationCreateRequest(
            base_revision=1,
            target={"kind": "dashboard", "label": "整个看板"},
            prompt="调整显示设置",
        ),
        "alice",
    )
    return service.propose_change(
        "annotation-dashboard",
        item.id,
        DashboardChangeProposalRequest(
            summary="调整显示设置",
            operations=[{"op": "replace", "path": path, "value": value}],
        ),
        "alice",
    )


def apply(service, ids):
    return service.apply_batch(
        "annotation-dashboard",
        ids,
        DashboardAnnotationApplyRequest(
            expected_revision=1, operation_id="batch-test-1", client_id="test"
        ),
        "alice",
    )


def test_batch_saves_two_changes_in_one_revision(annotation_services):
    service, dashboards, _, _ = annotation_services
    first = propose(service, "/widgets/by-id/value-card/title", "新指标名称")
    second = propose(service, "/dashboard/title", "新看板名称")
    result = apply(service, [first.id, second.id])
    current = dashboards.get_dashboard("annotation-dashboard", "alice")
    assert current.current_revision == 2
    assert current.schema_payload.widgets[0].title == "新指标名称"
    assert current.schema_payload.dashboard.title == "新看板名称"
    assert all(item.status.value == "applied" for item in result["annotations"])


def test_conflicting_batch_preserves_all_original_data(annotation_services):
    service, dashboards, _, _ = annotation_services
    first = propose(service, "/widgets/by-id/value-card/title", "名称 A")
    second = propose(service, "/widgets/by-id/value-card/title", "名称 B")
    with pytest.raises(DashboardPatchError, match="不同修改"):
        apply(service, [first.id, second.id])
    current = dashboards.get_dashboard("annotation-dashboard", "alice")
    assert current.current_revision == 1
    assert current.schema_payload.widgets[0].title == "Original value"
    assert all(
        item.status.value == "proposed"
        for item in service.list_annotations(current.id, "alice")
    )


def test_missing_proposal_does_not_apply_earlier_valid_item(annotation_services):
    service, dashboards, _, _ = annotation_services
    first = propose(service, "/dashboard/title", "新名称")
    pending = service.create_annotation(
        "annotation-dashboard",
        DashboardAnnotationCreateRequest(
            base_revision=1,
            target={"kind": "dashboard", "label": "整个看板"},
            prompt="解释指标",
        ),
        "alice",
    )
    with pytest.raises(DashboardConflictError, match="没有可应用"):
        apply(service, [first.id, pending.id])
    assert (
        dashboards.get_dashboard("annotation-dashboard", "alice").current_revision == 1
    )


def test_other_actor_cannot_apply_batch(annotation_services):
    service, _, _, _ = annotation_services
    first = propose(service, "/dashboard/title", "新名称")
    with pytest.raises(Exception) as failure:
        service.apply_batch(
            "annotation-dashboard",
            [first.id],
            DashboardAnnotationApplyRequest(
                expected_revision=1, operation_id="unauthorized", client_id="test"
            ),
            "bob",
        )
    assert (
        "access" in str(type(failure.value)).lower()
        or "notfound" in str(type(failure.value)).lower()
    )
