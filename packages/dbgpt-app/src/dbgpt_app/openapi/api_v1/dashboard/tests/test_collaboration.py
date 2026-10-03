import asyncio
import json

import pytest
from fastapi import WebSocketDisconnect

from dbgpt.storage.metadata import DatabaseManager, Model
from dbgpt_app.openapi.api_v1.dashboard.access import DashboardAuthorizationService
from dbgpt_app.openapi.api_v1.dashboard.collaboration import (
    CollaborationTicketStore,
    DashboardCollaborationHub,
    DashboardCollaborationService,
    DashboardPatchError,
    RedisDashboardTicketStore,
    apply_dashboard_patch,
    create_collaboration_ticket_store,
)
from dbgpt_app.openapi.api_v1.dashboard.models import (
    DashboardAccessDao,
    DashboardAccessDeniedError,
    DashboardAuditDao,
    DashboardConflictError,
    DashboardDao,
)
from dbgpt_app.openapi.api_v1.dashboard.planner import DashboardPlannerService
from dbgpt_app.openapi.api_v1.dashboard.schemas import (
    DashboardAssetState,
    DashboardCreateRequest,
    DashboardOperationRequest,
    DashboardOrigin,
    DashboardPatchOperation,
    DashboardPlan,
    DashboardQueryDraftRequest,
    DashboardRole,
    DashboardSchemaV1,
)
from dbgpt_app.openapi.api_v1.dashboard.service import (
    DashboardSchemaValidationError,
    DashboardService,
)
from dbgpt_app.openapi.api_v1.tools.dashboard import make_dashboard_planner_tools


