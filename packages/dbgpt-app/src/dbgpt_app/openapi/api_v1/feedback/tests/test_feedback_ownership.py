from types import SimpleNamespace

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from dbgpt.component import SystemApp
from dbgpt.storage.chat_history.chat_history_db import ChatHistoryEntity
from dbgpt.storage.metadata import db
from dbgpt_app.openapi.api_v1.dashboard.identity import (
    DashboardIdentityError,
    configure_dashboard_identity_provider,
)
from dbgpt_app.openapi.api_v1.feedback import api_fb_v1
from dbgpt_app.openapi.api_v1.feedback.feed_back_db import (
    ChatFeedBackDao,
    ChatFeedBackEntity,
)
from dbgpt_serve.feedback.api import endpoints as feedback_serve_endpoints
from dbgpt_serve.feedback.config import ServeConfig
from dbgpt_serve.utils.auth import UserRequest

GATEWAY_SECRET = "unit-test-trusted-gateway-secret"


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """Provide an isolated SQLite metadata database and clean auth env per test."""
    db_file = (tmp_path / "feedback_meta.db").as_posix()
    db.init_db(
        f"sqlite:///{db_file}",
        engine_args={"connect_args": {"check_same_thread": False}},
    )
    db.create_all()
    prev_app = feedback_serve_endpoints.global_system_app
    feedback_serve_endpoints.global_system_app = None
    configure_dashboard_identity_provider(None)
    for env_key in (
        "DBGPT_DASHBOARD_PRODUCTION_MODE",
        "DBGPT_DASHBOARD_IDENTITY_PROVIDER",
        api_fb_v1.TRUSTED_GATEWAY_SECRET_ENV,
        api_fb_v1.DEV_FALLBACK_ENV,
    ):
        monkeypatch.delenv(env_key, raising=False)
    yield
    configure_dashboard_identity_provider(None)
    if db.engine is not None:
        db.engine.dispose()
    feedback_serve_endpoints.global_system_app = prev_app


def _gateway_headers(actor_id: str, secret: str = GATEWAY_SECRET, **extra) -> dict:
    headers = {
        "user-id": actor_id,
        api_fb_v1.TRUSTED_GATEWAY_SIG_HEADER: api_fb_v1.compute_gateway_signature(
            secret, actor_id
        ),
    }
    headers.update(extra)
    return headers


@pytest.fixture
def gateway_client(monkeypatch) -> TestClient:
    monkeypatch.setenv(api_fb_v1.TRUSTED_GATEWAY_SECRET_ENV, GATEWAY_SECRET)
    app = FastAPI()
    app.include_router(api_fb_v1.router, prefix="/api")
    return TestClient(app)


@pytest.fixture
def raw_client() -> TestClient:
    app = FastAPI()
    app.include_router(api_fb_v1.router, prefix="/api")
    return TestClient(app)


def _sample_payload(conv_uid: str = "poc-fb-conv", conv_index: int = 1, **overrides):
    payload = {
        "conv_uid": conv_uid,
        "conv_index": conv_index,
        "question": "POC question marker M5-FB-ALICE",
        "knowledge_space": "poc",
        "score": 5,
        "ques_type": "QA",
        "messages": "POC transcript marker",
    }
    payload.update(overrides)
    return payload


def test_verified_owner_can_commit_update_and_read_back_own_feedback(
    gateway_client: TestClient,
):
    res = gateway_client.post(
        "/api/v1/feedback/commit",
        headers=_gateway_headers("alice"),
        json=_sample_payload(),
    )
    assert res.status_code == 200
    assert res.json()["success"] is True

    found = gateway_client.get(
        "/api/v1/feedback/find",
        params={"conv_uid": "poc-fb-conv", "conv_index": 1},
        headers=_gateway_headers("alice"),
    )
    assert found.status_code == 200
    body = found.json()
    assert body["success"] is True
    assert body["data"]["question"] == "POC question marker M5-FB-ALICE"
    assert body["data"]["messages"] == "POC transcript marker"
    assert body["data"]["score"] == 5
    assert body["data"]["user_name"] == "alice"

    updated = gateway_client.post(
        "/api/v1/feedback/commit",
        headers=_gateway_headers("alice"),
        json=_sample_payload(score=2, messages="Updated alice note"),
    )
    assert updated.status_code == 200
    found_after = gateway_client.get(
        "/api/v1/feedback/find",
        params={"conv_uid": "poc-fb-conv", "conv_index": 1},
        headers=_gateway_headers("alice"),
    ).json()
    assert found_after["data"]["score"] == 2
    assert found_after["data"]["messages"] == "Updated alice note"
    assert found_after["data"]["user_name"] == "alice"


