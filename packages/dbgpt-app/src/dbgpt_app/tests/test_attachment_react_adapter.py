"""Tests for the session-file attachments to ReAct agent bridge.

Covers:
- 400 mapping for conflicting/malformed/too-many chat file inputs via the
  FileInputSpec domain contract;
- owner + conversation scoped file_ids resolution with indistinguishable,
  non-enumerating 404 errors for missing/foreign/wrong-session/not-ready
  files (ready and preview_failed are the only accepted states);
- prompt-safe public manifests (never absolute paths, storage URIs, bodies
  or hashes) and internal-only materialized paths / files_json mapping;
- react_state wiring and legacy/text-only byte-for-byte preservation.
"""

import importlib
import io
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.pool import StaticPool

from dbgpt.storage.metadata import db
from dbgpt_app.openapi.api_view_model import ConversationVo
from dbgpt_serve.session_file.domain import (
    FileInputError,
    FileInputSpec,
    FileScope,
    SessionFileStatus,
)
from dbgpt_serve.session_file.inspector import SessionFileInspector
from dbgpt_serve.session_file.models.dao import SessionFileDao
from dbgpt_serve.session_file.models.models import SessionFileEntity  # noqa: F401
from dbgpt_serve.session_file.registry import SessionFileRegistry
from dbgpt_serve.utils.auth import UserRequest

OWNER = "alice"
OTHER_OWNER = "bob"
SESSION = "sess-1"
OTHER_SESSION = "sess-2"
CSV_CONTENT = b"colA,colB\n1,2\n"
TXT_CONTENT = b"hello attachments"


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


@pytest.fixture()
def registry(tmp_path):
    db.init_db(
        "sqlite:///:memory:",
        engine_args={
            "connect_args": {"check_same_thread": False},
            "poolclass": StaticPool,
        },
    )
    db.create_all()
    return SessionFileRegistry(
        storage_client=_FakeStorageClient(),
        dao=SessionFileDao(),
        inspector=_trusted_inspector(),
        config=_serve_config(),
        work_root=tmp_path / "work",
    )


def _serve_config():
    from dbgpt_serve.session_file.config import ServeConfig

    return ServeConfig()


def _ingest(
    registry,
    name="report.csv",
    content=CSV_CONTENT,
    owner=OWNER,
    session=SESSION,
    media="text/csv",
):
    return registry.ingest(
        owner_id=owner,
        session_id=session,
        display_name=name,
        media_type=media,
        stream=io.BytesIO(content),
        size_bytes=len(content),
    )


def _set_status(registry, file_id, status, owner=OWNER, session=SESSION):
    registry.dao.update_status(
        file_id,
        FileScope(owner, session_id=session),
        status,
        inspection_json=json.dumps({"preview": {}, "truncated": False}),
        error_code=None,
        error_message=None,
    )


def _dialogue(ext_info, conv_uid=SESSION):
    return ConversationVo(
        conv_uid=conv_uid,
        user_input="分析这些文件",
        ext_info=ext_info,
    )


_NOT_FOUND = (404, "SESSION_FILE_NOT_FOUND", "File not found.")


def _assert_not_found(error):
    assert error.status_code == _NOT_FOUND[0]
    assert error.code == _NOT_FOUND[1]
    assert error.message == _NOT_FOUND[2]


# ---------------------------------------------------------------------------
# 400 mapping through the FileInputSpec domain contract
# ---------------------------------------------------------------------------


def test_parse_chat_file_input_conflict_maps_to_400():
    from dbgpt_app.openapi.api_v1.attachment_react_adapter import (
        AttachmentInputError,
        parse_chat_file_input,
    )

    with pytest.raises(AttachmentInputError) as exc_info:
        parse_chat_file_input({"file_ids": ["sf_a"], "file_path": "/legacy/a.csv"})

    assert exc_info.value.status_code == 400
    assert exc_info.value.code == "CONFLICTING_FILE_INPUTS"
    assert "file_ids" in exc_info.value.message
    assert "file_path" in exc_info.value.message


@pytest.mark.parametrize(
    "file_ids",
    [[], "sf_a", {"sf_a": 1}, ["sf_a", 1], ["sf_a", ""], ["sf_a", "   "]],
)
def test_parse_chat_file_input_malformed_maps_to_400(file_ids):
    from dbgpt_app.openapi.api_v1.attachment_react_adapter import (
        AttachmentInputError,
        parse_chat_file_input,
    )

    with pytest.raises(AttachmentInputError) as exc_info:
        parse_chat_file_input({"file_ids": file_ids})

    assert exc_info.value.status_code == 400
    assert exc_info.value.code == "INVALID_FILE_IDS"


def test_parse_chat_file_input_too_many_maps_to_400():
    from dbgpt_app.openapi.api_v1.attachment_react_adapter import (
        AttachmentInputError,
        parse_chat_file_input,
    )

    too_many = [f"sf_{idx}" for idx in range(21)]
    with pytest.raises(AttachmentInputError) as exc_info:
        parse_chat_file_input({"file_ids": too_many})

    assert exc_info.value.status_code == 400
    assert exc_info.value.code == "TOO_MANY_FILES"


