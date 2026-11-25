import hashlib
import hmac
from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from dbgpt.component import SystemApp
from dbgpt.storage.chat_history.chat_history_db import ChatHistoryEntity
from dbgpt.storage.metadata import DatabaseManager, Model, db
from dbgpt_app.openapi.api_v1.dashboard import identity as dashboard_identity
from dbgpt_app.openapi.api_v1.dashboard.identity import (
    DashboardIdentityError,
    configure_dashboard_identity_provider,
)
from dbgpt_app.openapi.api_v1.feedback import api_fb_v1
from dbgpt_app.openapi.api_v1.feedback.feed_back_db import (
    ChatFeedBackDao,
    ChatFeedBackEntity,
)
from dbgpt_serve.conversation.api import endpoints as conv_serve_endpoints
from dbgpt_serve.feedback.api import endpoints as feedback_serve_endpoints
from dbgpt_serve.feedback.config import ServeConfig
from dbgpt_serve.utils.auth import UserRequest

GATEWAY_SECRET = "unit-test-trusted-gateway-secret"


@contextmanager
def _preserve_identity_provider():
    prev_provider = dashboard_identity._identity_provider
    configure_dashboard_identity_provider(None)
    try:
        yield
    finally:
        configure_dashboard_identity_provider(prev_provider)


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """Provide an isolated SQLite metadata database and restore global state."""
    from dbgpt._private.config import Config

    db_file = (tmp_path / "feedback_meta.db").as_posix()
    db.init_db(
        f"sqlite:///{db_file}",
        engine_args={"connect_args": {"check_same_thread": False}},
    )
    db.create_all()
    cfg = Config()
    prev_fb_app = feedback_serve_endpoints.global_system_app
    prev_conv_app = conv_serve_endpoints.global_system_app
    prev_cfg_app = cfg.SYSTEM_APP
    feedback_serve_endpoints.global_system_app = None
    conv_serve_endpoints.global_system_app = None
    cfg.SYSTEM_APP = None
    monkeypatch.setenv(
        api_fb_v1.SESSION_KEY_FILE_ENV, str(tmp_path / "feedback-session.key")
    )
    for env_key in (
        "DBGPT_DASHBOARD_PRODUCTION_MODE",
        "DBGPT_DASHBOARD_IDENTITY_PROVIDER",
        api_fb_v1.TRUSTED_GATEWAY_SECRET_ENV,
        api_fb_v1.DEV_FALLBACK_ENV,
        api_fb_v1.SESSION_SECRET_ENV,
    ):
        monkeypatch.delenv(env_key, raising=False)
    with _preserve_identity_provider():
        try:
            yield
        finally:
            if db.engine is not None:
                db.engine.dispose()
            feedback_serve_endpoints.global_system_app = prev_fb_app
            conv_serve_endpoints.global_system_app = prev_conv_app
            cfg.SYSTEM_APP = prev_cfg_app


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
    # Independently compute expected HMAC digest without calling production signer.
    independent_sig = hmac.new(
        GATEWAY_SECRET.encode("utf-8"), b"alice", hashlib.sha256
    ).hexdigest()
    res = gateway_client.post(
        "/api/v1/feedback/commit",
        headers={
            "user-id": "alice",
            api_fb_v1.TRUSTED_GATEWAY_SIG_HEADER: independent_sig,
        },
        json=_sample_payload(),
    )
    assert res.status_code == 200
    assert res.json()["success"] is True

    found = gateway_client.get(
        "/api/v1/feedback/find",
        params={"conv_uid": "poc-fb-conv", "conv_index": 1},
        headers={
            "user-id": "alice",
            api_fb_v1.TRUSTED_GATEWAY_SIG_HEADER: independent_sig,
        },
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

    # Stateless anonymous read (no session cookie, no auth) fails with 401.
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

    # Production mode likewise rejects raw user-id spoofing and stateless calls.
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


def test_browser_session_cookie_works_in_production_and_survives_restart(
    monkeypatch,
):
    """Browser select -> commit -> find flow works in production and across restarts."""
    monkeypatch.setenv("DBGPT_DASHBOARD_PRODUCTION_MODE", "true")
    # Intentionally leave SESSION_SECRET_ENV unset so the persistent key file is used
    # across independent app instances / restarts.
    with db.session() as session:
        session.add_all(
            [
                ChatHistoryEntity(
                    conv_uid="browser-conv-a",
                    chat_mode="chat_normal",
                    summary="Unowned browser dialogue",
                    user_name=None,
                ),
                ChatHistoryEntity(
                    conv_uid="default-001-conv",
                    chat_mode="chat_normal",
                    summary="Conversation owned by 001",
                    user_name="001",
                ),
                ChatHistoryEntity(
                    conv_uid="alice-named-conv",
                    chat_mode="chat_normal",
                    summary="Named user conversation",
                    user_name="alice",
                ),
            ]
        )

    app = FastAPI()
    app.include_router(api_fb_v1.router, prefix="/api")

    browser_a = TestClient(app)
    browser_b = TestClient(app)
    https_proxy_client = TestClient(app)

    # Behind HTTPS / X-Forwarded-Proto: https, Set-Cookie carries Secure + HttpOnly
    # and the response sets Cache-Control: no-store to prevent shared cache replay.
    https_sel = https_proxy_client.get(
        "/api/v1/feedback/select", headers={"x-forwarded-proto": "https"}
    )
    assert https_sel.status_code == 200
    assert https_sel.headers.get("cache-control") == "no-store"
    https_cookie_hdr = https_sel.headers.get("set-cookie", "").lower()
    assert "httponly" in https_cookie_hdr
    assert "secure" in https_cookie_hdr

    direct_tls_client = TestClient(app, base_url="https://testserver")
    tls_sel = direct_tls_client.get("/api/v1/feedback/select")
    assert tls_sel.headers.get("cache-control") == "no-store"
    assert "secure" in tls_sel.headers.get("set-cookie", "").lower()

    # Browser A loads feedback categories and gets a persistent-key-signed cookie.
    sel_a = browser_a.get("/api/v1/feedback/select")
    assert sel_a.status_code == 200
    assert sel_a.headers.get("cache-control") == "no-store"
    assert "httponly" in sel_a.headers.get("set-cookie", "").lower()
    cookie_a = browser_a.cookies.get(api_fb_v1.SESSION_COOKIE_NAME)
    assert cookie_a is not None and cookie_a.startswith("session:")

    # Subsequent select preserves the same session actor.
    browser_a.get("/api/v1/feedback/select")
    assert browser_a.cookies.get(api_fb_v1.SESSION_COOKIE_NAME) == cookie_a

    # Browser A commits and reads back its own feedback on a built-in ("001") chat
    # as well as an unowned (None) chat, and keeps access across restarts.
    commit_001 = browser_a.post(
        "/api/v1/feedback/commit",
        json=_sample_payload(conv_uid="default-001-conv", conv_index=1),
    )
    assert commit_001.status_code == 200

    commit_a = browser_a.post(
        "/api/v1/feedback/commit",
        json=_sample_payload(conv_uid="browser-conv-a", conv_index=1),
    )
    assert commit_a.status_code == 200

    find_001 = browser_a.get(
        "/api/v1/feedback/find",
        params={"conv_uid": "default-001-conv", "conv_index": 1},
    )
    assert find_001.status_code == 200
    assert find_001.headers.get("cache-control") == "no-store"
    assert find_001.json()["data"]["messages"] == "POC transcript marker"
    assert find_001.json()["data"]["user_name"].startswith("session:")

    find_a = browser_a.get(
        "/api/v1/feedback/find",
        params={"conv_uid": "browser-conv-a", "conv_index": 1},
    )
    assert find_a.status_code == 200
    assert find_a.headers.get("cache-control") == "no-store"
    assert find_a.json()["data"]["messages"] == "POC transcript marker"
    assert find_a.json()["data"]["user_name"].startswith("session:")

    # Simulate an application restart / independent worker reading the shared key file:
    # the existing browser cookie continues to verify and read/update its feedback.
    restarted_app = FastAPI()
    restarted_app.include_router(api_fb_v1.router, prefix="/api")
    restarted_browser_a = TestClient(restarted_app)
    restarted_browser_a.cookies.set(api_fb_v1.SESSION_COOKIE_NAME, cookie_a)
    after_restart_find = restarted_browser_a.get(
        "/api/v1/feedback/find",
        params={"conv_uid": "default-001-conv", "conv_index": 1},
    )
    assert after_restart_find.status_code == 200
    assert after_restart_find.json()["data"]["messages"] == "POC transcript marker"

    # Session actors still cannot attach feedback to a named ("alice") conversation.
    assert (
        browser_a.post(
            "/api/v1/feedback/commit",
            json=_sample_payload(conv_uid="alice-named-conv", conv_index=1),
        ).status_code
        == 403
    )

    # Cross-site fetch metadata and non-JSON form posts are rejected for cookie auth.
    csrf_cross_site = browser_a.post(
        "/api/v1/feedback/commit",
        headers={"sec-fetch-site": "cross-site"},
        json=_sample_payload(conv_uid="browser-conv-a", conv_index=1, score=1),
    )
    assert csrf_cross_site.status_code == 403

    csrf_form = browser_a.post(
        "/api/v1/feedback/commit",
        headers={"content-type": "text/plain"},
        content=b'{"conv_uid":"browser-conv-a","conv_index":1,"score":1}',
    )
    assert csrf_form.status_code == 415

    # Browser A still cannot forge a raw `user-id: alice` header -> 403.
    forged_from_browser = browser_a.get(
        "/api/v1/feedback/find",
        params={"conv_uid": "browser-conv-a", "conv_index": 1},
        headers={"user-id": "alice"},
    )
    assert forged_from_browser.status_code == 403

    # Browser B gets its own distinct session cookie: cannot read, overwrite, or
    # claim subsequent turns on Browser A's default-001-conv / browser-conv-a.
    browser_b.get("/api/v1/feedback/select")
    assert (
        browser_b.get(
            "/api/v1/feedback/find",
            params={"conv_uid": "default-001-conv", "conv_index": 1},
        ).json()["data"]
        is None
    )
    assert (
        browser_b.post(
            "/api/v1/feedback/commit",
            json=_sample_payload(conv_uid="default-001-conv", conv_index=1),
        ).status_code
        == 403
    )
    assert (
        browser_b.post(
            "/api/v1/feedback/commit",
            json=_sample_payload(conv_uid="default-001-conv", conv_index=2),
        ).status_code
        == 403
    )

    # Meanwhile the direct conversation owner ("001" via verified principal) is not
    # locked out by a session actor's prior row on its own conversation.
    ChatFeedBackDao().create_or_update_chat_feed_back(
        api_fb_v1.FeedBackBody(
            **_sample_payload(
                conv_uid="default-001-conv", conv_index=1, messages="Reclaimed by 001"
            )
        ),
        user_name="001",
    )
    reclaimed = ChatFeedBackDao().get_chat_feed_back(
        "default-001-conv", 1, user_name="001"
    )
    assert reclaimed is not None and reclaimed.messages == "Reclaimed by 001"

    find_b = browser_b.get(
        "/api/v1/feedback/find",
        params={"conv_uid": "browser-conv-a", "conv_index": 1},
    )
    assert find_b.status_code == 200
    assert find_b.json()["data"] is None

    overwrite_b = browser_b.post(
        "/api/v1/feedback/commit",
        json=_sample_payload(
            conv_uid="browser-conv-a", conv_index=1, messages="Tampered by B"
        ),
    )
    assert overwrite_b.status_code == 403

    # Tampered or malformed session cookies fail closed with 401.
    for bad_cookie in (
        "session:00112233445566778899aabbccddeeff.bad_sig",
        "no-dot-cookie",
        "session:not_hex_00112233445566778899.00",
    ):
        tampered_client = TestClient(app)
        tampered_client.cookies.set(api_fb_v1.SESSION_COOKIE_NAME, bad_cookie)
        assert (
            tampered_client.get(
                "/api/v1/feedback/find",
                params={"conv_uid": "browser-conv-a", "conv_index": 1},
            ).status_code
            == 401
        )


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

    # Request signed with a different gateway secret -> 401.
    wrong_secret = gateway_client.get(
        "/api/v1/feedback/find",
        params={"conv_uid": "poc-fb-conv", "conv_index": 1},
        headers=_gateway_headers("alice", secret="different-untrusted-secret"),
    )
    assert wrong_secret.status_code == 401

    # Non-ASCII Latin-1 header bytes return 401 rather than 500 TypeError.
    non_ascii_sig = gateway_client.get(
        "/api/v1/feedback/find",
        params={"conv_uid": "poc-fb-conv", "conv_index": 1},
        headers={
            "user-id": "alice",
            api_fb_v1.TRUSTED_GATEWAY_SIG_HEADER: "é-non-ascii-sig".encode("latin-1"),
        },
    )
    assert non_ascii_sig.status_code == 401

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


def test_principal_bound_shared_and_conflicting_api_keys(monkeypatch):
    app = FastAPI()
    sys_app = SystemApp(app)
    feedback_serve_endpoints.init_endpoints(
        sys_app,
        ServeConfig(
            api_keys=(
                "alice:secret-key-1, bob:secret-key-2, shared-gw-key, "
                "ambig-shared, alice:ambig-shared, bob:ambig-two, carol:ambig-two"
            )
        ),
    )
    app.include_router(api_fb_v1.router, prefix="/api")
    test_client = TestClient(app)

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

    # Ambiguous keys (shared+bound or two distinct owners) are rejected with 401.
    assert (
        test_client.get(
            "/api/v1/feedback/select",
            headers={"Authorization": "Bearer ambig-shared"},
        ).status_code
        == 401
    )
    assert (
        test_client.get(
            "/api/v1/feedback/select",
            headers={"Authorization": "Bearer ambig-two"},
        ).status_code
        == 401
    )

    # Unambiguous Alice key remains valid.
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


def test_scope_principal_custom_provider_and_fixture_restore(tmp_path, monkeypatch):
    scope_holder: dict = {"user": None}
    app = FastAPI()

    @app.middleware("http")
    async def set_scope_user(request: Request, call_next):
        if scope_holder["user"] is not None:
            request.scope["user"] = scope_holder["user"]
        return await call_next(request)

    sys_app = SystemApp(app)
    feedback_serve_endpoints.init_endpoints(sys_app, ServeConfig(api_keys=" , "))
    app.include_router(api_fb_v1.router, prefix="/api")
    client = TestClient(app)

    scope_holder["user"] = SimpleNamespace(username="alice", is_authenticated=False)
    assert (
        client.get(
            "/api/v1/feedback/find",
            params={"conv_uid": "poc-fb-conv", "conv_index": 1},
        ).status_code
        == 401
    )

    scope_holder["user"] = SimpleNamespace(username="alice", is_authenticated=True)
    assert (
        client.post(
            "/api/v1/feedback/commit",
            json=_sample_payload(conv_uid="", conv_index=1),
        ).status_code
        == 422
    )
    assert (
        client.post("/api/v1/feedback/commit", json=_sample_payload()).status_code
        == 200
    )
    scope_holder["user"] = None

    # Untrusted gateway signature header when gateway secret is unset -> 401.
    assert (
        client.get(
            "/api/v1/feedback/find",
            params={"conv_uid": "poc-fb-conv", "conv_index": 1},
            headers={api_fb_v1.TRUSTED_GATEWAY_SIG_HEADER: "deadbeef"},
        ).status_code
        == 401
    )

    # Custom DashboardIdentityProvider returning None is rejected as 401 (never "None").
    class CustomSSOProvider:
        def resolve_request(self, request: Request):
            token = request.headers.get("x-sso-ticket", "")
            if token == "none-ticket":
                return None
            if token == "valid-alice-ticket":
                return "alice"
            raise DashboardIdentityError("Invalid SSO ticket")

    configure_dashboard_identity_provider(CustomSSOProvider())
    assert (
        client.get(
            "/api/v1/feedback/find",
            params={"conv_uid": "poc-fb-conv", "conv_index": 1},
            headers={"x-sso-ticket": "none-ticket"},
        ).status_code
        == 401
    )
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

    scope_holder["user"] = SimpleNamespace(username="bob", is_authenticated=True)
    assert (
        client.get(
            "/api/v1/feedback/find",
            params={"conv_uid": "poc-fb-conv", "conv_index": 1},
            headers={"x-sso-ticket": "valid-alice-ticket"},
        ).status_code
        == 403
    )
    scope_holder["user"] = None
    configure_dashboard_identity_provider(None)

    monkeypatch.setenv(api_fb_v1.DEV_FALLBACK_ENV, "true")
    stateless_client = TestClient(app)
    assert (
        stateless_client.post(
            "/api/v1/feedback/commit",
            json=_sample_payload(conv_uid="dev-conv", conv_index=1),
        ).status_code
        == 200
    )
    assert (
        stateless_client.get(
            "/api/v1/feedback/find",
            params={"conv_uid": "dev-conv", "conv_index": 1},
        ).json()["data"]["user_name"]
        == "001"
    )
    monkeypatch.setenv("DBGPT_DASHBOARD_PRODUCTION_MODE", "true")
    assert (
        stateless_client.get(
            "/api/v1/feedback/find",
            params={"conv_uid": "dev-conv", "conv_index": 1},
        ).status_code
        == 401
    )

    # Verify _preserve_identity_provider saves and restores inherited provider cleanly
    # without reopening or disposing the metadata database.
    sentinel_provider = SimpleNamespace(resolve=lambda _u: "sentinel")
    configure_dashboard_identity_provider(sentinel_provider)
    with _preserve_identity_provider():
        assert dashboard_identity._identity_provider is None
    assert dashboard_identity._identity_provider is sentinel_provider
    configure_dashboard_identity_provider(None)


def test_case_sensitive_owner_matching_and_separate_conversation_db(
    tmp_path, gateway_client: TestClient, monkeypatch
):
    """Exact case-sensitive owner lookup and separate conversation DB binding."""
    # `Alice` commits feedback; `alice` (different case) cannot read or modify it.
    assert (
        gateway_client.post(
            "/api/v1/feedback/commit",
            headers=_gateway_headers("Alice"),
            json=_sample_payload(
                conv_uid="case-conv", conv_index=1, messages="Alice uppercase secret"
            ),
        ).status_code
        == 200
    )
    lower_find = gateway_client.get(
        "/api/v1/feedback/find",
        params={"conv_uid": "case-conv", "conv_index": 1},
        headers=_gateway_headers("alice"),
    )
    assert lower_find.status_code == 200
    assert lower_find.json()["data"] is None
    assert "Alice uppercase secret" not in lower_find.text

    lower_overwrite = gateway_client.post(
        "/api/v1/feedback/commit",
        headers=_gateway_headers("alice"),
        json=_sample_payload(conv_uid="case-conv", conv_index=1, score=1),
    )
    assert lower_overwrite.status_code == 403

    upper_find = gateway_client.get(
        "/api/v1/feedback/find",
        params={"conv_uid": "case-conv", "conv_index": 1},
        headers=_gateway_headers("Alice"),
    )
    assert upper_find.status_code == 200
    assert upper_find.json()["data"]["messages"] == "Alice uppercase secret"

    # Separate DatabaseManager holding `chat_history` (absent from global `db`):
    # feedback writes targeting another user's conversation in that manager are blocked.
    conv_db_file = (tmp_path / "separate_conv.db").as_posix()
    separate_conv_mgr = DatabaseManager()
    separate_conv_mgr.init_db(
        f"sqlite:///{conv_db_file}",
        engine_args={"connect_args": {"check_same_thread": False}},
        base=Model,
    )
    separate_conv_mgr.create_all()
    try:
        with separate_conv_mgr.session() as conv_session:
            conv_session.add(
                ChatHistoryEntity(
                    conv_uid="separate-db-alice-conv",
                    chat_mode="chat_normal",
                    summary="Stored in separate conversation DB",
                    user_name="alice",
                )
            )

        bound_dao = ChatFeedBackDao(conv_db_manager=separate_conv_mgr)
        with pytest.raises(PermissionError):
            bound_dao.create_or_update_chat_feed_back(
                api_fb_v1.FeedBackBody(
                    **_sample_payload(conv_uid="separate-db-alice-conv", conv_index=0)
                ),
                user_name="bob",
            )

        bound_dao.create_or_update_chat_feed_back(
            api_fb_v1.FeedBackBody(
                **_sample_payload(conv_uid="separate-db-alice-conv", conv_index=0)
            ),
            user_name="alice",
        )
        assert (
            bound_dao.get_chat_feed_back("separate-db-alice-conv", 0, user_name="alice")
            is not None
        )

        # Also verify ConversationServe._db_manager resolution via SystemApp on router.
        from dbgpt_serve.conversation.serve import Serve as ConversationServe

        app = FastAPI()
        sys_app = SystemApp(app)
        conv_serve = ConversationServe(
            sys_app, db_url_or_db=separate_conv_mgr, try_create_tables=False
        )
        sys_app.register_instance(conv_serve)
        conv_serve.before_start()
        conv_serve_endpoints.global_system_app = sys_app

        assert (
            gateway_client.post(
                "/api/v1/feedback/commit",
                headers=_gateway_headers("bob"),
                json=_sample_payload(conv_uid="separate-db-alice-conv", conv_index=2),
            ).status_code
            == 403
        )
        conv_serve_endpoints.global_system_app = None

        # Verify UnifiedDBManagerFactory resolution when registered on SystemApp.
        from dbgpt.storage.metadata.db_factory import UnifiedDBManagerFactory

        unified_app = SystemApp(FastAPI())
        unified_app.register_instance(
            UnifiedDBManagerFactory(unified_app, separate_conv_mgr)
        )
        feedback_serve_endpoints.global_system_app = unified_app
        assert (
            gateway_client.post(
                "/api/v1/feedback/commit",
                headers=_gateway_headers("bob"),
                json=_sample_payload(conv_uid="separate-db-alice-conv", conv_index=3),
            ).status_code
            == 403
        )
        feedback_serve_endpoints.global_system_app = None

        explicit_dao = ChatFeedBackDao(db_manager=separate_conv_mgr)
        with pytest.raises(PermissionError):
            explicit_dao.create_or_update_chat_feed_back(
                api_fb_v1.FeedBackBody(
                    **_sample_payload(conv_uid="separate-db-alice-conv", conv_index=4)
                ),
                user_name="bob",
            )
    finally:
        if separate_conv_mgr.engine is not None:
            separate_conv_mgr.engine.dispose()

    # Missing `chat_history` table in the bound conversation DB fails closed.
    empty_db_file = (tmp_path / "missing_table.db").as_posix()
    empty_mgr = DatabaseManager()
    empty_mgr.init_db(f"sqlite:///{empty_db_file}")
    try:
        missing_table_dao = ChatFeedBackDao(conv_db_manager=empty_mgr)
        with pytest.raises(PermissionError):
            missing_table_dao.create_or_update_chat_feed_back(
                api_fb_v1.FeedBackBody(**_sample_payload()),
                user_name="alice",
            )
    finally:
        if empty_mgr.engine is not None:
            empty_mgr.engine.dispose()


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