def test_other_verified_user_cannot_read_or_overwrite_feedback(
    gateway_client: TestClient,
):
    gateway_client.post(
        "/api/v1/feedback/commit",
        headers=_gateway_headers("alice"),
        json=_sample_payload(score=5, messages="Alice original"),
    )

    bob_find = gateway_client.get(
        "/api/v1/feedback/find",
        params={"conv_uid": "poc-fb-conv", "conv_index": 1},
        headers=_gateway_headers("bob"),
    )
    assert bob_find.status_code == 200
    assert bob_find.json()["data"] is None
    assert "M5-FB-ALICE" not in bob_find.text
    assert "Alice original" not in bob_find.text

    bob_overwrite = gateway_client.post(
        "/api/v1/feedback/commit",
        headers=_gateway_headers("bob"),
        json=_sample_payload(score=1, messages="Bob tampered"),
    )
    assert bob_overwrite.status_code == 403

    alice_check = gateway_client.get(
        "/api/v1/feedback/find",
        params={"conv_uid": "poc-fb-conv", "conv_index": 1},
        headers=_gateway_headers("alice"),
    ).json()
    assert alice_check["data"]["score"] == 5
    assert alice_check["data"]["messages"] == "Alice original"


def test_unauthenticated_and_raw_forged_user_id_headers_are_rejected(
    raw_client: TestClient, monkeypatch
):
    # Pre-populate Alice's row and a legacy unowned row directly in metadata DB.
    dao = ChatFeedBackDao()
    dao.create_or_update_chat_feed_back(
        api_fb_v1.FeedBackBody(**_sample_payload()),
        user_name="alice",
    )
    with db.session() as session:
        session.add(
            ChatFeedBackEntity(
                conv_uid="legacy-conv",
                conv_index=0,
                score=4,
                ques_type="QA",
                question="Legacy secret question",
                knowledge_space="legacy",
                messages="Legacy secret transcript",
                user_name=None,
            )
        )

    # Anonymous read (no headers) fails with 401.
    anon_find = raw_client.get(
        "/api/v1/feedback/find",
        params={"conv_uid": "poc-fb-conv", "conv_index": 1},
    )
    assert anon_find.status_code == 401
    assert "POC transcript marker" not in anon_find.text

    # Unverified raw user-id header spoofing Alice fails with 401 in default mode.
    forged_default_find = raw_client.get(
        "/api/v1/feedback/find",
        params={"conv_uid": "poc-fb-conv", "conv_index": 1},
        headers={"user-id": "alice"},
    )
    assert forged_default_find.status_code == 401
    assert "POC transcript marker" not in forged_default_find.text

    forged_default_commit = raw_client.post(
        "/api/v1/feedback/commit",
        headers={"user-id": "alice"},
        json=_sample_payload(score=1, messages="Forged overwrite"),
    )
    assert forged_default_commit.status_code == 401

    # Production mode likewise rejects raw user-id spoofing and anonymous calls.
    monkeypatch.setenv("DBGPT_DASHBOARD_PRODUCTION_MODE", "true")
    forged_prod_find = raw_client.get(
        "/api/v1/feedback/find",
        params={"conv_uid": "poc-fb-conv", "conv_index": 1},
        headers={"user-id": "alice"},
    )
    assert forged_prod_find.status_code == 401

    anon_legacy = raw_client.get(
        "/api/v1/feedback/find",
        params={"conv_uid": "legacy-conv", "conv_index": 0},
    )
    assert anon_legacy.status_code == 401