def test_parse_chat_file_input_returns_domain_spec():
    from dbgpt_app.openapi.api_v1.attachment_react_adapter import (
        parse_chat_file_input,
    )

    spec = parse_chat_file_input({"file_ids": ["sf_b", "sf_a", "sf_b"]})

    assert isinstance(spec, FileInputSpec)
    assert spec.file_ids == ("sf_b", "sf_a")
    assert parse_chat_file_input({"file_path": "/legacy/a.csv"}).file_path == (
        "/legacy/a.csv"
    )
    assert parse_chat_file_input(None) == FileInputSpec.empty()
    assert parse_chat_file_input({"skill_name": "sql"}) == FileInputSpec.empty()


# ---------------------------------------------------------------------------
# Owner + session scoped resolution with non-enumerating 404s
# ---------------------------------------------------------------------------


def test_open_attachments_missing_file_yields_404(registry):
    from dbgpt_app.openapi.api_v1.attachment_react_adapter import (
        AttachmentInputError,
        open_session_attachments,
    )

    with pytest.raises(AttachmentInputError) as exc_info:
        open_session_attachments(
            registry,
            owner_id=OWNER,
            session_id=SESSION,
            file_ids=("sf_missing",),
        )

    _assert_not_found(exc_info.value)


def test_open_attachments_foreign_owner_yields_identical_404(registry):
    from dbgpt_app.openapi.api_v1.attachment_react_adapter import (
        AttachmentInputError,
        open_session_attachments,
    )

    foreign = _ingest(registry, owner=OTHER_OWNER)
    with pytest.raises(AttachmentInputError) as exc_info:
        open_session_attachments(
            registry,
            owner_id=OWNER,
            session_id=SESSION,
            file_ids=(foreign.file_id,),
        )

    _assert_not_found(exc_info.value)


def test_open_attachments_wrong_session_yields_identical_404(registry):
    from dbgpt_app.openapi.api_v1.attachment_react_adapter import (
        AttachmentInputError,
        open_session_attachments,
    )

    record = _ingest(registry, session=OTHER_SESSION)
    with pytest.raises(AttachmentInputError) as exc_info:
        open_session_attachments(
            registry,
            owner_id=OWNER,
            session_id=SESSION,
            file_ids=(record.file_id,),
        )

    _assert_not_found(exc_info.value)


@pytest.mark.parametrize(
    "status",
    [
        SessionFileStatus.UPLOADING,
        SessionFileStatus.INSPECTING,
        SessionFileStatus.FAILED,
        SessionFileStatus.DELETED,
    ],
)
def test_open_attachments_non_ready_statuses_yield_identical_404(registry, status):
    from dbgpt_app.openapi.api_v1.attachment_react_adapter import (
        AttachmentInputError,
        open_session_attachments,
    )

    record = _ingest(registry)
    _set_status(registry, record.file_id, status)
    with pytest.raises(AttachmentInputError) as exc_info:
        open_session_attachments(
            registry,
            owner_id=OWNER,
            session_id=SESSION,
            file_ids=(record.file_id,),
        )

    _assert_not_found(exc_info.value)


def test_open_attachments_physically_deleted_file_yields_identical_404(registry):
    from dbgpt_app.openapi.api_v1.attachment_react_adapter import (
        AttachmentInputError,
        open_session_attachments,
    )

    record = _ingest(registry)
    assert registry.delete_file(
        owner_id=OWNER, session_id=SESSION, file_id=record.file_id
    )
    with pytest.raises(AttachmentInputError) as exc_info:
        open_session_attachments(
            registry,
            owner_id=OWNER,
            session_id=SESSION,
            file_ids=(record.file_id,),
        )

    _assert_not_found(exc_info.value)


# ---------------------------------------------------------------------------
# Successful resolution: order, accepted states, prompt safety, lifecycle
# ---------------------------------------------------------------------------


def test_open_attachments_orders_by_request_and_accepts_preview_failed(registry):
    from dbgpt_app.openapi.api_v1.attachment_react_adapter import (
        open_session_attachments,
    )

    ready = _ingest(registry, name="a.csv")
    preview_failed = _ingest(
        registry,
        name="notes.txt",
        content=TXT_CONTENT,
        media="text/plain",
    )
    _set_status(registry, preview_failed.file_id, SessionFileStatus.PREVIEW_FAILED)

    ctx = open_session_attachments(
        registry,
        owner_id=OWNER,
        session_id=SESSION,
        file_ids=(preview_failed.file_id, ready.file_id),
    )
    try:
        assert [m.file_id for m in ctx.manifests] == [
            preview_failed.file_id,
            ready.file_id,
        ]
        assert ctx.manifests[0].status == SessionFileStatus.PREVIEW_FAILED
        assert ctx.manifests[1].status == SessionFileStatus.READY
        assert ctx.primary_local_path == ctx.local_paths[preview_failed.file_id]
    finally:
        ctx.close()


