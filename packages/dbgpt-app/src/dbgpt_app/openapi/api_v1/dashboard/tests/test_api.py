from datetime import datetime

import pytest
from fastapi import HTTPException

from dbgpt_app.openapi.api_v1.dashboard.api import (
    _user_id,
    create_dashboard_schedule,
    filter_public_dashboard,
    get_dashboard_edit_version,
    get_latest_dashboard_snapshot,
    import_legacy_dashboard,
    list_dashboard_edit_versions,
    list_dashboard_publications,
    list_dashboard_schedules,
    preview_widget,
    resolve_dashboard_reference,
    restore_dashboard_edit_version,
    revoke_dashboard_publication,
    rotate_dashboard_publication,
    toggle_dashboard_schedule,
    update_dashboard,
    validate_dashboard,
)
from dbgpt_app.openapi.api_v1.dashboard.identity import DBGPTUserIdentityProvider
from dbgpt_app.openapi.api_v1.dashboard.models import DashboardConflictError
from dbgpt_app.openapi.api_v1.dashboard.schemas import (
    DashboardEditVersionDetail,
    DashboardEditVersionRecord,
    DashboardRecord,
    DashboardScheduleCreateRequest,
    DashboardScheduleToggleRequest,
    DashboardSchemaV1,
    DashboardShareRecord,
    DashboardShareRotateRequest,
    DashboardSnapshot,
    DashboardStateRequest,
    DashboardTargetResolutionRequest,
    DashboardUpdateRequest,
    DashboardValidateRequest,
    DashboardValidationResult,
    DashboardWidgetPreviewRequest,
    LegacyDashboardImportRequest,
    PublicDashboardFilterRequest,
    PublicDashboardFilterResponse,
    WidgetQueryResult,
)
from dbgpt_serve.scheduled_task.api.schemas import (
    DashboardRefreshPayload,
    TaskResponse,
)
from dbgpt_serve.utils.auth import UserRequest


def _schema(sql="SELECT 1 AS value"):
    return DashboardSchemaV1.model_validate(
        {
            "schema_version": "1.0",
            "dashboard": {
                "id": "dashboard-1",
                "title": "API test",
                "data_source_id": "demo",
            },
            "widgets": [
                {
                    "id": "value",
                    "type": "kpi",
                    "title": "Value",
                    "query": {
                        "data_source_id": "demo",
                        "sql": sql,
                        "output_fields": [{"name": "value", "type": "number"}],
                    },
                    "encoding": {"value": "value"},
                }
            ],
            "layouts": {
                "desktop": [{"widget_id": "value", "x": 0, "y": 0, "w": 4, "h": 3}]
            },
        }
    )


def _record(schema=None):
    now = datetime.now()
    return DashboardRecord(
        id="dashboard-1",
        owner_id="alice",
        current_revision=1,
        status="draft",
        schema=schema or _schema(),
        created_at=now,
        updated_at=now,
    )


def test_dashboard_identity_comes_from_upstream_user_request():
    assert _user_id(UserRequest(user_id="alice")) == "alice"
    assert _user_id(UserRequest(user_name="legacy-alice")) == "legacy-alice"
    with pytest.raises(HTTPException) as raised:
        _user_id(UserRequest())
    assert raised.value.status_code == 401


def test_dashboard_production_identity_rejects_upstream_mock_admin():
    strict = DBGPTUserIdentityProvider(allow_development_fallback=False)
    fallback = UserRequest(
        user_id="001", role="admin", nick_name="dbgpt", real_name="dbgpt"
    )
    with pytest.raises(HTTPException) as raised:
        _user_id(fallback, strict)
    assert raised.value.status_code == 401
    assert _user_id(UserRequest(user_id="alice"), strict) == "alice"


