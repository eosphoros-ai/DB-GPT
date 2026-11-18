"""Verified-owner constraints at conversation and flow data access boundaries."""

import asyncio
import hashlib
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from dbgpt_serve.conversation.api import endpoints as conversation_endpoints
from dbgpt_serve.conversation.api.schemas import (
    ServeRequest as ConversationRequest,
)
from dbgpt_serve.conversation.api.schemas import (
    ServerResponse as ConversationResponse,
)
from dbgpt_serve.conversation.service.service import Service as ConversationService
from dbgpt_serve.flow.api import endpoints as flow_endpoints
from dbgpt_serve.flow.api.schemas import (
    ServeRequest as FlowRequest,
)
from dbgpt_serve.flow.api.schemas import (
    VariablesRequest,
)
from dbgpt_serve.flow.service import service as flow_module
from dbgpt_serve.flow.service.variables_service import VariablesService
from dbgpt_serve.utils.auth import v1_auth_middleware


class _ConversationDao:
    def __init__(self):
        self.rows = {"a": "owner-a", "b": "owner-b"}
        self.last_query = None

    def get_one(self, request):
        self.last_query = request
        if self.rows.get(request.conv_uid) == request.user_name:
            return SimpleNamespace(conv_uid=request.conv_uid)
        return None

    def get_conv_by_page(self, request, page, page_size):
        self.last_query = request
        return SimpleNamespace(items=[])


def test_conversation_uid_operations_require_stored_owner():
    service = object.__new__(ConversationService)
    service._dao = _ConversationDao()
    calls = []
    service.create_storage_conv = lambda request: (
        calls.append(request)
        or SimpleNamespace(delete=lambda: None, clear=lambda: None)
    )

    for method in (service.delete, service.clear, service.get_history_messages):
        with pytest.raises(HTTPException) as exc:
            method(
                ConversationRequest(conv_uid="b", user_name="owner-b"), owner="owner-a"
            )
        assert exc.value.status_code == 404
    assert calls == []

    assert service.get(ConversationRequest(conv_uid="b"), owner="owner-a") is None
    assert service.get(ConversationRequest(conv_uid="a"), owner="owner-a") is not None
    service.get_list_by_page(
        ConversationRequest(user_name="owner-b"), 1, 10, owner="owner-a"
    )
    assert service.dao.last_query.user_name == "owner-a"
    service.delete(ConversationRequest(conv_uid="a"), owner="owner-a")
    assert calls[0].user_name == "owner-a"


class _FlowDao:
    def __init__(self):
        self.rows = {"a": "owner-a", "b": "owner-b"}
        self.last_query = None
        self.deleted = []

    def get_one(self, request):
        self.last_query = request
        uid = request.get("uid")
        owner = request.get("user_name")
        if uid in self.rows and (owner is None or owner == self.rows[uid]):
            return SimpleNamespace(
                uid=uid, dag_id=None, state=flow_module.State.INITIALIZING
            )
        return None

    def get_list_page(self, request, page, page_size, **kwargs):
        self.last_query = request
        return SimpleNamespace(items=[])

    def delete(self, request):
        self.deleted.append(request)


def test_flow_read_update_delete_and_list_are_owner_scoped(monkeypatch):
    service = object.__new__(flow_module.Service)
    service._dao = _FlowDao()
    service._dag_manager = SimpleNamespace(
        get_dag_metadata=lambda *args, **kwargs: None
    )
    monkeypatch.setattr(flow_module, "fill_flow_panel", lambda flow: None)

    assert service.get({"uid": "b", "user_name": "owner-b"}, owner="owner-a") is None
    assert service.get({"uid": "a"}, owner="owner-a") is not None
    service.get_list_by_page({"user_name": "owner-b"}, 1, 10, owner="owner-a")
    assert service.dao.last_query["user_name"] == "owner-a"
    with pytest.raises(HTTPException) as exc:
        service.delete("b", owner="owner-a")
    assert exc.value.status_code == 404
    assert service.dao.deleted == []

    async def check_callable():
        with pytest.raises(HTTPException) as exc:
            await service._get_callable_task("b", owner="owner-a")
        assert exc.value.status_code == 404

    asyncio.run(check_callable())

    request = FlowRequest(
        uid="b", label="Other flow", name="other", user_name="owner-b"
    )
    with pytest.raises(HTTPException) as exc:
        service.update_flow(request, owner="owner-a")
    assert exc.value.status_code == 404
    assert service.dao.deleted == []