def test_open_attachments_materializes_until_turn_ends(registry):
    from dbgpt_app.openapi.api_v1.attachment_react_adapter import (
        open_session_attachments,
    )

    first = _ingest(registry, name="a.csv")
    second = _ingest(registry, name="b.csv", content=b"x,y\n3,4\n")

    ctx = open_session_attachments(
        registry,
        owner_id=OWNER,
        session_id=SESSION,
        file_ids=(first.file_id, second.file_id),
    )
    paths = dict(ctx.local_paths)
    files_json_path = ctx.files_json_path

    from pathlib import Path

    for file_id, local_path in paths.items():
        path = Path(local_path)
        assert path.is_file()
        assert path.is_relative_to(registry.work_root)

    files_json = Path(files_json_path)
    assert files_json.is_file()
    mapping = json.loads(files_json.read_text(encoding="utf-8"))
    assert mapping == {
        first.file_id: paths[first.file_id],
        second.file_id: paths[second.file_id],
    }

    ctx.close()
    for local_path in paths.values():
        assert not Path(local_path).exists()
    assert not files_json.exists()


def test_prompt_lists_numbered_manifests_without_private_fields(registry):
    from dbgpt_app.openapi.api_v1.attachment_react_adapter import (
        build_file_context,
        open_session_attachments,
    )

    record = _ingest(registry)
    ctx = open_session_attachments(
        registry,
        owner_id=OWNER,
        session_id=SESSION,
        file_ids=(record.file_id,),
    )
    try:
        prompt = ctx.prompt
        expected = (
            "\n## User Attachments\n"
            f"1. [{record.file_id}] report.csv — table, text/csv, "
            f"{len(CSV_CONTENT)} B, ready\n"
            f"   path: {ctx.primary_local_path} (valid for this turn only)\n"
            "- Analyze these files if needed for the user's request. Use the "
            "shown path with code_interpreter for free-form analysis (valid "
            "for this turn only — re-run load_file in a new turn), or "
            "reference files by file_id.\n"
        )
        assert prompt == expected
        # The per-turn materialized path is intentionally exposed for
        # analysis; storage internals must never leak into the prompt.
        assert record.storage_uri not in prompt
        assert record.sha256 not in prompt
        assert ctx.files_json_path not in prompt
        # And the file_context builder uses exactly the same prompt block.
        assert build_file_context(ctx, None) == prompt
    finally:
        ctx.close()


def test_manifest_prompt_includes_ids_and_names_for_multiple_ready_files(registry):
    from dbgpt_app.openapi.api_v1.attachment_react_adapter import (
        open_session_attachments,
    )

    first = _ingest(registry, name="a.csv")
    second = _ingest(registry, name="b.csv", content=b"x,y\n3,4\n")
    ctx = open_session_attachments(
        registry,
        owner_id=OWNER,
        session_id=SESSION,
        file_ids=(first.file_id, second.file_id),
    )
    try:
        lines = ctx.prompt.strip().splitlines()
        assert lines[0] == "## User Attachments"
        assert lines[1].startswith(f"1. [{first.file_id}] a.csv — table, text/csv, ")
        assert lines[3].startswith(f"2. [{second.file_id}] b.csv — table, text/csv, ")
        assert first.file_id in ctx.prompt
        assert "a.csv" in ctx.prompt
        # Materialized per-turn paths are listed for in-turn analysis.
        for local_path in ctx.local_paths.values():
            assert local_path in ctx.prompt
        # The internal child-process handoff file stays invisible.
        assert ctx.files_json_path not in ctx.prompt
    finally:
        ctx.close()


@pytest.mark.asyncio
async def test_prepare_logs_ids_and_names_but_never_paths(registry, caplog):
    from dbgpt_app.openapi.api_v1.attachment_react_adapter import (
        prepare_react_attachments,
    )

    record = _ingest(registry)
    with caplog.at_level("DEBUG"):
        ctx = await prepare_react_attachments(
            _dialogue({"file_ids": [record.file_id]}),
            owner_id=OWNER,
            registry=registry,
        )
    try:
        logged = caplog.text
        assert ctx.primary_local_path not in logged
        assert ctx.files_json_path not in logged
        assert record.storage_uri not in logged
        assert record.sha256 not in logged
    finally:
        ctx.close()


# ---------------------------------------------------------------------------
# react_state wiring helpers
# ---------------------------------------------------------------------------