class ApiServiceStub:
    def __init__(self):
        self.record = _record()
        self.preview_schema = None
        self.created_request = None
        self.raise_conflict = False
        self.validated_schema = None
        self.required_action = None
        self.audit_events = []
        self.publications = []
        self.public_filter_call = None

    def get_dashboard(self, dashboard_id, owner_id):
        assert dashboard_id == "dashboard-1"
        assert owner_id == "alice"
        return self.record

    def list_edit_versions(self, dashboard_id, owner_id, *, limit, offset):
        assert (dashboard_id, owner_id, limit, offset) == (
            "dashboard-1",
            "alice",
            25,
            0,
        )
        return [
            DashboardEditVersionRecord(
                dashboard_id=dashboard_id,
                revision=1,
                source="create",
                actor_id=owner_id,
                created_at=datetime.now(),
            )
        ]

    def get_edit_version(self, dashboard_id, revision, owner_id):
        assert (dashboard_id, revision, owner_id) == ("dashboard-1", 1, "alice")
        return DashboardEditVersionDetail(
            dashboard_id=dashboard_id,
            revision=revision,
            source="create",
            actor_id=owner_id,
            created_at=datetime.now(),
            schema=self.record.schema_payload,
        )

    def restore_edit_version(self, dashboard_id, revision, expected_revision, owner_id):
        assert (dashboard_id, revision, expected_revision, owner_id) == (
            "dashboard-1",
            1,
            2,
            "alice",
        )
        return self.record

    def require_permission(self, dashboard_id, actor_id, action, schema=None):
        assert dashboard_id == "dashboard-1"
        assert actor_id == "alice"
        self.required_action = action
        return self.record

    def validate_widget_query(self, schema, widget_id, filters):
        self.preview_schema = schema
        return WidgetQueryResult(
            widget_id=widget_id,
            columns=["value"],
            rows=[[2]],
            row_count=1,
            refreshed_at=datetime.now(),
        )

    def update_dashboard(self, *args, **kwargs):
        if self.raise_conflict:
            raise DashboardConflictError("revision conflict")
        return self.record

    def validate_schema(
        self,
        schema,
        execute_queries,
        filters,
        require_publication_bindings=False,
    ):
        self.validated_schema = schema
        return DashboardValidationResult(valid=True)

    def create_dashboard(self, request, owner_id):
        self.created_request = request
        return _record(request.schema_payload)

    def record_audit(self, dashboard_id, actor_id, action, **kwargs):
        self.audit_events.append((dashboard_id, actor_id, action, kwargs))

    def list_publications(self, dashboard_id, actor_id):
        assert (dashboard_id, actor_id) == ("dashboard-1", "alice")
        return self.publications

    def get_latest_published_snapshot(self, dashboard_id, actor_id):
        assert (dashboard_id, actor_id) == ("dashboard-1", "alice")
        return DashboardSnapshot(
            dashboard_id=dashboard_id,
            refreshed_at=datetime.now(),
            filters={},
            widgets={
                "value": WidgetQueryResult(
                    widget_id="value",
                    columns=["value"],
                    rows=[[2]],
                    row_count=1,
                    refreshed_at=datetime.now(),
                )
            },
        )

    def rotate_publication(
        self,
        dashboard_id,
        published_revision,
        actor_id,
        *,
        share_expires_in_seconds=None,
    ):
        from dbgpt_app.openapi.api_v1.dashboard.schemas import DashboardPublishResponse

        assert (dashboard_id, published_revision, actor_id) == (
            "dashboard-1",
            1,
            "alice",
        )
        assert share_expires_in_seconds == 3600
        return DashboardPublishResponse(
            dashboard_id=dashboard_id,
            published_revision=published_revision,
            share_token="rotated",
            share_path="/dashboard-share/rotated",
            published_at=datetime.now(),
        )

    def revoke_publication(self, dashboard_id, published_revision, actor_id):
        assert (dashboard_id, published_revision, actor_id) == (
            "dashboard-1",
            1,
            "alice",
        )
        return True

    def filter_public_snapshot(self, token, filters):
        self.public_filter_call = (token, filters)
        return PublicDashboardFilterResponse(
            snapshot=DashboardSnapshot(
                dashboard_id="dashboard-1",
                refreshed_at=datetime.now(),
                filters=filters,
                widgets={
                    "value": WidgetQueryResult(
                        widget_id="value",
                        columns=["value"],
                        rows=[[3]],
                        row_count=1,
                        refreshed_at=datetime.now(),
                    )
                },
            ),
            unsupported_widget_ids=[],
        )


