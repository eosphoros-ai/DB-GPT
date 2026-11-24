import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from dbgpt.component import SystemApp
from dbgpt.storage.chat_history.chat_history_db import ChatHistoryEntity
from dbgpt.storage.metadata import db
from dbgpt_app.openapi.api_v1.feedback import api_fb_v1
from dbgpt_app.openapi.api_v1.feedback.feed_back_db import (
    ChatFeedBackDao,
    ChatFeedBackEntity,
)
from dbgpt_serve.feedback.api import endpoints as feedback_serve_endpoints
from dbgpt_serve.feedback.config import ServeConfig


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """Provide an isolated SQLite metadata database per test."""
    db_file = (tmp_path / "feedback_meta.db").as_posix()
    db.init_db(
        f"sqlite:///{db_file}",
        engine_args={"connect_args": {"check_same_thread": False}},
    )
    db.create_all()
    prev_app = feedback_serve_endpoints.global_system_app
    feedback_serve_endpoints.global_system_app = None
    monkeypatch.delenv("DBGPT_DASHBOARD_PRODUCTION_MODE", raising=False)
    yield
    if db.engine is not None:
        db.engine.dispose()
    feedback_serve_endpoints.global_system_app = prev_app


@pytest.fixture
def client() -> TestClient:
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


def test_owner_can_commit_update_and_read_back_own_feedback(client: TestClient):
    res = client.post(
        "/api/v1/feedback/commit",
        headers={"user-id": "alice"},
        json=_sample_payload(),
    )
    assert res.status_code == 200
    assert res.json()["success"] is True

    found = client.get(
        "/api/v1/feedback/find",
        params={"conv_uid": "poc-fb-conv", "conv_index": 1},
        headers={"user-id": "alice"},
    )
    assert found.status_code == 200
    body = found.json()
    assert body["success"] is True
    assert body["data"]["question"] == "POC question marker M5-FB-ALICE"
    assert body["data"]["messages"] == "POC transcript marker"
    assert body["data"]["score"] == 5
    assert body["data"]["user_name"] == "alice"

    # Updating own feedback succeeds and updates score/messages.
    updated = client.post(
        "/api/v1/feedback/commit",
        headers={"user-id": "alice"},
        json=_sample_payload(score=2, messages="Updated alice note"),
    )
    assert updated.status_code == 200
    found_after = client.get(
        "/api/v1/feedback/find",
        params={"conv_uid": "poc-fb-conv", "conv_index": 1},
        headers={"user-id": "alice"},
    ).json()
    assert found_after["data"]["score"] == 2
    assert found_after["data"]["messages"] == "Updated alice note"


def test_other_user_cannot_read_feedback_via_find(client: TestClient):
    client.post(
        "/api/v1/feedback/commit",
        headers={"user-id": "alice"},
        json=_sample_payload(),
    )

    bob_res = client.get(
        "/api/v1/feedback/find",
        params={"conv_uid": "poc-fb-conv", "conv_index": 1},
        headers={"user-id": "bob"},
    )
    assert bob_res.status_code == 200
    assert bob_res.json()["data"] is None
    assert "M5-FB-ALICE" not in bob_res.text
    assert "POC transcript marker" not in bob_res.text


def test_anonymous_caller_cannot_read_other_users_or_unowned_feedback(
    client: TestClient,
):
    client.post(
        "/api/v1/feedback/commit",
        headers={"user-id": "alice"},
        json=_sample_payload(),
    )

    # Insert a legacy row with user_name=None to verify upgrade safety.
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

    anon_alice = client.get(
        "/api/v1/feedback/find",
        params={"conv_uid": "poc-fb-conv", "conv_index": 1},
    )
    assert anon_alice.status_code == 200
    assert anon_alice.json()["data"] is None
    assert "POC transcript marker" not in anon_alice.text

    anon_legacy = client.get(
        "/api/v1/feedback/find",
        params={"conv_uid": "legacy-conv", "conv_index": 0},
    )
    assert anon_legacy.status_code == 200
    assert anon_legacy.json()["data"] is None
    assert "Legacy secret transcript" not in anon_legacy.text


def test_commit_ignores_spoofed_body_user_name(client: TestClient):
    res = client.post(
        "/api/v1/feedback/commit",
        headers={"user-id": "mallory"},
        json=_sample_payload(user_name="alice"),
    )
    assert res.status_code == 200

    # Alice should not see Mallory's spoofed record; Mallory owns it.
    alice_res = client.get(
        "/api/v1/feedback/find",
        params={"conv_uid": "poc-fb-conv", "conv_index": 1},
        headers={"user-id": "alice"},
    )
    assert alice_res.json()["data"] is None

    mallory_res = client.get(
        "/api/v1/feedback/find",
        params={"conv_uid": "poc-fb-conv", "conv_index": 1},
        headers={"user-id": "mallory"},
    )
    assert mallory_res.json()["data"]["user_name"] == "mallory"


def test_other_user_or_anonymous_cannot_overwrite_existing_feedback(
    client: TestClient,
):
    client.post(
        "/api/v1/feedback/commit",
        headers={"user-id": "alice"},
        json=_sample_payload(score=5, messages="Alice original"),
    )

    bob_attempt = client.post(
        "/api/v1/feedback/commit",
        headers={"user-id": "bob"},
        json=_sample_payload(score=1, messages="Bob tampered"),
    )
    assert bob_attempt.status_code == 403

    anon_attempt = client.post(
        "/api/v1/feedback/commit",
        json=_sample_payload(score=1, messages="Anon tampered"),
    )
    assert anon_attempt.status_code == 403

    alice_check = client.get(
        "/api/v1/feedback/find",
        params={"conv_uid": "poc-fb-conv", "conv_index": 1},
        headers={"user-id": "alice"},
    ).json()
    assert alice_check["data"]["score"] == 5
    assert alice_check["data"]["messages"] == "Alice original"
    assert alice_check["data"]["user_name"] == "alice"


