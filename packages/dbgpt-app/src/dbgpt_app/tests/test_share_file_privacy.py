"""Share-link privacy for conversations containing react history payloads.

Covers:
- share creation verifies conversation ownership: a foreign authenticated
  user (or an anonymous caller) cannot create a share for someone else's
  conversation, and unknown conversations fail closed with 404;
- share deletion verifies share ownership: only the recorded creator may
  revoke a link (legacy anonymous links stay revocable as before);
- the public share endpoint parses stored react history JSON server-side:
  v1 payloads stay byte-for-byte untouched while v2 ``input_files`` are
  rewritten to allowlisted public snapshots whose ``display_key`` is a
  non-resolvable placeholder — the payload JSON never contains storage_uri,
  file_path, work_root or a private file_id;
- the private (authenticated) history payload keeps the real file_id, and
  the scrubbed display key cannot resolve any registry file, so the public
  payload carries no usable key for the auth-protected preview/download
  endpoints.
"""

import importlib
import io
import json
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy.pool import StaticPool

from dbgpt.storage.chat_history.chat_history_db import (
    ChatHistoryEntity,  # noqa: F401  (registers the table)
)
from dbgpt.storage.metadata import db
from dbgpt_app.share.models import ShareLinkEntity  # noqa: F401  (registers table)
from dbgpt_serve.conversation.config import ServeConfig
from dbgpt_serve.conversation.models.models import ServeDao
from dbgpt_serve.session_file.inspector import SessionFileInspector
from dbgpt_serve.session_file.models.dao import SessionFileDao
from dbgpt_serve.session_file.models.models import SessionFileEntity  # noqa: F401
from dbgpt_serve.session_file.registry import SessionFileRegistry
from dbgpt_serve.utils.auth import UserRequest

OWNER = "alice"
OTHER = "bob"
CONV = "conv-share-1"
SESSION = "sess-share-1"
SECRET_FILE_ID = "sf_9f8b7c6a5b4c3d2e1f"

_V1_CONTEXT = json.dumps(
    {
        "version": 1,
        "type": "react-agent",
        "final_content": "legacy answer",
        "steps": [{"id": "s1", "status": "done"}],
        "task_plan": [],
        "generated_images": [],
        "sub_agents": [],
    },
    ensure_ascii=False,
)


class _FakeStorageClient:
    """In-memory FileStorageClient seam double."""

    def __init__(self):
        self.saved = {}

    def save_file(
        self,
        bucket,
        file_name,
        file_data,
        storage_type=None,
        custom_metadata=None,
        file_id=None,
    ):
        data = file_data.read()
        uri = f"dbgpt-fs://local/{bucket}/{file_id}"
        self.saved[uri] = data
        return uri

    def get_file(self, uri):
        if uri not in self.saved:
            raise FileNotFoundError(uri)
        metadata = SimpleNamespace(
            file_id=uri.rsplit("/", 1)[-1],
            file_size=len(self.saved[uri]),
            file_hash="-1",
            uri=uri,
        )
        return io.BytesIO(self.saved[uri]), metadata

    def delete_file(self, uri):
        return self.saved.pop(uri, None) is not None


def _trusted_inspector() -> SessionFileInspector:
    base = SessionFileInspector()
    return SessionFileInspector(
        optional_import=importlib.import_module,
        parsers={
            ".csv": base._parse_delimited,
            ".txt": base._parse_text,
        },
    )


def _init_memory_db():
    db.init_db(
        "sqlite:///:memory:",
        engine_args={
            "connect_args": {"check_same_thread": False},
            "poolclass": StaticPool,
        },
    )
    db.create_all()


@pytest.fixture()
def share_env(monkeypatch):
    from dbgpt_app.openapi.api_v1 import agentic_data_api

    _init_memory_db()
    share_dao = _share_dao()
    state = {"history": []}
    service = SimpleNamespace(
        dao=ServeDao(ServeConfig()),
        get_history_messages=lambda request: state["history"],
    )
    monkeypatch.setattr(agentic_data_api, "_get_share_dao", lambda: share_dao)
    monkeypatch.setattr(agentic_data_api, "_get_conversation_service", lambda: service)
    return SimpleNamespace(module=agentic_data_api, share_dao=share_dao, state=state)


def _share_dao():
    from dbgpt_app.share.models import ShareLinkDao

    return ShareLinkDao()


@pytest.fixture()
def registry(tmp_path):
    from dbgpt_serve.session_file.config import ServeConfig as SessionFileConfig

    _init_memory_db()
    return SessionFileRegistry(
        storage_client=_FakeStorageClient(),
        dao=SessionFileDao(),
        inspector=_trusted_inspector(),
        config=SessionFileConfig(),
        work_root=tmp_path / "work",
    )