class ScheduledServiceStub:
    def __init__(self):
        self.tasks = {}

    async def create_task(self, request, user_name=None, owner_id=None):
        task = TaskResponse(
            task_id="schedule-1",
            task_name=request.task_name,
            task_type=request.task_type,
            cron_expression=request.cron_expression,
            payload=request.payload,
            owner_id=owner_id,
            user_name=user_name,
        )
        self.tasks[task.task_id] = task
        return task

    async def list_tasks(self, **kwargs):
        return [
            task
            for task in self.tasks.values()
            if task.owner_id == kwargs.get("owner_id")
            and isinstance(task.payload, DashboardRefreshPayload)
            and task.payload.dashboard_id == kwargs.get("resource_id")
        ]

    async def get_task(self, task_id, owner_id=None):
        task = self.tasks.get(task_id)
        return task if task and task.owner_id == owner_id else None

    async def toggle_task(self, task_id, enabled, owner_id=None):
        task = await self.get_task(task_id, owner_id=owner_id)
        if task is None:
            raise ValueError("Task not found")
        task.enabled = enabled
        return task


def test_preview_uses_current_unsaved_schema_after_owner_check():
    service = ApiServiceStub()
    current = _schema("SELECT 2 AS value")

    response = preview_widget(
        "dashboard-1",
        "value",
        DashboardWidgetPreviewRequest(filters={}, schema=current),
        UserRequest(user_id="alice"),
        service,
    )

    assert response.data.rows == [[2]]
    assert service.preview_schema.widgets[0].query.sql == "SELECT 2 AS value"


def test_resolve_dashboard_reference_reads_authorized_dashboard():
    service = ApiServiceStub()

    response = resolve_dashboard_reference(
        "dashboard-1",
        DashboardTargetResolutionRequest(
            reference="这个图太挤了", selected_widget_id="value"
        ),
        UserRequest(user_id="alice"),
        service,
    )

    assert response.data.status.value == "resolved"
    assert response.data.target.widget_id == "value"


def test_edit_version_api_lists_previews_and_restores_as_new_revision():
    service = ApiServiceStub()

    listed = list_dashboard_edit_versions(
        "dashboard-1",
        25,
        0,
        UserRequest(user_id="alice"),
        service,
    )
    detail = get_dashboard_edit_version(
        "dashboard-1", 1, UserRequest(user_id="alice"), service
    )
    restored = restore_dashboard_edit_version(
        "dashboard-1",
        1,
        DashboardStateRequest(expected_revision=2),
        UserRequest(user_id="alice"),
        service,
    )

    assert listed.data[0].revision == 1
    assert detail.data.schema_payload.dashboard.title == "API test"
    assert restored.data.id == "dashboard-1"


def test_editor_can_restore_latest_published_snapshot():
    service = ApiServiceStub()

    response = get_latest_dashboard_snapshot(
        "dashboard-1", UserRequest(user_id="alice"), service
    )

    assert response.data.widgets["value"].rows == [[2]]


def test_revision_conflict_is_http_409():
    service = ApiServiceStub()
    service.raise_conflict = True

    with pytest.raises(HTTPException) as raised:
        update_dashboard(
            "dashboard-1",
            DashboardUpdateRequest(schema=_schema(), expected_revision=1),
            UserRequest(user_id="alice"),
            service,
        )

    assert raised.value.status_code == 409
    assert "revision conflict" in raised.value.detail


def test_validate_owner_checks_and_accepts_unsaved_schema_on_same_data_source():
    service = ApiServiceStub()
    current = _schema("SELECT 2 AS value")

    response = validate_dashboard(
        "dashboard-1",
        DashboardValidateRequest(schema=current, execute_queries=True),
        UserRequest(user_id="alice"),
        service,
    )

    assert response.data.valid is True
    assert service.validated_schema.widgets[0].query.sql == "SELECT 2 AS value"


def test_validate_rejects_unsaved_data_source_switch():
    service = ApiServiceStub()
    current = _schema()
    current.dashboard.data_source_id = "another-source"
    current.widgets[0].query.data_source_id = "another-source"

    with pytest.raises(HTTPException) as raised:
        validate_dashboard(
            "dashboard-1",
            DashboardValidateRequest(schema=current, execute_queries=True),
            UserRequest(user_id="alice"),
            service,
        )

    assert raised.value.status_code == 422
    assert raised.value.detail[0]["code"] == (
        "validation_data_source_change_not_allowed"
    )