def test_owned_draft_cannot_run_or_unregister_another_flows_dag(monkeypatch):
    class Dao:
        deleted = []

        def get_one(self, query):
            if query == {"uid": "draft", "user_name": "owner-a"}:
                return SimpleNamespace(
                    uid="draft",
                    dag_id="other-dag",
                    state=flow_module.State.INITIALIZING,
                )
            return None

        def delete(self, query):
            self.deleted.append(query)

        def get_list_page(self, query, page, page_size, **kwargs):
            return SimpleNamespace(items=[self.get_one({"uid": "draft", **query})])

    unregistered = []
    metadata_lookups = []
    foreign_task = object()
    service = object.__new__(flow_module.Service)
    service._dao = Dao()
    service._dag_manager = SimpleNamespace(
        dag_map={"other-dag": SimpleNamespace(leaf_nodes=[foreign_task])},
        dag_alias_map={"other-flow": "other-dag"},
        get_dag_metadata=lambda *args, **kwargs: metadata_lookups.append(args)
        or SimpleNamespace(to_dict=lambda: {"foreign": True}),
        unregister_dag=unregistered.append,
    )
    monkeypatch.setattr(flow_module, "fill_flow_panel", lambda flow: None)

    assert not hasattr(service.get({"uid": "draft"}, owner="owner-a"), "metadata")
    page = service.get_list_by_page({}, 1, 10, owner="owner-a")
    assert not hasattr(page.items[0], "metadata")
    assert metadata_lookups == []
    with pytest.raises(HTTPException) as exc:
        asyncio.run(service._get_callable_task("draft", owner="owner-a"))
    assert exc.value.status_code == 404

    service.delete("draft", owner="owner-a")
    assert unregistered == []
    assert service.dao.deleted == [{"uid": "draft", "user_name": "owner-a"}]


def test_owned_registered_flow_can_run_and_unregister_its_dag(monkeypatch):
    class Dao:
        def get_one(self, query):
            if query == {"uid": "own", "user_name": "owner-a"}:
                return SimpleNamespace(
                    uid="own", dag_id="own-dag", state=flow_module.State.RUNNING
                )
            return None

        def delete(self, query):
            pass

    unregistered = []
    own_task = object()
    service = object.__new__(flow_module.Service)
    service._dao = Dao()
    service._dag_manager = SimpleNamespace(
        dag_map={"own-dag": SimpleNamespace(leaf_nodes=[own_task])},
        dag_alias_map={"own": "own-dag"},
        get_dag_metadata=lambda *args, **kwargs: None,
        unregister_dag=unregistered.append,
    )
    monkeypatch.setattr(flow_module, "fill_flow_panel", lambda flow: None)

    assert asyncio.run(service._get_callable_task("own", owner="owner-a")) is own_task
    service.delete("own", owner="owner-a")
    assert unregistered == ["own-dag"]


def test_flow_create_and_update_ignore_caller_dag_identifiers():
    class BuildStopped(Exception):
        pass

    class Factory:
        seen = []

        def build(self, request):
            self.seen.append(request.dag_id)
            raise BuildStopped

    class Dao:
        def get_one(self, query):
            return SimpleNamespace(dag_id="own-dag")

    service = object.__new__(flow_module.Service)
    service._flow_factory = Factory()
    service._dao = Dao()

    create_request = FlowRequest(
        uid="new", label="New flow", name="new", dag_id="other-dag"
    )
    with pytest.raises(ValueError):
        service.create_and_save_dag(create_request, owner="owner-a")
    assert service._flow_factory.seen == [None]

    update_request = FlowRequest(
        uid="own", label="Own flow", name="own", dag_id="other-dag"
    )
    with pytest.raises(BuildStopped):
        service.update_flow(update_request, owner="owner-a")
    assert service._flow_factory.seen == [None, "own-dag"]


def test_builtin_variable_providers_query_only_verified_owner(monkeypatch):
    from dbgpt_serve.flow.api import variables_provider

    class Dao:
        queries = []
        rows = [
            SimpleNamespace(
                name=name,
                label=name,
                value=value,
                category=category,
                value_type="str",
                enabled=True,
                description=None,
                user_name=owner,
            )
            for owner, category, name, value in (
                ("owner-a", "common", "mine", "own-common"),
                ("owner-b", "common", "other", "foreign-common"),
                ("owner-a", "secret", "mine-secret", "own-secret"),
                ("owner-b", "secret", "other-secret", "foreign-secret"),
            )
        ]

        def get_list(self, query):
            self.queries.append(query)
            return [
                row
                for row in self.rows
                if row.category == query["category"]
                and (not query.get("user_name") or row.user_name == query["user_name"])
            ]

    service = object.__new__(VariablesService)
    service._dao = Dao()
    monkeypatch.setattr(variables_provider, "get_variable_service", lambda: service)

    common = variables_provider.BuiltinAllVariablesProvider().get_variables(
        "dbgpt.core.variables", user_name="owner-a"
    )
    secret = variables_provider.BuiltinAllSecretVariablesProvider().get_variables(
        "dbgpt.core.secrets", user_name="owner-a"
    )

    assert [item.value for item in common] == ["own-common"]
    assert [item.value for item in secret] == ["own-secret"]
    assert [query["user_name"] for query in service.dao.queries] == [
        "owner-a",
        "owner-a",
    ]