def _create_conversation(env, conv_uid=CONV, user_name=OWNER):
    with env.share_dao.session() as session:
        session.add(
            ChatHistoryEntity(
                conv_uid=conv_uid,
                chat_mode="chat_react_agent",
                summary="summarize these files",
                user_name=user_name,
            )
        )


# ---------------------------------------------------------------------------
# Ownership checks on create/delete
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_owner_can_create_and_delete_share(share_env):
    module = share_env.module
    _create_conversation(share_env)

    created = await module.create_share_link(
        module.ShareCreateRequest(conv_uid=CONV),
        UserRequest(user_id=OWNER),
    )

    assert created.success is True
    token = created.data.token
    assert created.data.conv_uid == CONV
    assert created.data.share_url == f"/share/{token}"
    assert share_env.share_dao.get_by_conv_uid(CONV).created_by == OWNER

    deleted = await module.delete_share_link(token, UserRequest(user_id=OWNER))

    assert deleted.success is True
    assert share_env.share_dao.get_by_token(token) is None


@pytest.mark.asyncio
async def test_foreign_user_cannot_create_share(share_env):
    module = share_env.module
    _create_conversation(share_env)

    with pytest.raises(HTTPException) as exc_info:
        await module.create_share_link(
            module.ShareCreateRequest(conv_uid=CONV),
            UserRequest(user_id=OTHER),
        )

    assert exc_info.value.status_code == 403
    assert share_env.share_dao.get_by_conv_uid(CONV) is None


@pytest.mark.asyncio
async def test_anonymous_caller_cannot_create_share_for_owned_conversation(
    share_env,
):
    module = share_env.module
    _create_conversation(share_env)

    with pytest.raises(HTTPException) as exc_info:
        await module.create_share_link(
            module.ShareCreateRequest(conv_uid=CONV),
            None,
        )

    assert exc_info.value.status_code == 403
    assert share_env.share_dao.get_by_conv_uid(CONV) is None


@pytest.mark.asyncio
async def test_create_share_for_unknown_conversation_fails_closed(share_env):
    module = share_env.module

    with pytest.raises(HTTPException) as exc_info:
        await module.create_share_link(
            module.ShareCreateRequest(conv_uid="conv-missing"),
            UserRequest(user_id=OWNER),
        )

    assert exc_info.value.status_code == 404
    assert share_env.share_dao.get_by_conv_uid("conv-missing") is None


@pytest.mark.asyncio
async def test_legacy_anonymous_conversation_remains_shareable(share_env):
    module = share_env.module
    _create_conversation(share_env, conv_uid="conv-legacy", user_name=None)

    created = await module.create_share_link(
        module.ShareCreateRequest(conv_uid="conv-legacy"),
        UserRequest(user_id=OTHER),
    )

    assert created.success is True


@pytest.mark.asyncio
async def test_foreign_user_cannot_delete_share(share_env):
    module = share_env.module
    _create_conversation(share_env)
    link = share_env.share_dao.create_share(conv_uid=CONV, created_by=OWNER)

    with pytest.raises(HTTPException) as exc_info:
        await module.delete_share_link(link.token, UserRequest(user_id=OTHER))

    assert exc_info.value.status_code == 403
    assert share_env.share_dao.get_by_token(link.token) is not None


@pytest.mark.asyncio
async def test_anonymous_caller_cannot_delete_owned_share(share_env):
    module = share_env.module
    _create_conversation(share_env)
    link = share_env.share_dao.create_share(conv_uid=CONV, created_by=OWNER)

    with pytest.raises(HTTPException) as exc_info:
        await module.delete_share_link(link.token, None)

    assert exc_info.value.status_code == 403
    assert share_env.share_dao.get_by_token(link.token) is not None


@pytest.mark.asyncio
async def test_legacy_anonymous_share_remains_deletable(share_env):
    module = share_env.module
    _create_conversation(share_env, user_name=None)
    link = share_env.share_dao.create_share(conv_uid=CONV, created_by=None)

    deleted = await module.delete_share_link(link.token, UserRequest(user_id=OTHER))

    assert deleted.success is True
    assert share_env.share_dao.get_by_token(link.token) is None


@pytest.mark.asyncio
async def test_delete_unknown_share_yields_404(share_env):
    module = share_env.module

    with pytest.raises(HTTPException) as exc_info:
        await module.delete_share_link("missing-token", UserRequest(user_id=OWNER))

    assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# Public payload scrubbing