def test_react_state_patch_exposes_internal_paths_and_public_manifests(registry):
    from dbgpt_app.openapi.api_v1.attachment_react_adapter import (
        open_session_attachments,
        react_state_patch,
    )
    from dbgpt_serve.session_file.domain import SessionFileManifest

    first = _ingest(registry, name="a.csv")
    second = _ingest(registry, name="b.csv", content=b"x,y\n3,4\n")
    ctx = open_session_attachments(
        registry,
        owner_id=OWNER,
        session_id=SESSION,
        file_ids=(first.file_id, second.file_id),
    )
    try:
        patch = react_state_patch(ctx)
        assert patch["file_path"] == ctx.primary_local_path
        assert patch["files_json_path"] == ctx.files_json_path
        manifests = patch["session_files"]
        assert len(manifests) == 2
        for manifest in manifests:
            assert isinstance(manifest, SessionFileManifest)
            public_fields = set(type(manifest).__dataclass_fields__)
            assert public_fields == {
                "file_id",
                "name",
                "size",
                "media_type",
                "kind",
                "status",
                "ordinal",
            }
    finally:
        ctx.close()


def test_react_state_patch_includes_public_inspection_summaries(registry):
    from dbgpt_app.openapi.api_v1.attachment_react_adapter import (
        open_session_attachments,
        react_state_patch,
    )

    record = _ingest(registry)
    ctx = open_session_attachments(
        registry,
        owner_id=OWNER,
        session_id=SESSION,
        file_ids=(record.file_id,),
    )
    try:
        patch = react_state_patch(ctx)
        inspections = patch["session_file_inspections"]
        assert set(inspections) == {record.file_id}
        preview = inspections[record.file_id]["preview"]
        assert isinstance(preview, dict)
        assert "rows" in preview
        assert inspections[record.file_id]["truncated"] is False
        # Inspection summaries are public: no storage internals or paths.
        payload = json.dumps(inspections, ensure_ascii=False, default=str)
        assert str(registry.work_root) not in payload
        assert record.storage_uri not in payload
        assert record.sha256 not in payload
        assert ctx.primary_local_path not in payload
        assert ctx.files_json_path not in payload
    finally:
        ctx.close()


# ---------------------------------------------------------------------------
# file_context: new wording / legacy path byte-for-byte / pure text unchanged
# ---------------------------------------------------------------------------


def test_build_file_context_keeps_legacy_path_prompt_byte_for_byte():
    from dbgpt_app.openapi.api_v1.attachment_react_adapter import build_file_context

    legacy = build_file_context(None, "/legacy/path/file.csv")

    assert legacy == (
        "\n## User Uploaded File\n"
        "- File path: /legacy/path/file.csv\n"
        "- Analyze this file if needed for the user's request.\n"
    )


def test_build_file_context_returns_empty_for_pure_text():
    from dbgpt_app.openapi.api_v1.attachment_react_adapter import build_file_context

    assert build_file_context(None, None) == ""


# ---------------------------------------------------------------------------
# prepare_react_attachments async entry point
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_prepare_returns_none_for_text_only_request(registry):
    from dbgpt_app.openapi.api_v1.attachment_react_adapter import (
        prepare_react_attachments,
    )

    ctx = await prepare_react_attachments(
        _dialogue({"skill_name": "sql"}), owner_id=OWNER, registry=registry
    )

    assert ctx is None


@pytest.mark.asyncio
async def test_prepare_returns_none_for_legacy_file_path_request(registry):
    from dbgpt_app.openapi.api_v1.attachment_react_adapter import (
        prepare_react_attachments,
    )

    ctx = await prepare_react_attachments(
        _dialogue({"file_path": "/legacy/a.csv"}), owner_id=OWNER, registry=registry
    )

    assert ctx is None