def test_middleware_verified_principal_rejects_forged_victim_header():
    """Verified middleware owner works while a forged victim user-id header gets 403."""
    current_principal: dict = {"user": None}
    app = FastAPI()

    @app.middleware("http")
    async def inject_authenticated_user(request: Request, call_next):
        if current_principal["user"] is not None:
            request.state.user = current_principal["user"]
        return await call_next(request)

    app.include_router(api_fb_v1.router, prefix="/api")
    test_client = TestClient(app)

    # Verified owner Alice stores and reads back her feedback without raw headers.
    current_principal["user"] = UserRequest(user_id="alice")
    commit_res = test_client.post(
        "/api/v1/feedback/commit",
        json=_sample_payload(user_name="spoofed-body-user"),
    )
    assert commit_res.status_code == 200

    alice_find = test_client.get(
        "/api/v1/feedback/find",
        params={"conv_uid": "poc-fb-conv", "conv_index": 1},
    )
    assert alice_find.status_code == 200
    assert alice_find.json()["data"]["user_name"] == "alice"
    assert alice_find.json()["data"]["messages"] == "POC transcript marker"

    # Verified Bob attempting to pass a forged `user-id: alice` header is rejected.
    current_principal["user"] = UserRequest(user_id="bob")
    forged_find = test_client.get(
        "/api/v1/feedback/find",
        params={"conv_uid": "poc-fb-conv", "conv_index": 1},
        headers={"user-id": "alice"},
    )
    assert forged_find.status_code == 403
    assert "POC transcript marker" not in forged_find.text

    forged_commit = test_client.post(
        "/api/v1/feedback/commit",
        headers={"user-id": "alice"},
        json=_sample_payload(score=1, messages="Bob forged header"),
    )
    assert forged_commit.status_code == 403

    # Verified Alice still reads her intact record (matching header also allowed).
    current_principal["user"] = "alice"
    intact = test_client.get(
        "/api/v1/feedback/find",
        params={"conv_uid": "poc-fb-conv", "conv_index": 1},
        headers={"user-id": "alice"},
    )
    assert intact.status_code == 200
    assert intact.json()["data"]["score"] == 5
    assert intact.json()["data"]["messages"] == "POC transcript marker"


def test_trusted_gateway_enforces_signature_and_blocks_header_tampering(
    gateway_client: TestClient,
):
    gateway_client.post(
        "/api/v1/feedback/commit",
        headers={
            api_fb_v1.AUTH_USER_HEADER: "alice",
            api_fb_v1.TRUSTED_GATEWAY_SIG_HEADER: api_fb_v1.compute_gateway_signature(
                GATEWAY_SECRET, "alice"
            ),
        },
        json=_sample_payload(),
    )

    # Missing signature when supplying user-id directly -> 401.
    no_sig = gateway_client.get(
        "/api/v1/feedback/find",
        params={"conv_uid": "poc-fb-conv", "conv_index": 1},
        headers={"user-id": "alice"},
    )
    assert no_sig.status_code == 401

    # Replaying Bob's valid signature with forged `user-id: alice` -> 401.
    replayed_bob_sig = gateway_client.get(
        "/api/v1/feedback/find",
        params={"conv_uid": "poc-fb-conv", "conv_index": 1},
        headers={
            "user-id": "alice",
            api_fb_v1.TRUSTED_GATEWAY_SIG_HEADER: api_fb_v1.compute_gateway_signature(
                GATEWAY_SECRET, "bob"
            ),
        },
    )
    assert replayed_bob_sig.status_code == 401

    # Conflicting user-id and x-authenticated-user headers -> 403.
    conflicting = gateway_client.get(
        "/api/v1/feedback/find",
        params={"conv_uid": "poc-fb-conv", "conv_index": 1},
        headers={
            "user-id": "bob",
            api_fb_v1.AUTH_USER_HEADER: "alice",
            api_fb_v1.TRUSTED_GATEWAY_SIG_HEADER: api_fb_v1.compute_gateway_signature(
                GATEWAY_SECRET, "alice"
            ),
        },
    )
    assert conflicting.status_code == 403

    # Duplicate user-id headers -> 400.
    dup_res = gateway_client.get(
        "/api/v1/feedback/find",
        params={"conv_uid": "poc-fb-conv", "conv_index": 1},
        headers=[("user-id", "bob"), ("user-id", "alice")],
    )
    assert dup_res.status_code == 400