def test_other_user_cannot_commit_feedback_on_foreign_conversation(client: TestClient):
    with db.session() as session:
        session.add(
            ChatHistoryEntity(
                conv_uid="alice-owned-conv",
                chat_mode="chat_normal",
                summary="Alice chat",
                user_name="alice",
            )
        )

    bob_res = client.post(
        "/api/v1/feedback/commit",
        headers={"user-id": "bob"},
        json=_sample_payload(conv_uid="alice-owned-conv", conv_index=0),
    )
    assert bob_res.status_code == 403

    alice_res = client.post(
        "/api/v1/feedback/commit",
        headers={"user-id": "alice"},
        json=_sample_payload(conv_uid="alice-owned-conv", conv_index=0),
    )
    assert alice_res.status_code == 200


def test_production_mode_rejects_anonymous_fallback_with_401(
    client: TestClient, monkeypatch
):
    monkeypatch.setenv("DBGPT_DASHBOARD_PRODUCTION_MODE", "true")

    find_res = client.get(
        "/api/v1/feedback/find",
        params={"conv_uid": "poc-fb-conv", "conv_index": 1},
    )
    assert find_res.status_code == 401

    commit_res = client.post(
        "/api/v1/feedback/commit",
        json=_sample_payload(),
    )
    assert commit_res.status_code == 401

    # Explicit user-id header still succeeds.
    auth_commit = client.post(
        "/api/v1/feedback/commit",
        headers={"user-id": "alice"},
        json=_sample_payload(),
    )
    assert auth_commit.status_code == 200


def test_configured_api_keys_require_valid_bearer_token():
    app = FastAPI()
    sys_app = SystemApp(app)
    feedback_serve_endpoints.init_endpoints(
        sys_app, ServeConfig(api_keys="secret-key-1, secret-key-2")
    )
    app.include_router(api_fb_v1.router, prefix="/api")
    test_client = TestClient(app)

    unauth_find = test_client.get(
        "/api/v1/feedback/find",
        params={"conv_uid": "poc-fb-conv", "conv_index": 1},
        headers={"user-id": "alice"},
    )
    assert unauth_find.status_code == 401

    wrong_key = test_client.post(
        "/api/v1/feedback/commit",
        headers={
            "user-id": "alice",
            "Authorization": "Bearer wrong-key",
        },
        json=_sample_payload(),
    )
    assert wrong_key.status_code == 401

    ok_commit = test_client.post(
        "/api/v1/feedback/commit",
        headers={
            "user-id": "alice",
            "Authorization": "Bearer secret-key-1",
        },
        json=_sample_payload(),
    )
    assert ok_commit.status_code == 200

    ok_find = test_client.get(
        "/api/v1/feedback/find",
        params={"conv_uid": "poc-fb-conv", "conv_index": 1},
        headers={
            "user-id": "alice",
            "Authorization": "Bearer secret-key-2",
        },
    )
    assert ok_find.status_code == 200
    assert ok_find.json()["data"]["messages"] == "POC transcript marker"


def test_dao_get_without_user_name_fails_closed(client: TestClient):
    client.post(
        "/api/v1/feedback/commit",
        headers={"user-id": "alice"},
        json=_sample_payload(),
    )
    dao = ChatFeedBackDao()
    assert dao.get_chat_feed_back("poc-fb-conv", 1) is None
    assert dao.get_chat_feed_back("poc-fb-conv", 1, user_name="") is None
    assert dao.get_chat_feed_back("poc-fb-conv", 1, user_name="   ") is None
    owned = dao.get_chat_feed_back("poc-fb-conv", 1, user_name="alice")
    assert owned is not None
    assert owned.messages == "POC transcript marker"

    blank_header = client.get(
        "/api/v1/feedback/find",
        params={"conv_uid": "poc-fb-conv", "conv_index": 1},
        headers={"user-id": "   "},
    )
    assert blank_header.status_code == 401


def test_select_validation_and_dao_guard_edges(client: TestClient):
    # /v1/feedback/select remains reachable when api_keys is empty.
    app = FastAPI()
    sys_app = SystemApp(app)
    feedback_serve_endpoints.init_endpoints(sys_app, ServeConfig(api_keys=""))
    app.include_router(api_fb_v1.router, prefix="/api")
    open_client = TestClient(app)

    select_res = open_client.get("/api/v1/feedback/select")
    assert select_res.status_code == 200
    assert "information" in select_res.json()["data"]

    missing_conv = open_client.post(
        "/api/v1/feedback/commit",
        headers={"user-id": "alice"},
        json=_sample_payload(conv_uid="", conv_index=1),
    )
    assert missing_conv.status_code == 422

    dao = ChatFeedBackDao()
    with pytest.raises(PermissionError):
        dao.create_or_update_chat_feed_back(
            api_fb_v1.FeedBackBody(**_sample_payload()), user_name="  "
        )
    with pytest.raises(ValueError):
        dao.create_or_update_chat_feed_back(
            api_fb_v1.FeedBackBody(**_sample_payload(conv_uid="")), user_name="alice"
        )