def test_debug_route_rejects_foreign_owner_before_streaming():
    class Service:
        async def check_debug_flow_owner(self, request, owner):
            raise HTTPException(status_code=404, detail="Flow not found")

        def debug_flow(self, *args, **kwargs):
            raise AssertionError("stream must not be created")

    request = SimpleNamespace(flow=SimpleNamespace(uid="other"))
    with pytest.raises(HTTPException) as exc:
        asyncio.run(flow_endpoints.debug_flow(request, Service(), owner="owner-a"))
    assert exc.value.status_code == 404


def test_debug_owner_lookup_is_offloaded(monkeypatch):
    class Dao:
        def get_one(self, query):
            return SimpleNamespace(uid="other") if query == {"uid": "other"} else None

    calls = []

    async def offload(system_app, function, query):
        calls.append(query)
        return function(query)

    service = object.__new__(flow_module.Service)
    service._dao = Dao()
    service._system_app = None
    monkeypatch.setattr(flow_module, "blocking_func_to_async", offload)
    request = SimpleNamespace(flow=SimpleNamespace(uid="other"))

    with pytest.raises(HTTPException) as exc:
        asyncio.run(service.check_debug_flow_owner(request, "owner-a"))
    assert exc.value.status_code == 404
    assert calls == [
        {"uid": "other", "user_name": "owner-a"},
        {"uid": "other"},
    ]


def test_flow_variable_write_and_key_list_use_verified_owner(monkeypatch):
    class Dao:
        last_query = None

        def get_one(self, query):
            self.last_query = query
            return SimpleNamespace(user_name=query["user_name"])

        def get_list(self, query):
            self.last_query = query
            return []

    class Provider:
        saved = None

        def save(self, value):
            self.saved = value

        def get(self, identifier, default):
            return object()

    service = object.__new__(VariablesService)
    service._dao = Dao()
    provider = Provider()
    monkeypatch.setattr(
        VariablesService, "variables_provider", property(lambda _: provider)
    )
    request = VariablesRequest(
        key="k",
        name="n",
        label="L",
        value="v",
        category="common",
        scope="global",
        user_name="owner-b",
    )
    assert service.create(request, owner="owner-a").user_name == "owner-a"
    assert provider.saved.user_name == "owner-a"
    request.user_name = "owner-b"
    assert service.update(1, request, owner="owner-a").user_name == "owner-a"
    assert provider.saved.user_name == "owner-a"
    service.list_keys(user_name="owner-b", owner="owner-a")
    assert service.dao.last_query["user_name"] == "owner-a"


def test_flow_update_keeps_owner_not_found_as_http_404(monkeypatch):
    class Service:
        def update_flow(self, request, owner=None):
            raise HTTPException(status_code=404, detail="Flow not found")

    async def run_direct(_app, func, *args, **kwargs):
        return func(*args, **kwargs)

    monkeypatch.setattr(flow_endpoints, "blocking_func_to_async", run_direct)
    request = FlowRequest(uid="b", label="Other flow", name="other")

    async def check():
        with pytest.raises(HTTPException) as exc:
            await flow_endpoints.update(
                "b", request, service=Service(), owner="owner-a"
            )
        assert exc.value.status_code == 404

    asyncio.run(check())


def test_session_file_owner_ignores_caller_header():
    from dbgpt_serve.session_file.api.endpoints import get_authenticated_owner
    from dbgpt_serve.session_file.config import ServeConfig

    owner = get_authenticated_owner(
        user_id="owner-b",
        _checked_key="key-a",
        config=ServeConfig(api_keys="key-a,key-b"),
        verified_owner="key-verified-owner-a",
    )
    assert owner == "key-verified-owner-a"