def test_principal_bound_and_shared_api_keys_prevent_impersonation(monkeypatch):
    app = FastAPI()
    sys_app = SystemApp(app)
    feedback_serve_endpoints.init_endpoints(
        sys_app,
        ServeConfig(api_keys="alice:secret-key-1, bob:secret-key-2, shared-gw-key"),
    )
    app.include_router(api_fb_v1.router, prefix="/api")
    test_client = TestClient(app)

    # Missing or invalid bearer token -> 401.
    assert (
        test_client.get(
            "/api/v1/feedback/find",
            params={"conv_uid": "poc-fb-conv", "conv_index": 1},
        ).status_code
        == 401
    )
    assert (
        test_client.post(
            "/api/v1/feedback/commit",
            headers={"Authorization": "Bearer wrong-key"},
            json=_sample_payload(),
        ).status_code
        == 401
    )

    # Alice's bound key commits and reads Alice's feedback without user-id header.
    ok_commit = test_client.post(
        "/api/v1/feedback/commit",
        headers={"Authorization": "Bearer secret-key-1"},
        json=_sample_payload(),
    )
    assert ok_commit.status_code == 200

    ok_find = test_client.get(
        "/api/v1/feedback/find",
        params={"conv_uid": "poc-fb-conv", "conv_index": 1},
        headers={"Authorization": "Bearer secret-key-1"},
    )
    assert ok_find.status_code == 200
    assert ok_find.json()["data"]["user_name"] == "alice"
    assert ok_find.json()["data"]["messages"] == "POC transcript marker"

    # Bob's bound key cannot read Alice's feedback and gets 403 if forging user-id.
    bob_find = test_client.get(
        "/api/v1/feedback/find",
        params={"conv_uid": "poc-fb-conv", "conv_index": 1},
        headers={"Authorization": "Bearer secret-key-2"},
    )
    assert bob_find.status_code == 200
    assert bob_find.json()["data"] is None

    bob_forged = test_client.get(
        "/api/v1/feedback/find",
        params={"conv_uid": "poc-fb-conv", "conv_index": 1},
        headers={
            "Authorization": "Bearer secret-key-2",
            "user-id": "alice",
        },
    )
    assert bob_forged.status_code == 403

    # An unbound shared bearer key does NOT bind to Alice and rejects raw user-id.
    shared_forged = test_client.get(
        "/api/v1/feedback/find",
        params={"conv_uid": "poc-fb-conv", "conv_index": 1},
        headers={
            "Authorization": "Bearer shared-gw-key",
            "user-id": "alice",
        },
    )
    assert shared_forged.status_code == 401

    shared_no_principal = test_client.get(
        "/api/v1/feedback/find",
        params={"conv_uid": "poc-fb-conv", "conv_index": 1},
        headers={"Authorization": "Bearer shared-gw-key"},
    )
    assert shared_no_principal.status_code == 401

    # Shared bearer key paired with a valid trusted gateway signature succeeds.
    monkeypatch.setenv(api_fb_v1.TRUSTED_GATEWAY_SECRET_ENV, GATEWAY_SECRET)
    shared_with_gw = test_client.get(
        "/api/v1/feedback/find",
        params={"conv_uid": "poc-fb-conv", "conv_index": 1},
        headers=_gateway_headers("alice", Authorization="Bearer shared-gw-key"),
    )
    assert shared_with_gw.status_code == 200
    assert shared_with_gw.json()["data"]["user_name"] == "alice"

    # Malformed owner:token entry fails closed rather than bypassing auth.
    malformed_app = FastAPI()
    malformed_sys = SystemApp(malformed_app)
    feedback_serve_endpoints.init_endpoints(
        malformed_sys, ServeConfig(api_keys=":missing-owner")
    )
    malformed_app.include_router(api_fb_v1.router, prefix="/api")
    malformed_client = TestClient(malformed_app)
    assert (
        malformed_client.get(
            "/api/v1/feedback/select",
            headers={"Authorization": "Bearer missing-owner"},
        ).status_code
        == 401
    )


def test_other_user_cannot_commit_feedback_on_foreign_conversation(
    gateway_client: TestClient,
):
    with db.session() as session:
        session.add(
            ChatHistoryEntity(
                conv_uid="alice-owned-conv",
                chat_mode="chat_normal",
                summary="Alice chat",
                user_name="alice",
            )
        )

    bob_res = gateway_client.post(
        "/api/v1/feedback/commit",
        headers=_gateway_headers("bob"),
        json=_sample_payload(conv_uid="alice-owned-conv", conv_index=0),
    )
    assert bob_res.status_code == 403

    alice_res = gateway_client.post(
        "/api/v1/feedback/commit",
        headers=_gateway_headers("alice"),
        json=_sample_payload(conv_uid="alice-owned-conv", conv_index=0),
    )
    assert alice_res.status_code == 200