def test_legacy_import_api_creates_a_new_schema_v1_draft():
    service = ApiServiceStub()
    response = import_legacy_dashboard(
        LegacyDashboardImportRequest(
            data_source_id="demo",
            report={
                "conv_uid": "legacy-conversation",
                "template_name": "Legacy dashboard",
                "charts": [
                    {
                        "chart_uid": "legacy-kpi",
                        "chart_name": "Total",
                        "chart_type": "IndicatorValue",
                        "chart_desc": "",
                        "chart_sql": "SELECT 1 AS value",
                        "column_name": ["value"],
                        "values": [],
                    }
                ],
            },
        ),
        UserRequest(user_id="alice"),
        service,
    )

    assert response.data.schema_payload.dashboard.title == "Legacy dashboard"
    imported = service.created_request.schema_payload
    assert imported.widgets[0].type.value == "kpi"
    assert imported.metadata.conversation_id == "legacy-conversation"


def test_publication_lifecycle_api_never_returns_stored_token_hashes():
    service = ApiServiceStub()
    service.publications = [
        DashboardShareRecord(
            id=1,
            dashboard_id="dashboard-1",
            published_revision=1,
            created_by="alice",
            created_at=datetime.now(),
            active=True,
        )
    ]
    user = UserRequest(user_id="alice")

    listed = list_dashboard_publications("dashboard-1", user, service)
    assert listed.data[0].active is True
    assert "token" not in listed.data[0].model_dump()

    rotated = rotate_dashboard_publication(
        "dashboard-1",
        1,
        DashboardShareRotateRequest(share_expires_in_seconds=3600),
        user,
        service,
    )
    assert rotated.data.share_token == "rotated"
    assert revoke_dashboard_publication("dashboard-1", 1, user, service).data is True


def test_public_snapshot_filter_is_anonymous_and_uses_only_supplied_filters():
    service = ApiServiceStub()

    response = filter_public_dashboard(
        "share-token",
        PublicDashboardFilterRequest(filters={"year": 2024}),
        service,
    )

    assert service.public_filter_call == ("share-token", {"year": 2024})
    assert response.data.snapshot.filters == {"year": 2024}
    assert response.data.snapshot.widgets["value"].rows == [[3]]


@pytest.mark.asyncio
async def test_dashboard_schedule_api_binds_owner_resource_and_audit():
    service = ApiServiceStub()
    scheduled = ScheduledServiceStub()
    user = UserRequest(user_id="alice", nick_name="Alice")

    created = await create_dashboard_schedule(
        "dashboard-1",
        DashboardScheduleCreateRequest(
            task_name="Daily refresh",
            cron_expression="0 6 * * *",
            filters={"region": "east"},
            publish_after_refresh=True,
        ),
        user,
        service,
        scheduled,
    )

    assert created.data.owner_id == "alice"
    assert created.data.payload.dashboard_id == "dashboard-1"
    assert created.data.payload.publish_after_refresh is True
    assert service.required_action.value == "manage_schedule"
    assert service.audit_events[-1][2] == "schedule.created"

    listed = await list_dashboard_schedules("dashboard-1", user, service, scheduled)
    assert [task.task_id for task in listed.data] == ["schedule-1"]

    toggled = await toggle_dashboard_schedule(
        "dashboard-1",
        "schedule-1",
        DashboardScheduleToggleRequest(enabled=False),
        user,
        service,
        scheduled,
    )
    assert toggled.data.enabled is False
    assert service.audit_events[-1][2] == "schedule.toggled"


@pytest.mark.asyncio
async def test_dashboard_schedule_api_hides_another_owners_schedule():
    service = ApiServiceStub()
    scheduled = ScheduledServiceStub()
    scheduled.tasks["schedule-1"] = TaskResponse(
        task_id="schedule-1",
        task_name="Private refresh",
        task_type="dashboard_refresh",
        cron_expression="0 6 * * *",
        payload=DashboardRefreshPayload(dashboard_id="dashboard-1"),
        owner_id="bob",
    )

    with pytest.raises(HTTPException) as raised:
        await toggle_dashboard_schedule(
            "dashboard-1",
            "schedule-1",
            DashboardScheduleToggleRequest(enabled=False),
            UserRequest(user_id="alice"),
            service,
            scheduled,
        )

    assert raised.value.status_code == 404