def test_conversation_routes_pass_verified_owner_to_service():
    class SpyService:
        config = SimpleNamespace(api_keys="key-a,key-b")

        def __init__(self):
            self.calls = []

        def get(self, request, owner=None):
            self.calls.append(("query", request.user_name, owner))
            return None

        def delete(self, request, owner=None):
            self.calls.append(("delete", request.conv_uid, owner))

        def clear(self, request, owner=None):
            self.calls.append(("clear", request.conv_uid, owner))

        def get_history_messages(self, request, owner=None):
            self.calls.append(("history", request.conv_uid, owner))
            return []

    service = SpyService()
    app = FastAPI()
    app.state.api_keys = ("key-a", "key-b")
    app.middleware("http")(v1_auth_middleware)
    app.include_router(conversation_endpoints.router, prefix="/api/v1/chat/dialogue")
    app.include_router(conversation_endpoints.router, prefix="/api/v2/chat/dialogue")
    app.dependency_overrides[conversation_endpoints.get_service] = lambda: service
    client = TestClient(app)
    headers = {"Authorization": "Bearer key-a", "user-id": "owner-b"}

    assert (
        client.post(
            "/api/v1/chat/dialogue/query",
            json={"conv_uid": "b", "user_name": "owner-b"},
            headers=headers,
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/api/v1/chat/dialogue/delete", params={"con_uid": "b"}, headers=headers
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/api/v1/chat/dialogue/clear", params={"con_uid": "b"}, headers=headers
        ).status_code
        == 200
    )
    assert (
        client.get(
            "/api/v1/chat/dialogue/messages/history",
            params={"con_uid": "b"},
            headers=headers,
        ).status_code
        == 200
    )
    owner = service.calls[0][2]
    assert owner.startswith("key-") and owner != "owner-b"
    assert all(call[2] == owner for call in service.calls)
    assert (
        client.post(
            "/api/v2/chat/dialogue/query",
            json={"conv_uid": "b", "user_name": "owner-b"},
            headers=headers,
        ).status_code
        == 200
    )
    assert service.calls[-1] == ("query", "owner-b", None)


def test_conversation_http_and_storage_boundaries_reject_other_owner():
    owner_a = "key-" + hashlib.sha256(b"key-a").hexdigest()
    owner_b = "key-" + hashlib.sha256(b"key-b").hexdigest()

    class Dao:
        def get_one(self, request):
            if request.conv_uid == "b" and request.user_name == owner_b:
                return ConversationResponse(
                    conv_uid="b", user_input="private", chat_mode="chat_normal"
                )
            return None

    service = object.__new__(ConversationService)
    service._dao = Dao()
    service._serve_config = SimpleNamespace(api_keys="key-a,key-b")
    service.create_storage_conv = lambda request: pytest.fail(
        "foreign conversation storage must not be reached"
    )
    app = FastAPI()
    app.state.api_keys = ("key-a", "key-b")
    app.middleware("http")(v1_auth_middleware)
    app.include_router(conversation_endpoints.router, prefix="/api/v1/chat/dialogue")
    app.dependency_overrides[conversation_endpoints.get_service] = lambda: service
    client = TestClient(app)
    headers_a = {"Authorization": "Bearer key-a", "user-id": owner_b}

    response = client.post(
        "/api/v1/chat/dialogue/query",
        json={"conv_uid": "b", "user_name": owner_b},
        headers=headers_a,
    )
    assert response.status_code == 200
    assert response.json()["data"] is None
    for path, method in (
        ("/delete", client.post),
        ("/clear", client.post),
        ("/messages/history", client.get),
    ):
        response = method(
            "/api/v1/chat/dialogue" + path,
            params={"con_uid": "b"},
            headers=headers_a,
        )
        assert response.status_code == 404

    own = client.post(
        "/api/v1/chat/dialogue/query",
        json={"conv_uid": "b", "user_name": owner_a},
        headers={"Authorization": "Bearer key-b"},
    )
    assert own.status_code == 200
    assert own.json()["data"]["conv_uid"] == "b"


def test_flow_http_and_storage_boundaries_reject_other_owner(monkeypatch):
    owner_b = "key-" + hashlib.sha256(b"key-b").hexdigest()

    class Dao:
        deleted = []

        def get_one(self, query):
            if query.get("uid") == "b" and query.get("user_name") == owner_b:
                return FlowRequest(
                    uid="b", label="Private flow", name="private", user_name=owner_b
                )
            return None

        def delete(self, query):
            self.deleted.append(query)

    service = object.__new__(flow_module.Service)
    service._dao = Dao()
    service._dag_manager = SimpleNamespace(
        get_dag_metadata=lambda *args, **kwargs: None
    )
    monkeypatch.setattr(flow_module, "fill_flow_panel", lambda flow: None)
    app = FastAPI()
    app.state.api_keys = ("key-a", "key-b")
    app.middleware("http")(v1_auth_middleware)
    app.include_router(flow_endpoints.router, prefix="/api/v1/serve/awel")
    app.dependency_overrides[flow_endpoints.get_service] = lambda: service
    client = TestClient(app)
    headers_a = {"Authorization": "Bearer key-a"}
    assert (
        client.get("/api/v1/serve/awel/flows/b", headers=headers_a).status_code == 404
    )
    assert (
        client.delete("/api/v1/serve/awel/flows/b", headers=headers_a).status_code
        == 404
    )
    assert service.dao.deleted == []
    own = client.get(
        "/api/v1/serve/awel/flows/b",
        headers={"Authorization": "Bearer key-b", "user-id": "owner-a"},
    )
    assert own.status_code == 200
    assert own.json()["data"]["uid"] == "b"