def test_scope_principal_custom_provider_and_dev_fallback_edges(monkeypatch):
    scope_Holder: dict = {"user": None}
    app = FastAPI()

    @app.middleware("http")
    async def set_scope_user(request: Request, call_next):
        if scope_Holder["user"] is not None:
            request.scope["user"] = scope_Holder["user"]
        return await call_next(request)

    sys_app = SystemApp(app)
    feedback_serve_endpoints.init_endpoints(sys_app, ServeConfig(api_keys=" , "))
    app.include_router(api_fb_v1.router, prefix="/api")
    client = TestClient(app)

    # /v1/feedback/select remains reachable when api_keys has no active entries.
    select_res = client.get("/api/v1/feedback/select")
    assert select_res.status_code == 200
    assert "information" in select_res.json()["data"]

    # Unauthenticated scope user object is ignored -> 401.
    scope_Holder["user"] = SimpleNamespace(username="alice", is_authenticated=False)
    assert (
        client.get(
            "/api/v1/feedback/find",
            params={"conv_uid": "poc-fb-conv", "conv_index": 1},
        ).status_code
        == 401
    )

    # Authenticated scope user object resolves principal and validates payload.
    scope_Holder["user"] = SimpleNamespace(username="alice", is_authenticated=True)
    missing_conv = client.post(
        "/api/v1/feedback/commit",
        json=_sample_payload(conv_uid="", conv_index=1),
    )
    assert missing_conv.status_code == 422

    assert (
        client.post("/api/v1/feedback/commit", json=_sample_payload()).status_code
        == 200
    )
    scope_Holder["user"] = None

    # Untrusted gateway signature header when gateway secret is unset -> 401.
    assert (
        client.get(
            "/api/v1/feedback/find",
            params={"conv_uid": "poc-fb-conv", "conv_index": 1},
            headers={api_fb_v1.TRUSTED_GATEWAY_SIG_HEADER: "deadbeef"},
        ).status_code
        == 401
    )

    # Custom DashboardIdentityProvider adapter (request-aware and error handling).
    class CustomSSOProvider:
        def __init__(self, actor: str = ""):
            self.actor = actor

        def resolve_request(self, request: Request) -> str:
            token = request.headers.get("x-sso-ticket", "")
            if token == "valid-alice-ticket":
                return "alice"
            raise DashboardIdentityError("Invalid SSO ticket")

    configure_dashboard_identity_provider(CustomSSOProvider())
    assert (
        client.get(
            "/api/v1/feedback/find",
            params={"conv_uid": "poc-fb-conv", "conv_index": 1},
            headers={"x-sso-ticket": "bad"},
        ).status_code
        == 401
    )
    sso_ok = client.get(
        "/api/v1/feedback/find",
        params={"conv_uid": "poc-fb-conv", "conv_index": 1},
        headers={"x-sso-ticket": "valid-alice-ticket"},
    )
    assert sso_ok.status_code == 200
    assert sso_ok.json()["data"]["user_name"] == "alice"

    # Conflicting principals (e.g. scope user=bob vs custom SSO=alice) -> 403.
    scope_Holder["user"] = SimpleNamespace(username="bob", is_authenticated=True)
    conflict_res = client.get(
        "/api/v1/feedback/find",
        params={"conv_uid": "poc-fb-conv", "conv_index": 1},
        headers={"x-sso-ticket": "valid-alice-ticket"},
    )
    assert conflict_res.status_code == 403
    scope_Holder["user"] = None
    configure_dashboard_identity_provider(None)

    # Explicit opt-in dev fallback works only without forged headers or prod mode.
    monkeypatch.setenv(api_fb_v1.DEV_FALLBACK_ENV, "true")
    assert (
        client.post(
            "/api/v1/feedback/commit",
            json=_sample_payload(conv_uid="dev-conv", conv_index=1),
        ).status_code
        == 200
    )
    assert (
        client.get(
            "/api/v1/feedback/find",
            params={"conv_uid": "dev-conv", "conv_index": 1},
        ).json()["data"]["user_name"]
        == "001"
    )
    assert (
        client.get(
            "/api/v1/feedback/find",
            params={"conv_uid": "poc-fb-conv", "conv_index": 1},
            headers={"user-id": "alice"},
        ).status_code
        == 401
    )
    monkeypatch.setenv("DBGPT_DASHBOARD_PRODUCTION_MODE", "true")
    assert (
        client.get(
            "/api/v1/feedback/find",
            params={"conv_uid": "dev-conv", "conv_index": 1},
        ).status_code
        == 401
    )


def test_dao_guards_fail_closed():
    dao = ChatFeedBackDao()
    dao.create_or_update_chat_feed_back(
        api_fb_v1.FeedBackBody(**_sample_payload()),
        user_name="alice",
    )
    assert dao.get_chat_feed_back("poc-fb-conv", 1) is None
    assert dao.get_chat_feed_back("poc-fb-conv", 1, user_name="") is None
    assert dao.get_chat_feed_back("poc-fb-conv", 1, user_name="   ") is None
    owned = dao.get_chat_feed_back("poc-fb-conv", 1, user_name="alice")
    assert owned is not None
    assert owned.messages == "POC transcript marker"

    with pytest.raises(PermissionError):
        dao.create_or_update_chat_feed_back(
            api_fb_v1.FeedBackBody(**_sample_payload()), user_name="  "
        )
    with pytest.raises(ValueError):
        dao.create_or_update_chat_feed_back(
            api_fb_v1.FeedBackBody(**_sample_payload(conv_uid="")), user_name="alice"
        )