def _schema():
    return DashboardSchemaV1.model_validate(
        {
            "schema_version": "1.0",
            "dashboard": {
                "id": "collab-dashboard",
                "title": "Original",
                "data_source_id": "demo",
            },
            "widgets": [
                {
                    "id": "value",
                    "type": "kpi",
                    "title": "Value",
                    "query": {
                        "data_source_id": "demo",
                        "sql": "SELECT 1 AS value",
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


@pytest.fixture
def collaboration_service():
    return _make_collaboration_service()


def _make_collaboration_service(
    data_source_policy=None, connector=None, *, generated=False
):
    manager = DatabaseManager()
    manager.init_db("sqlite:///:memory:", base=Model)
    Model.metadata.create_all(manager.engine)
    dao = DashboardDao(manager)
    authorization = DashboardAuthorizationService(
        dashboard_dao=dao,
        access_dao=DashboardAccessDao(manager),
        audit_dao=DashboardAuditDao(manager),
        data_source_policy=data_source_policy,
        require_data_source_authorizer=data_source_policy is not None,
    )
    dashboard_service = DashboardService(
        dao=dao,
        authorization_service=authorization,
        connector_resolver=lambda _source_id: connector or _Connector(),
    )
    dashboard_service.create_dashboard(
        DashboardCreateRequest(
            schema=_schema(),
            origin=DashboardOrigin.TASK if generated else DashboardOrigin.MANUAL,
            asset_state=(
                DashboardAssetState.GENERATED
                if generated
                else DashboardAssetState.SAVED
            ),
        ),
        "alice",
    )
    return DashboardCollaborationService(dashboard_service)


class _Connector:
    db_type = "sqlite"

    def __init__(self):
        self.calls = []

    def get_table_names(self):
        return ["sales"]

    def get_fields(self, *_args):
        return [("sales", "number")]

    def query_ex(self, _sql, params=None, timeout=None):
        self.calls.append((_sql, params, timeout))
        return ["value"], [(1,)]


def _request(
    operation_id="operation-1", revision=1, *, path="/dashboard/title", value="Updated"
):
    return DashboardOperationRequest(
        operation_id=operation_id,
        client_id="browser-a",
        expected_revision=revision,
        operations=[DashboardPatchOperation(op="replace", path=path, value=value)],
    )


def test_operation_is_atomic_persisted_and_idempotent(collaboration_service):
    first = collaboration_service.apply_operation(
        "collab-dashboard", _request(), "alice"
    )
    assert first.dashboard.current_revision == 2
    assert first.dashboard.schema_payload.dashboard.title == "Updated"
    assert first.operation.applied_revision == 2
    assert first.replayed is False
    version = collaboration_service.dashboard_service.dao.get_edit_version(
        "collab-dashboard", 2
    )
    assert version.source == "manual_edit"
    assert version.operation_id == "operation-1"

    replay = collaboration_service.apply_operation(
        "collab-dashboard", _request(), "alice"
    )
    assert replay.replayed is True
    assert replay.dashboard.current_revision == 2
    assert len(collaboration_service.list_operations("collab-dashboard", "alice")) == 1
    assert (
        len(
            collaboration_service.dashboard_service.dao.list_edit_versions(
                "collab-dashboard"
            )
        )
        == 2
    )


def test_generated_draft_refresh_save_does_not_promote_until_explicit_save():
    collaboration = _make_collaboration_service(generated=True)
    refresh_request = _request()
    refresh_request.promote_to_asset = False

    refreshed = collaboration.apply_operation(
        "collab-dashboard", refresh_request, "alice"
    )
    assert refreshed.dashboard.asset_state == DashboardAssetState.GENERATED
    assert refreshed.dashboard.saved_at is None

    saved = collaboration.apply_operation(
        "collab-dashboard",
        _request("operation-2", revision=2, value="Explicitly saved"),
        "alice",
    )
    assert saved.dashboard.asset_state == DashboardAssetState.SAVED
    assert saved.dashboard.saved_at is not None


def test_stale_revision_is_rejected_without_losing_first_edit(collaboration_service):
    collaboration_service.apply_operation("collab-dashboard", _request(), "alice")
    with pytest.raises(DashboardConflictError):
        collaboration_service.apply_operation(
            "collab-dashboard",
            _request("operation-2", 1, value="Stale"),
            "alice",
        )
    record = collaboration_service.dashboard_service.get_dashboard(
        "collab-dashboard", "alice"
    )
    assert record.current_revision == 2
    assert record.schema_payload.dashboard.title == "Updated"


@pytest.mark.parametrize(
    "path",
    [
        "/dashboard",
        "/dashboard/id",
        "/dashboard/data_source_id",
        "/dashboard/status",
        "/metadata/agent",
        "/widgets/0/query/last_execution/status",
    ],
)
def test_server_managed_paths_are_protected(collaboration_service, path):
    with pytest.raises(DashboardPatchError):
        collaboration_service.apply_operation(
            "collab-dashboard", _request(path=path, value="tampered"), "alice"
        )
    assert (
        collaboration_service.dashboard_service.get_dashboard(
            "collab-dashboard", "alice"
        ).current_revision
        == 1
    )


def test_invalid_result_rolls_back(collaboration_service):
    with pytest.raises(DashboardSchemaValidationError):
        collaboration_service.apply_operation(
            "collab-dashboard", _request(value=""), "alice"
        )
    record = collaboration_service.dashboard_service.get_dashboard(
        "collab-dashboard", "alice"
    )
    assert record.current_revision == 1
    assert record.schema_payload.dashboard.title == "Original"


def test_legacy_dashboard_can_atomically_upgrade_to_schema_1_3(
    collaboration_service,
):
    widget = _schema().widgets[0].model_dump(mode="json")
    widget["query"]["output_fields"].extend(
        [
            {"name": "month", "type": "string"},
            {"name": "store", "type": "string"},
        ]
    )
    widget["encoding"].update({"row": "month", "column": "store", "value": "value"})
    widget["presentation"] = {"visualization": "heatmap"}
    request = DashboardOperationRequest(
        operation_id="upgrade-to-1-3",
        client_id="browser-a",
        expected_revision=1,
        operations=[
            DashboardPatchOperation(op="replace", path="/schema_version", value="1.3"),
            DashboardPatchOperation(op="replace", path="/widgets", value=[widget]),
        ],
    )

    response = collaboration_service.apply_operation(
        "collab-dashboard", request, "alice"
    )

    assert response.dashboard.current_revision == 2
    assert response.dashboard.schema_payload.schema_version == "1.3"
    assert (
        response.dashboard.schema_payload.widgets[0].presentation.visualization.value
        == "heatmap"
    )


def test_unsupported_schema_upgrade_rolls_back(collaboration_service):
    with pytest.raises(DashboardSchemaValidationError):
        collaboration_service.apply_operation(
            "collab-dashboard",
            _request(path="/schema_version", value="99.0"),
            "alice",
        )
    record = collaboration_service.dashboard_service.get_dashboard(
        "collab-dashboard", "alice"
    )
    assert record.current_revision == 1
    assert record.schema_payload.schema_version == "1.0"


def test_collaboration_sql_edit_recomputes_server_owned_lineage(
    collaboration_service,
):
    response = collaboration_service.apply_operation(
        "collab-dashboard",
        _request(
            path="/widgets/0/query/sql",
            value="SELECT sales AS value FROM sales",
        ),
        "alice",
    )
    lineage = response.dashboard.schema_payload.widgets[0].query.lineage
    assert len(lineage.sources) == 1
    assert lineage.sources[0].tables == ["sales"]
    assert lineage.sources[0].columns == ["sales"]


def test_schema_changes_cannot_introduce_an_unauthorized_data_source():
    class DemoOnlyPolicy:
        def can_query(self, actor_id: str, data_source_id: str) -> bool:
            return actor_id == "alice" and data_source_id == "demo"

    collaboration = _make_collaboration_service(DemoOnlyPolicy())
    blocked = _schema().model_copy(deep=True)
    blocked.dashboard.id = "payroll-dashboard"
    blocked.dashboard.data_source_id = "payroll"
    blocked.widgets[0].query.data_source_id = "payroll"
    with pytest.raises(DashboardAccessDeniedError, match="payroll"):
        collaboration.dashboard_service.create_dashboard(
            DashboardCreateRequest(schema=blocked), "alice"
        )

    current = collaboration.dashboard_service.get_dashboard("collab-dashboard", "alice")
    changed = current.schema_payload.model_copy(deep=True)
    changed.widgets[0].query.data_source_id = "payroll"

    with pytest.raises(DashboardAccessDeniedError, match="payroll"):
        collaboration.dashboard_service.update_dashboard(
            "collab-dashboard", changed, current.current_revision, "alice"
        )

    with pytest.raises(DashboardAccessDeniedError, match="payroll"):
        collaboration.apply_operation(
            "collab-dashboard",
            _request(
                operation_id="bind-payroll",
                path="/widgets/0/query/data_source_id",
                value="payroll",
            ),
            "alice",
        )
    assert (
        collaboration.dashboard_service.get_dashboard(
            "collab-dashboard", "alice"
        ).current_revision
        == 1
    )


def test_revoked_source_access_is_checked_before_publish_executes_sql():
    class TogglePolicy:
        allowed = True

        def can_query(self, actor_id: str, data_source_id: str) -> bool:
            return self.allowed and actor_id == "alice" and data_source_id == "demo"

    policy = TogglePolicy()
    connector = _Connector()
    collaboration = _make_collaboration_service(policy, connector)
    policy.allowed = False

    with pytest.raises(DashboardAccessDeniedError, match="demo"):
        collaboration.dashboard_service.publish_dashboard(
            "collab-dashboard", 1, {}, "alice"
        )
    assert connector.calls == []


def test_revoked_source_access_is_checked_before_agent_sql_execution():
    class TogglePolicy:
        allowed = True

        def can_query(self, actor_id: str, data_source_id: str) -> bool:
            return self.allowed and actor_id == "alice" and data_source_id == "demo"

    policy = TogglePolicy()
    connector = _Connector()
    collaboration = _make_collaboration_service(policy, connector)
    planner = DashboardPlannerService(collaboration.dashboard_service)
    plan = DashboardPlan.model_validate(
        {
            "title": "Permission test",
            "business_theme": "Security",
            "metrics": ["value"],
            "widgets": [
                {
                    "id": "value",
                    "type": "kpi",
                    "title": "Value",
                    "business_question": "What is the value?",
                    "metric": "value",
                }
            ],
        }
    )
    pending = asyncio.run(
        planner.create_plan_draft(
            plan=plan,
            data_source_id="demo",
            owner_id="alice",
            conversation_id="permission-check",
            prompt="Build a dashboard",
            model_name="mock",
            request_token="turn-one",
        )
    )
    queries = DashboardQueryDraftRequest.model_validate(
        {
            "dashboard_id": pending.id,
            "expected_revision": pending.current_revision,
            "widgets": [
                {
                    "widget_id": "value",
                    "sql": "SELECT 1 AS value",
                    "output_fields": [{"name": "value", "type": "number"}],
                    "encoding": {"value": "value"},
                }
            ],
        }
    )
    policy.allowed = False

    with pytest.raises(DashboardAccessDeniedError, match="demo"):
        asyncio.run(
            planner.complete_plan_draft(
                dashboard_id=pending.id,
                query_request=queries,
                owner_id="alice",
                request_token="turn-two",
            )
        )
    assert connector.calls == []


@pytest.mark.asyncio
async def test_agent_modification_is_validated_and_saved_as_one_operation(
    collaboration_service,
):
    events = []

    async def capture(event_type, payload):
        events.append((event_type, payload))

    state = {"conv_id": "modify-conv"}
    tools = {
        item._tool.name: item
        for item in make_dashboard_planner_tools(
            react_state=state,
            database_connector=_Connector(),
            database_name="demo",
            owner_id="alice",
            user_prompt="Rename dashboard collab-dashboard to Agent updated",
            model_name="mock-model",
            stream_callback=capture,
            planner_service=DashboardPlannerService(
                collaboration_service.dashboard_service
            ),
        )
    }
    await tools["load_dashboard_draft"]("collab-dashboard")
    result = json.loads(
        await tools["modify_dashboard_draft"](
            dashboard_id="collab-dashboard",
            operations=json.dumps(
                [
                    {
                        "op": "replace",
                        "path": "/dashboard/title",
                        "value": "Agent updated",
                    }
                ]
            ),
        )
    )
    assert result["__dashboard__"]["current_revision"] == 2
    assert (
        collaboration_service.dashboard_service.dao.get_edit_version(
            "collab-dashboard", 2
        ).source
        == "ai_edit"
    )
    assert (
        collaboration_service.dashboard_service.get_dashboard(
            "collab-dashboard", "alice"
        ).schema_payload.dashboard.title
        == "Agent updated"
    )
    assert events[-1][0] == "dashboard.updated"


def test_same_operation_id_cannot_be_reused_for_another_edit(collaboration_service):
    collaboration_service.apply_operation("collab-dashboard", _request(), "alice")
    with pytest.raises(DashboardConflictError):
        collaboration_service.apply_operation(
            "collab-dashboard", _request(value="Different"), "alice"
        )


def test_patch_supports_list_add_and_remove():
    source = {"widgets": [{"id": "one"}], "dashboard": {"title": "x"}}
    added = apply_dashboard_patch(
        source,
        [DashboardPatchOperation(op="add", path="/widgets/-", value={"id": "two"})],
    )
    removed = apply_dashboard_patch(
        added, [DashboardPatchOperation(op="remove", path="/widgets/0")]
    )
    assert source["widgets"] == [{"id": "one"}]
    assert removed["widgets"] == [{"id": "two"}]


def test_ticket_is_one_time_scoped_and_expires():
    now = [100.0]
    store = CollaborationTicketStore(ttl_seconds=10, clock=lambda: now[0])
    issued = store.issue("dashboard-a", "alice", "client-a")
    claim = store.consume(issued.ticket, "dashboard-a")
    assert claim.actor_id == "alice"
    with pytest.raises(DashboardPatchError, match="already used"):
        store.consume(issued.ticket, "dashboard-a")

    wrong = store.issue("dashboard-a", "alice", "client-a")
    with pytest.raises(DashboardPatchError, match="another dashboard"):
        store.consume(wrong.ticket, "dashboard-b")

    expired = store.issue("dashboard-a", "alice", "client-a")
    now[0] = 111.0
    with pytest.raises(DashboardPatchError, match="expired"):
        store.consume(expired.ticket, "dashboard-a")


class _FakeSharedRedis:
    def __init__(self):
        self.values = {}

    def set(self, key, value, ex=None, nx=False):
        if nx and key in self.values:
            return False
        self.values[key] = value
        return True

    def eval(self, script, key_count, key):
        return self.values.pop(key, None)


def test_redis_ticket_can_be_issued_and_consumed_by_different_workers():
    redis = _FakeSharedRedis()
    worker_a = RedisDashboardTicketStore(client=redis)
    worker_b = RedisDashboardTicketStore(client=redis)

    issued = worker_a.issue("dashboard-a", "alice", "client-a")
    claim = worker_b.consume(issued.ticket, "dashboard-a")

    assert (claim.actor_id, claim.client_id) == ("alice", "client-a")
    with pytest.raises(DashboardPatchError, match="already used"):
        worker_a.consume(issued.ticket, "dashboard-a")


def test_production_ticket_factory_fails_closed_without_redis():
    with pytest.raises(RuntimeError, match="requires"):
        create_collaboration_ticket_store(redis_url=None, production_mode=True)


class _FakeWebSocket:
    def __init__(self):
        self.messages = []

    async def send_json(self, message):
        self.messages.append(message)


def test_hub_broadcasts_presence_and_messages():
    async def run():
        hub = DashboardCollaborationHub()
        first = _FakeWebSocket()
        second = _FakeWebSocket()
        first_id = await hub.connect("dash", first, "alice", "client-a")
        await hub.connect("dash", second, "bob", "client-b")
        assert await hub.presence("dash") == [
            {"actor_id": "alice", "client_id": "client-a"},
            {"actor_id": "bob", "client_id": "client-b"},
        ]
        await hub.broadcast("dash", {"type": "operation.accepted"})
        assert first.messages == second.messages == [{"type": "operation.accepted"}]
        await hub.disconnect("dash", first_id)
        assert await hub.presence("dash") == [
            {"actor_id": "bob", "client_id": "client-b"}
        ]

    asyncio.run(run())


class _RouteWebSocket(_FakeWebSocket):
    def __init__(self, ticket, incoming=None):
        super().__init__()
        self.query_params = {"ticket": ticket}
        self.incoming = list(incoming or [])
        self.accepted = False
        self.close_code = None

    async def accept(self):
        self.accepted = True

    async def close(self, code, reason=None):
        self.close_code = code

    async def receive_json(self):
        if self.incoming:
            return self.incoming.pop(0)
        raise WebSocketDisconnect()


def test_websocket_route_authenticates_ticket_and_broadcasts_operation(
    collaboration_service, monkeypatch
):
    from dbgpt_app.openapi.api_v1.dashboard import api

    store = CollaborationTicketStore()
    issued = store.issue("collab-dashboard", "alice", "browser-a")
    hub = DashboardCollaborationHub()
    socket = _RouteWebSocket(
        issued.ticket,
        incoming=[
            {
                "type": "operation",
                "payload": _request().model_dump(mode="json"),
            }
        ],
    )
    monkeypatch.setattr(api, "ticket_store", store)
    monkeypatch.setattr(api, "collaboration_hub", hub)
    monkeypatch.setattr(
        api, "DashboardCollaborationService", lambda: collaboration_service
    )

    asyncio.run(api.collaborate_dashboard(socket, "collab-dashboard"))

    assert socket.accepted is True
    assert socket.close_code is None
    assert {message["type"] for message in socket.messages} >= {
        "collaboration.ready",
        "presence.changed",
        "operation.accepted",
    }
    assert (
        collaboration_service.dashboard_service.get_dashboard(
            "collab-dashboard", "alice"
        ).current_revision
        == 2
    )


def test_websocket_route_denies_viewer_edit_ticket(collaboration_service, monkeypatch):
    from dbgpt_app.openapi.api_v1.dashboard import api

    collaboration_service.dashboard_service.upsert_member(
        "collab-dashboard", "alice", "bob", DashboardRole.VIEWER
    )
    store = CollaborationTicketStore()
    issued = store.issue("collab-dashboard", "bob", "browser-b")
    socket = _RouteWebSocket(issued.ticket)
    monkeypatch.setattr(api, "ticket_store", store)
    monkeypatch.setattr(
        api, "DashboardCollaborationService", lambda: collaboration_service
    )

    asyncio.run(api.collaborate_dashboard(socket, "collab-dashboard"))

    assert socket.accepted is False
    assert socket.close_code == 4403