@pytest.mark.asyncio
async def test_prepare_conflict_raises_400_before_any_resolution(registry):
    from dbgpt_app.openapi.api_v1.attachment_react_adapter import (
        AttachmentInputError,
        prepare_react_attachments,
    )

    with pytest.raises(AttachmentInputError) as exc_info:
        await prepare_react_attachments(
            _dialogue({"file_ids": ["sf_a"], "file_path": "/legacy/a.csv"}),
            owner_id=OWNER,
            registry=registry,
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.code == "CONFLICTING_FILE_INPUTS"


@pytest.mark.asyncio
async def test_prepare_resolves_owner_and_conv_session(registry):
    from dbgpt_app.openapi.api_v1.attachment_react_adapter import (
        prepare_react_attachments,
    )

    record = _ingest(registry)
    ctx = await prepare_react_attachments(
        _dialogue({"file_ids": [record.file_id]}), owner_id=OWNER, registry=registry
    )
    try:
        assert ctx is not None
        assert [m.file_id for m in ctx.manifests] == [record.file_id]
    finally:
        ctx.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("conv_uid", ["", "   ", "\t"])
async def test_prepare_blank_conv_uid_maps_to_400_missing_session_id(
    registry, conv_uid
):
    from dbgpt_app.openapi.api_v1.attachment_react_adapter import (
        AttachmentInputError,
        prepare_react_attachments,
    )

    record = _ingest(registry)
    with pytest.raises(AttachmentInputError) as exc_info:
        await prepare_react_attachments(
            _dialogue({"file_ids": [record.file_id]}, conv_uid=conv_uid),
            owner_id=OWNER,
            registry=registry,
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.code == "MISSING_SESSION_ID"
    assert "conversation" in exc_info.value.message.lower()


# ---------------------------------------------------------------------------
# ConversationVo exposes the FileInputSpec domain contract
# ---------------------------------------------------------------------------


def test_conversation_vo_file_input_spec_uses_domain_contract():
    dialogue = _dialogue({"file_ids": ["sf_b", "sf_a"]})

    spec = dialogue.file_input_spec()

    assert isinstance(spec, FileInputSpec)
    assert spec.file_ids == ("sf_b", "sf_a")
    assert _dialogue({}).file_input_spec() == FileInputSpec.empty()
    assert _dialogue(None).file_input_spec() == FileInputSpec.empty()
    with pytest.raises(FileInputError, match="CONFLICTING_FILE_INPUTS"):
        _dialogue({"file_ids": ["sf_a"], "file_path": "/x.csv"}).file_input_spec()


# ---------------------------------------------------------------------------
# Endpoint pre-flight: HTTP errors before streaming/agent construction
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_chat_react_agent_conflict_raises_400_before_streaming(
    registry, monkeypatch
):
    from dbgpt_app.openapi.api_v1 import agentic_data_api, attachment_react_adapter

    monkeypatch.setattr(
        attachment_react_adapter, "_session_file_registry", lambda: registry
    )

    with pytest.raises(HTTPException) as exc_info:
        await agentic_data_api.chat_react_agent(
            _dialogue({"file_ids": ["sf_a"], "file_path": "/x.csv"}),
            UserRequest(user_id=OWNER),
        )

    assert exc_info.value.status_code == 400
    assert "file_ids" in str(exc_info.value.detail)
    assert "file_path" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_chat_react_agent_missing_and_foreign_ids_share_identical_404(
    registry, monkeypatch
):
    from dbgpt_app.openapi.api_v1 import agentic_data_api, attachment_react_adapter

    monkeypatch.setattr(
        attachment_react_adapter, "_session_file_registry", lambda: registry
    )
    foreign = _ingest(registry, owner=OTHER_OWNER)

    errors = []
    for file_id in ("sf_missing", foreign.file_id):
        with pytest.raises(HTTPException) as exc_info:
            await agentic_data_api.chat_react_agent(
                _dialogue({"file_ids": [file_id]}),
                UserRequest(user_id=OWNER),
            )
        errors.append((exc_info.value.status_code, exc_info.value.detail))

    assert errors == [(404, "File not found."), (404, "File not found.")]


@pytest.mark.asyncio
async def test_chat_knowledge_agent_conflict_raises_400_before_streaming(
    registry, monkeypatch
):
    from dbgpt_app.openapi.api_v1 import agentic_data_api, attachment_react_adapter

    monkeypatch.setattr(
        attachment_react_adapter, "_session_file_registry", lambda: registry
    )

    with pytest.raises(HTTPException) as exc_info:
        await agentic_data_api.chat_knowledge_agent(
            _dialogue({"file_ids": ["sf_a"], "file_path": "/x.csv"}),
            UserRequest(user_id=OWNER),
        )

    assert exc_info.value.status_code == 400
    assert "file_ids" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_chat_react_agent_returns_stream_for_valid_file_ids(
    registry, monkeypatch
):
    from dbgpt_app.openapi.api_v1 import agentic_data_api, attachment_react_adapter

    monkeypatch.setattr(
        attachment_react_adapter, "_session_file_registry", lambda: registry
    )
    record = _ingest(registry)

    response = await agentic_data_api.chat_react_agent(
        _dialogue({"file_ids": [record.file_id]}),
        UserRequest(user_id=OWNER),
    )

    assert isinstance(response, StreamingResponse)


# ---------------------------------------------------------------------------
# Stream lifecycle: materialization context closes when the turn ends
# ---------------------------------------------------------------------------


class _ClosableContext:
    def __init__(self):
        self.closed = 0

    def close(self):
        self.closed += 1


@pytest.mark.asyncio
async def test_react_agent_stream_closes_attachment_context_on_completion(
    monkeypatch,
):
    from dbgpt_app.openapi.api_v1 import agentic_data_api

    async def fake_inner(dialogue, tool_mode, attachment_ctx):
        yield "data: ok\n\n"

    monkeypatch.setattr(agentic_data_api, "_react_agent_stream_inner", fake_inner)
    ctx = _ClosableContext()

    chunks = [
        chunk
        async for chunk in agentic_data_api._react_agent_stream(
            _dialogue({}), "full", ctx
        )
    ]

    assert chunks == ["data: ok\n\n"]
    assert ctx.closed == 1


@pytest.mark.asyncio
async def test_react_agent_stream_closes_attachment_context_on_error(monkeypatch):
    from dbgpt_app.openapi.api_v1 import agentic_data_api

    async def failing_inner(dialogue, tool_mode, attachment_ctx):
        yield "data: partial\n\n"
        raise RuntimeError("agent exploded")

    monkeypatch.setattr(agentic_data_api, "_react_agent_stream_inner", failing_inner)
    ctx = _ClosableContext()

    with pytest.raises(RuntimeError, match="agent exploded"):
        async for _ in agentic_data_api._react_agent_stream(_dialogue({}), "full", ctx):
            pass

    assert ctx.closed == 1


@pytest.mark.asyncio
async def test_react_agent_stream_defaults_keep_legacy_call_signature(monkeypatch):
    from dbgpt_app.openapi.api_v1 import agentic_data_api

    seen = {}

    async def fake_inner(dialogue, tool_mode, attachment_ctx):
        seen["tool_mode"] = tool_mode
        seen["attachment_ctx"] = attachment_ctx
        yield "data: ok\n\n"

    monkeypatch.setattr(agentic_data_api, "_react_agent_stream_inner", fake_inner)

    chunks = [
        chunk async for chunk in agentic_data_api._react_agent_stream(_dialogue({}))
    ]

    assert chunks == ["data: ok\n\n"]
    assert seen == {"tool_mode": "full", "attachment_ctx": None}


# ---------------------------------------------------------------------------
# Legacy ext_info.file_path owner isolation (chat side)
# ---------------------------------------------------------------------------

LEGACY_CSV = b"region,sales\nwest,1\n"


def _write_legacy_file(base_dir, owner, name="report.csv", content=LEGACY_CSV):
    owner_root = Path(base_dir) / "python_uploads" / owner
    owner_root.mkdir(parents=True, exist_ok=True)
    target = owner_root / name
    target.write_bytes(content)
    return target


def _resolve(base_dir, owner, file_path):
    from dbgpt_app.openapi.api_v1.attachment_react_adapter import (
        resolve_legacy_chat_file_path,
    )

    return resolve_legacy_chat_file_path(
        file_path=file_path, owner_id=owner, base_dir=str(base_dir)
    )


def test_legacy_resolve_accepts_regular_file_inside_owner_root(tmp_path):
    target = _write_legacy_file(tmp_path, OWNER)

    resolved = _resolve(tmp_path, OWNER, str(target))

    assert resolved == str(target.resolve())


def test_legacy_resolve_rejects_cross_owner_path_with_generic_404(tmp_path):
    foreign = _write_legacy_file(tmp_path, OTHER_OWNER, name="secret.csv")

    with pytest.raises(_attachment_input_error()) as exc_info:
        _resolve(tmp_path, OWNER, str(foreign))

    _assert_not_found(exc_info.value)


def test_legacy_resolve_missing_and_foreign_share_identical_404(tmp_path):
    foreign = _write_legacy_file(tmp_path, OTHER_OWNER, name="secret.csv")
    missing = tmp_path / "python_uploads" / OWNER / "ghost.csv"

    errors = []
    for candidate in (str(foreign), str(missing)):
        with pytest.raises(_attachment_input_error()) as exc_info:
            _resolve(tmp_path, OWNER, candidate)
        errors.append(
            (
                exc_info.value.status_code,
                exc_info.value.code,
                exc_info.value.message,
            )
        )

    assert errors[0] == errors[1] == _NOT_FOUND


def test_legacy_resolve_never_reads_arbitrary_absolute_path(tmp_path):
    outside = tmp_path / "elsewhere" / "secrets.csv"
    outside.parent.mkdir(parents=True)
    outside.write_bytes(b"top,secret\n1,2\n")
    _write_legacy_file(tmp_path, OWNER)

    for candidate in (str(outside), "/etc/passwd"):
        with pytest.raises(_attachment_input_error()) as exc_info:
            _resolve(tmp_path, OWNER, candidate)
        _assert_not_found(exc_info.value)


@pytest.mark.parametrize(
    "file_path",
    [
        "{base}/python_uploads/alice/../bob/secret.csv",
        "{base}/python_uploads/alice/../../bob/secret.csv",
        "{base}/python_uploads/alice/sub/../report.csv",
    ],
)
def test_legacy_resolve_rejects_dot_dot_traversal(tmp_path, file_path):
    _write_legacy_file(tmp_path, OWNER)
    _write_legacy_file(tmp_path, OTHER_OWNER, name="secret.csv")

    with pytest.raises(_attachment_input_error()) as exc_info:
        _resolve(tmp_path, OWNER, file_path.format(base=tmp_path))

    _assert_not_found(exc_info.value)


@pytest.mark.parametrize(
    "file_path",
    [
        "{base}\\python_uploads\\alice\\report.csv",
        "..\\python_uploads\\bob\\secret.csv",
        "python_uploads\\alice\\report.csv",
    ],
)
def test_legacy_resolve_rejects_windows_separators_with_400(tmp_path, file_path):
    _write_legacy_file(tmp_path, OWNER)

    with pytest.raises(_attachment_input_error()) as exc_info:
        _resolve(tmp_path, OWNER, file_path.format(base=tmp_path))

    assert exc_info.value.status_code == 400
    assert exc_info.value.code == "INVALID_FILE_PATH"


@pytest.mark.parametrize("file_path", [None, 3.14, ["a.csv"], {"p": "a.csv"}, ""])
def test_legacy_resolve_rejects_malformed_values_with_400(tmp_path, file_path):
    with pytest.raises(_attachment_input_error()) as exc_info:
        _resolve(tmp_path, OWNER, file_path)

    assert exc_info.value.status_code == 400
    assert exc_info.value.code == "INVALID_FILE_PATH"


def test_legacy_resolve_rejects_null_byte_with_400(tmp_path):
    _write_legacy_file(tmp_path, OWNER)

    with pytest.raises(_attachment_input_error()) as exc_info:
        _resolve(tmp_path, OWNER, "report.csv\x00.exe")

    assert exc_info.value.status_code == 400
    assert exc_info.value.code == "INVALID_FILE_PATH"


def test_legacy_resolve_rejects_final_symlink(tmp_path):
    target = _write_legacy_file(tmp_path, OWNER)
    link = target.parent / "linked.csv"
    try:
        link.symlink_to(target)
    except OSError as exc:
        pytest.skip(f"symlinks are not available in this environment: {exc}")

    with pytest.raises(_attachment_input_error()) as exc_info:
        _resolve(tmp_path, OWNER, str(link))

    _assert_not_found(exc_info.value)
    assert target.read_bytes() == LEGACY_CSV


def test_legacy_resolve_rejects_symlinked_parent_component(tmp_path):
    owner_root = Path(tmp_path) / "python_uploads" / OWNER
    owner_root.mkdir(parents=True)
    outside_dir = tmp_path / "escape"
    outside_dir.mkdir()
    escape_file = outside_dir / "stolen.csv"
    escape_file.write_bytes(b"a,b\n1,2\n")
    try:
        (owner_root / "linkdir").symlink_to(outside_dir, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"symlinks are not available in this environment: {exc}")

    with pytest.raises(_attachment_input_error()) as exc_info:
        _resolve(tmp_path, OWNER, str(owner_root / "linkdir" / "stolen.csv"))

    _assert_not_found(exc_info.value)


def test_legacy_resolve_rejects_symlinked_owner_root(tmp_path):
    uploads_root = Path(tmp_path) / "python_uploads"
    uploads_root.mkdir(parents=True)
    escape_dir = tmp_path / "escape"
    escape_dir.mkdir()
    (escape_dir / "data.csv").write_bytes(b"a,b\n1,2\n")
    try:
        (uploads_root / "mallory").symlink_to(escape_dir, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"symlinks are not available in this environment: {exc}")

    with pytest.raises(_attachment_input_error()) as exc_info:
        _resolve(tmp_path, "mallory", str(uploads_root / "mallory" / "data.csv"))

    _assert_not_found(exc_info.value)


def test_legacy_resolve_rejects_missing_and_non_regular_files(tmp_path):
    owner_root = _write_legacy_file(tmp_path, OWNER).parent
    directory = owner_root / "a-directory"
    directory.mkdir()

    for candidate in (owner_root / "ghost.csv", directory):
        with pytest.raises(_attachment_input_error()) as exc_info:
            _resolve(tmp_path, OWNER, str(candidate))
        _assert_not_found(exc_info.value)


def test_legacy_relative_path_resolves_inside_owner_root(tmp_path):
    target = _write_legacy_file(tmp_path, OWNER)

    resolved = _resolve(tmp_path, OWNER, "report.csv")

    assert resolved == str(target.resolve())


def test_legacy_blank_owner_is_rejected_with_generic_404(tmp_path):
    target = _write_legacy_file(tmp_path, OWNER)

    for owner in (None, "", "   "):
        with pytest.raises(_attachment_input_error()) as exc_info:
            _resolve(tmp_path, owner, str(target))
        _assert_not_found(exc_info.value)


def _attachment_input_error():
    from dbgpt_app.openapi.api_v1.attachment_react_adapter import (
        AttachmentInputError,
    )

    return AttachmentInputError


# ---------------------------------------------------------------------------
# Endpoint pre-flight: legacy path validation and stream-init failure cleanup
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_chat_react_agent_accepts_valid_legacy_path(tmp_path, monkeypatch):
    from dbgpt_app.openapi.api_v1 import agentic_data_api

    monkeypatch.setattr(
        agentic_data_api, "_legacy_upload_base_dir", lambda: str(tmp_path)
    )
    target = _write_legacy_file(tmp_path, OWNER)
    dialogue = _dialogue({"file_path": str(target)})

    response = await agentic_data_api.chat_react_agent(
        dialogue, UserRequest(user_id=OWNER)
    )

    assert isinstance(response, StreamingResponse)
    assert dialogue.ext_info["file_path"] == str(target.resolve())


@pytest.mark.asyncio
async def test_chat_endpoints_reject_cross_owner_legacy_path_with_generic_404(
    tmp_path, monkeypatch
):
    from dbgpt_app.openapi.api_v1 import agentic_data_api

    monkeypatch.setattr(
        agentic_data_api, "_legacy_upload_base_dir", lambda: str(tmp_path)
    )
    foreign = _write_legacy_file(tmp_path, OTHER_OWNER, name="secret.csv")
    missing = tmp_path / "python_uploads" / OWNER / "ghost.csv"

    for endpoint in (
        agentic_data_api.chat_react_agent,
        agentic_data_api.chat_knowledge_agent,
    ):
        errors = []
        for candidate in (str(foreign), str(missing)):
            with pytest.raises(HTTPException) as exc_info:
                await endpoint(
                    _dialogue({"file_path": str(candidate)}),
                    UserRequest(user_id=OWNER),
                )
            errors.append((exc_info.value.status_code, exc_info.value.detail))

        assert errors == [(404, "File not found."), (404, "File not found.")]


@pytest.mark.asyncio
async def test_chat_react_agent_rejects_arbitrary_legacy_path(tmp_path, monkeypatch):
    from dbgpt_app.openapi.api_v1 import agentic_data_api

    monkeypatch.setattr(
        agentic_data_api, "_legacy_upload_base_dir", lambda: str(tmp_path)
    )
    outside = tmp_path / "elsewhere" / "secrets.csv"
    outside.parent.mkdir(parents=True)
    outside.write_bytes(b"top,secret\n1,2\n")

    with pytest.raises(HTTPException) as exc_info:
        await agentic_data_api.chat_react_agent(
            _dialogue({"file_path": str(outside)}),
            UserRequest(user_id=OWNER),
        )

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "File not found."


@pytest.mark.asyncio
async def test_chat_react_agent_rejects_windows_legacy_path_with_400(
    tmp_path, monkeypatch
):
    from dbgpt_app.openapi.api_v1 import agentic_data_api

    monkeypatch.setattr(
        agentic_data_api, "_legacy_upload_base_dir", lambda: str(tmp_path)
    )
    _write_legacy_file(tmp_path, OWNER)

    with pytest.raises(HTTPException) as exc_info:
        await agentic_data_api.chat_react_agent(
            _dialogue(
                {"file_path": f"{tmp_path}\\python_uploads\\{OWNER}\\report.csv"}
            ),
            UserRequest(user_id=OWNER),
        )

    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_chat_react_agent_closes_attachments_when_stream_response_init_fails(
    registry, monkeypatch
):
    from dbgpt_app.openapi.api_v1 import agentic_data_api, attachment_react_adapter

    monkeypatch.setattr(
        attachment_react_adapter, "_session_file_registry", lambda: registry
    )
    record = _ingest(registry)

    captured = {}
    original_prepare = agentic_data_api.prepare_react_attachments

    async def spy_prepare(dialogue, *, owner_id, registry=None):
        ctx = await original_prepare(dialogue, owner_id=owner_id, registry=registry)
        captured["ctx"] = ctx
        return ctx

    monkeypatch.setattr(agentic_data_api, "prepare_react_attachments", spy_prepare)

    real_streaming_response = agentic_data_api.StreamingResponse
    attempts = {"count": 0}

    def flaky_streaming_response(*args, **kwargs):
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise RuntimeError("stream init exploded")
        return real_streaming_response(*args, **kwargs)

    monkeypatch.setattr(agentic_data_api, "StreamingResponse", flaky_streaming_response)

    response = await agentic_data_api.chat_react_agent(
        _dialogue({"file_ids": [record.file_id]}),
        UserRequest(user_id=OWNER),
    )

    assert isinstance(response, real_streaming_response)
    assert attempts["count"] == 2
    ctx = captured["ctx"]
    assert ctx is not None
    for local_path in ctx.local_paths.values():
        assert not Path(local_path).exists()
    assert not Path(ctx.files_json_path).exists()
    assert not list(registry.work_root.rglob("run_*"))


@pytest.mark.asyncio
async def test_chat_knowledge_agent_closes_attachments_exactly_once_when_stream_fails(
    monkeypatch,
):
    from dbgpt_app.openapi.api_v1 import agentic_data_api

    closable = _ClosableContext()

    async def fake_prepare(dialogue, *, owner_id, registry=None):
        return closable

    monkeypatch.setattr(agentic_data_api, "prepare_react_attachments", fake_prepare)

    real_streaming_response = agentic_data_api.StreamingResponse
    attempts = {"count": 0}

    def flaky_streaming_response(*args, **kwargs):
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise RuntimeError("stream init exploded")
        return real_streaming_response(*args, **kwargs)

    monkeypatch.setattr(agentic_data_api, "StreamingResponse", flaky_streaming_response)

    response = await agentic_data_api.chat_knowledge_agent(
        _dialogue({}), UserRequest(user_id=OWNER)
    )

    assert isinstance(response, real_streaming_response)
    assert attempts["count"] == 2
    assert closable.closed == 1