# ---------------------------------------------------------------------------


def _polluted_v2_context():
    from dbgpt_app.openapi.api_v1.agentic_data_api import (
        _build_react_history_payload,
    )

    # Simulate a stored entry polluted with server-side internals; the public
    # rewrite must strip them by allowlist instead of copying keys through.
    polluted_entry = {
        "file_id": SECRET_FILE_ID,
        "name": "report.csv",
        "size": 13,
        "media_type": "text/csv",
        "kind": "table",
        "status": "ready",
        "ordinal": 0,
        "storage_uri": "dbgpt-fs://secret-bucket/report.csv",
        "file_path": "/private/work/run/report.csv",
        "work_root": "/private/work",
        "owner_id": OWNER,
        "sha256": "deadbeef" * 8,
        "inspection": {"preview": {"columns": ["secret"]}},
    }
    return _build_react_history_payload(
        final_content="analysis answer",
        steps=[{"id": "s1", "status": "done", "outputs": []}],
        task_plan=[],
        generated_images=[],
        sub_agents=[],
        input_files=[polluted_entry],
    )


@pytest.mark.asyncio
async def test_public_share_scrubs_v2_input_files_and_private_markers(share_env):
    module = share_env.module
    share_env.state["history"] = [
        SimpleNamespace(role="view", context=_polluted_v2_context(), order=1)
    ]
    link = share_env.share_dao.create_share(conv_uid=CONV, created_by=OWNER)

    result = await module.get_share_conversation(link.token)

    assert result.success is True
    scrubbed = result.data.messages[0]["context"]
    parsed = json.loads(scrubbed)
    assert parsed["version"] == 2
    assert parsed["final_content"] == "analysis answer"
    assert parsed["steps"] == [{"id": "s1", "status": "done", "outputs": []}]
    assert parsed["input_files"] == [
        {
            "display_key": "file-1",
            "name": "report.csv",
            "size": 13,
            "media_type": "text/csv",
            "kind": "table",
            "status": "ready",
            "ordinal": 0,
        }
    ]
    for marker in (
        SECRET_FILE_ID,
        "file_id",
        "storage_uri",
        "file_path",
        "work_root",
        "/private/work",
        "dbgpt-fs://",
        "owner_id",
        "sha256",
        "deadbeef",
    ):
        assert marker not in scrubbed


@pytest.mark.asyncio
async def test_public_share_leaves_v1_and_plain_text_messages_untouched(share_env):
    module = share_env.module
    share_env.state["history"] = [
        SimpleNamespace(role="human", context="分析这些文件", order=0),
        SimpleNamespace(role="view", context=_V1_CONTEXT, order=1),
    ]
    link = share_env.share_dao.create_share(conv_uid=CONV, created_by=OWNER)

    result = await module.get_share_conversation(link.token)

    assert result.success is True
    assert result.data.messages[0]["context"] == "分析这些文件"
    assert result.data.messages[1]["context"] == _V1_CONTEXT
    parsed_v1 = json.loads(result.data.messages[1]["context"])
    assert parsed_v1["version"] == 1
    assert parsed_v1["final_content"] == "legacy answer"


@pytest.mark.asyncio
async def test_private_history_payload_keeps_resolvable_file_id(share_env):
    from dbgpt_app.openapi.api_v1.agentic_data_api import (
        _build_react_history_payload,
    )

    private_context = _build_react_history_payload(
        final_content="analysis answer",
        steps=[],
        task_plan=[],
        generated_images=[],
        sub_agents=[],
        input_files=[
            {
                "file_id": SECRET_FILE_ID,
                "name": "report.csv",
                "size": 13,
                "media_type": "text/csv",
                "kind": "table",
                "status": "ready",
                "ordinal": 0,
            }
        ],
    )

    parsed_private = json.loads(private_context)
    assert parsed_private["input_files"][0]["file_id"] == SECRET_FILE_ID

    module = share_env.module
    share_env.state["history"] = [
        SimpleNamespace(role="view", context=private_context, order=1)
    ]
    link = share_env.share_dao.create_share(conv_uid=CONV, created_by=OWNER)
    result = await module.get_share_conversation(link.token)
    scrubbed = result.data.messages[0]["context"]

    assert SECRET_FILE_ID in private_context
    assert SECRET_FILE_ID not in scrubbed


def test_scrubbed_display_key_is_not_resolvable_in_registry(registry):
    display_key = "file-1"  # the scrubber's non-resolvable placeholder

    assert (
        registry.get_file(owner_id=OWNER, session_id=SESSION, file_id=display_key)
        is None
    )
