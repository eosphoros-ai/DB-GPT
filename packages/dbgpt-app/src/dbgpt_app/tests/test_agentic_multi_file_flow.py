"""End-to-end service contracts for the multi-file agentic flow.

Every test composes the real seams — in-memory SQLite, in-memory
``FileStorageClient``, a fake bounded inspector and a fake agent stream —
instead of slicing them with unit doubles, so the wire between upload,
registry, adapter, history, scheduled task replay and share redaction is
verified as one flow:

- pure-text and legacy ``file_path`` requests stay byte-for-byte untouched;
- one/N ``file_ids`` resolve strictly in request order into a prompt-safe
  manifest, with mixed CSV/XLSX/PDF kinds and preview failures tolerated;
- history payload v2 reloads with public snapshots only;
- scheduled task creation freezes copies and every replay re-copies them
  into a fresh session;
- share payloads are redacted to non-resolvable display keys.
"""

import hashlib
import io
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.responses import StreamingResponse
from sqlalchemy.pool import StaticPool

from dbgpt.storage.chat_history.chat_history_db import ChatHistoryEntity  # noqa: F401
from dbgpt.storage.metadata import db
from dbgpt_app.openapi.api_view_model import ConversationVo
from dbgpt_app.share.models import ShareLinkEntity  # noqa: F401
from dbgpt_serve.scheduled_task.models.scheduled_run_model import (  # noqa: F401
    ScheduledRunEntity,
)
from dbgpt_serve.scheduled_task.models.scheduled_task_model import (  # noqa: F401
    ScheduledTaskEntity,
)
from dbgpt_serve.session_file.config import ServeConfig
from dbgpt_serve.session_file.domain import SessionFileStatus
from dbgpt_serve.session_file.inspector import InspectionResult
from dbgpt_serve.session_file.models.dao import SessionFileDao
from dbgpt_serve.session_file.models.models import SessionFileEntity
from dbgpt_serve.session_file.registry import SessionFileRegistry
from dbgpt_serve.utils.auth import UserRequest

OWNER = "alice"
OTHER_OWNER = "bob"
SESSION = "sess-flow-1"

CSV_BYTES = b"region,sales\nwest,1\neast,2\n"
XLSX_BYTES = b"PK\x03\x04fake-xlsx-bytes-not-parsed-by-fake-inspector"
PDF_BYTES = b"%PDF-1.4 fake pdf bytes"
TXT_BYTES = b"hello flow"

_KIND_BY_SUFFIX = {
    ".csv": ("table", "text/csv"),
    ".xlsx": (
        "table",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ),
    ".pdf": ("document", "application/pdf"),
    ".txt": ("document", "text/plain"),
}


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


class _FakeBoundedInspector:
    """Deterministic bounded-inspector double.

    Returns canned, byte-bounded previews keyed by file suffix (never parses
    real content, so XLSX/PDF flows need no heavyweight parser deps). Suffixes
    listed in ``fail_suffixes`` yield a safe ``PREVIEW_FAILED`` result to
    exercise partial-failure paths.
    """

    def __init__(self, fail_suffixes=()):
        self._fail_suffixes = set(fail_suffixes)

    async def inspect_async(self, path, declared_media_type=None):
        suffix = Path(path).suffix.lower()
        kind, media_type = _KIND_BY_SUFFIX.get(
            suffix, ("binary", "application/octet-stream")
        )
        if suffix in self._fail_suffixes:
            return InspectionResult(
                kind=kind,
                media_type=media_type,
                status=SessionFileStatus.PREVIEW_FAILED,
                preview={},
                truncated=False,
                error_code="CORRUPT_FILE",
                error_message="The file could not be parsed safely.",
            )
        preview = (
            {"columns": ["region", "sales"], "rows": [["west", 1]]}
            if kind == "table"
            else {"metadata": {"pages": 1}}
        )
        return InspectionResult(
            kind=kind,
            media_type=media_type,
            status=SessionFileStatus.READY,
            preview=preview,
            truncated=False,
        )


@pytest.fixture()
def env(tmp_path):
    """Full flow environment: in-memory DB, storage, registry, work root."""
    db.init_db(
        "sqlite:///:memory:",
        engine_args={
            "connect_args": {"check_same_thread": False},
            "poolclass": StaticPool,
        },
    )
    db.create_all()
    storage = _FakeStorageClient()
    registry = SessionFileRegistry(
        storage_client=storage,
        dao=SessionFileDao(),
        inspector=_FakeBoundedInspector(),
        config=ServeConfig(),
        work_root=tmp_path / "work",
    )
    return SimpleNamespace(
        registry=registry,
        storage=storage,
        tmp_path=tmp_path,
        work_root=tmp_path / "work",
    )


def _rebuild_registry(env, **config_overrides) -> SessionFileRegistry:
    """Rebuild the registry on the same DB/storage with tweaked config."""
    registry = SessionFileRegistry(
        storage_client=env.storage,
        dao=SessionFileDao(),
        inspector=_FakeBoundedInspector(),
        config=ServeConfig(**config_overrides),
        work_root=env.work_root,
    )
    env.registry = registry
    return registry


def _ingest(
    env,
    name="report.csv",
    content=CSV_BYTES,
    owner=OWNER,
    session=SESSION,
    media="text/csv",
):
    return env.registry.ingest(
        owner_id=owner,
        session_id=session,
        display_name=name,
        media_type=media,
        stream=io.BytesIO(content),
        size_bytes=len(content),
    )


def _dialogue(ext_info, conv_uid=SESSION):
    return ConversationVo(
        conv_uid=conv_uid,
        user_input="分析这些文件",
        ext_info=ext_info,
    )


def _bind_registry(monkeypatch, registry):
    from dbgpt_app.openapi.api_v1 import attachment_react_adapter

    monkeypatch.setattr(
        attachment_react_adapter, "_session_file_registry", lambda: registry
    )


def _patch_agent_stream(monkeypatch, captured):
    """Swap the ReAct agent executor for a fake capturing its live inputs."""

    async def fake_inner(dialogue, tool_mode, attachment_ctx):
        captured["dialogue"] = dialogue
        captured["tool_mode"] = tool_mode
        captured["attachment_ctx"] = attachment_ctx
        yield 'data: {"type":"final","content":"ok"}'
        yield 'data: {"type":"done"}'

    from dbgpt_app.openapi.api_v1 import agentic_data_api

    monkeypatch.setattr(agentic_data_api, "_react_agent_stream_inner", fake_inner)


async def _run_chat_turn(env, monkeypatch, ext_info, owner=OWNER):
    """Drive one chat turn end to end; returns (chunks, captured)."""
    from dbgpt_app.openapi.api_v1 import agentic_data_api

    _bind_registry(monkeypatch, env.registry)
    captured = {}
    _patch_agent_stream(monkeypatch, captured)
    response = await agentic_data_api.chat_react_agent(
        _dialogue(ext_info), UserRequest(user_id=owner)
    )
    assert isinstance(response, StreamingResponse)
    chunks = [chunk async for chunk in response.body_iterator]
    return chunks, captured


def _session_file_rows():
    """Return every persisted session file row (test inspection only)."""
    with SessionFileDao().session(commit=False) as session:
        return session.query(SessionFileEntity).all()


# ---------------------------------------------------------------------------
# 1. Pure text: zero file behavior is untouched end to end
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pure_text_turn_never_touches_file_seams(env, monkeypatch):
    chunks, captured = await _run_chat_turn(env, monkeypatch, {"skill_id": "s1"})

    assert chunks == ['data: {"type":"final","content":"ok"}', 'data: {"type":"done"}']
    # No attachment context is built for a text-only request.
    assert captured["attachment_ctx"] is None
    # Nothing was persisted anywhere.
    assert env.storage.saved == {}
    assert _session_file_rows() == []
    # The fake agent saw the raw dialogue without file wiring.
    assert captured["dialogue"].ext_info == {"skill_id": "s1"}


# ---------------------------------------------------------------------------
# 2. Legacy owner file: ext_info.file_path keeps the single-file behavior
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_legacy_owner_file_turn_resolves_inside_owner_root(
    env, monkeypatch, tmp_path
):
    from dbgpt_app.openapi.api_v1 import agentic_data_api

    monkeypatch.setattr(
        agentic_data_api, "_legacy_upload_base_dir", lambda: str(tmp_path)
    )
    owner_root = tmp_path / "python_uploads" / OWNER
    owner_root.mkdir(parents=True)
    legacy = owner_root / "legacy.csv"
    legacy.write_bytes(CSV_BYTES)

    chunks, captured = await _run_chat_turn(
        env, monkeypatch, {"file_path": str(legacy)}
    )

    assert len(chunks) == 2
    # Legacy flow stays legacy: no attachment context, no registry rows/blobs.
    assert captured["attachment_ctx"] is None
    assert env.storage.saved == {}
    assert _session_file_rows() == []
    # The dialogue carries the resolved in-root absolute path (existing
    # legacy contract — a validated owner path, identical bytes content).
    resolved = captured["dialogue"].ext_info["file_path"]
    assert resolved == str(legacy.resolve())
    assert Path(resolved).read_bytes() == CSV_BYTES


# ---------------------------------------------------------------------------
# 3. Single new file: ingest -> resolve -> manifest prompt -> cleanup
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_single_file_turn_materializes_and_cleans_up(env, monkeypatch):
    record = _ingest(env)

    chunks, captured = await _run_chat_turn(
        env, monkeypatch, {"file_ids": [record.file_id]}
    )

    assert len(chunks) == 2
    ctx = captured["attachment_ctx"]
    assert ctx is not None
    assert [m.file_id for m in ctx.manifests] == [record.file_id]
    assert ctx.manifests[0].name == "report.csv"
    assert ctx.manifests[0].kind == "table"
    # The turn ended: materialization is gone, blob/row survive for history.
    for local_path in ctx.local_paths.values():
        assert not Path(local_path).exists()
    assert not Path(ctx.files_json_path).exists()
    assert not list(env.work_root.rglob("run_*"))
    assert len(env.storage.saved) == 1
    assert len(_session_file_rows()) == 1


# ---------------------------------------------------------------------------
# 4. N files: manifests follow request order, not upload order
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_n_files_resolve_in_exact_request_order(env, monkeypatch):
    first = _ingest(env, name="a.csv")
    second = _ingest(env, name="b.csv", content=b"x,y\n3,4\n")
    third = _ingest(env, name="c.csv", content=b"p,q\n5,6\n")

    _bind_registry(monkeypatch, env.registry)
    from dbgpt_app.openapi.api_v1.attachment_react_adapter import (
        open_session_attachments,
    )

    ctx = open_session_attachments(
        env.registry,
        owner_id=OWNER,
        session_id=SESSION,
        file_ids=(third.file_id, first.file_id, second.file_id),
    )
    try:
        assert [m.file_id for m in ctx.manifests] == [
            third.file_id,
            first.file_id,
            second.file_id,
        ]
        # Prompt enumerates the same order, numbered 1..N; each manifest
        # line is followed by its per-turn materialized path line.
        lines = ctx.prompt.strip().splitlines()
        assert lines[1].startswith(f"1. [{third.file_id}] c.csv")
        assert lines[3].startswith(f"2. [{first.file_id}] a.csv")
        assert lines[5].startswith(f"3. [{second.file_id}] b.csv")
        # Primary path is the first requested file (single-file tool compat).
        assert ctx.primary_local_path == ctx.local_paths[third.file_id]
        # files_json maps every public id to its materialized path.
        mapping = json.loads(Path(ctx.files_json_path).read_text(encoding="utf-8"))
        assert set(mapping) == {first.file_id, second.file_id, third.file_id}
    finally:
        ctx.close()


# ---------------------------------------------------------------------------
# 5. Mixed CSV/XLSX/PDF: one manifest block carrying every kind
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mixed_kind_manifest_covers_csv_xlsx_pdf(env, monkeypatch):
    csv_rec = _ingest(env, name="sales.csv", content=CSV_BYTES)
    xlsx_rec = _ingest(
        env,
        name="spec.xlsx",
        content=XLSX_BYTES,
        media="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    pdf_rec = _ingest(
        env, name="口径说明.pdf", content=PDF_BYTES, media="application/pdf"
    )

    _, captured = await _run_chat_turn(
        env,
        monkeypatch,
        {"file_ids": [csv_rec.file_id, xlsx_rec.file_id, pdf_rec.file_id]},
    )

    ctx = captured["attachment_ctx"]
    kinds = [m.kind for m in ctx.manifests]
    media_types = [m.media_type for m in ctx.manifests]
    assert kinds == ["table", "table", "document"]
    assert media_types == [
        "text/csv",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/pdf",
    ]
    # One bounded inspection was performed per uploaded file.
    assert len(ctx.inspections) == 3
    # The prompt names every file with its kind and media type.
    for manifest in ctx.manifests:
        assert manifest.name in ctx.prompt
        assert manifest.media_type in ctx.prompt
        assert manifest.kind in ctx.prompt


# ---------------------------------------------------------------------------
# 6. One preview failure must not block the rest of the batch
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_preview_failure_does_not_block_sibling_files(env, monkeypatch):
    env.registry._inspector._fail_suffixes.add(".pdf")
    good = _ingest(env, name="good.csv", content=CSV_BYTES)
    degraded = _ingest(
        env, name="口径说明.pdf", content=PDF_BYTES, media="application/pdf"
    )

    assert good.status == SessionFileStatus.READY
    assert degraded.status == SessionFileStatus.PREVIEW_FAILED
    assert degraded.error_code == "CORRUPT_FILE"

    _, captured = await _run_chat_turn(
        env, monkeypatch, {"file_ids": [good.file_id, degraded.file_id]}
    )
    ctx = captured["attachment_ctx"]

    # preview_failed is a soft warning: both files still reach the agent.
    assert [m.file_id for m in ctx.manifests] == [good.file_id, degraded.file_id]
    statuses = {m.file_id: m.status for m in ctx.manifests}
    assert statuses[good.file_id] == SessionFileStatus.READY
    assert statuses[degraded.file_id] == SessionFileStatus.PREVIEW_FAILED
    # Inspection summaries stay public and bounded for both files.
    assert ctx.inspections[good.file_id]["preview"]
    assert ctx.inspections[degraded.file_id]["preview"] == {}
    assert ctx.inspections[degraded.file_id]["truncated"] is False


# ---------------------------------------------------------------------------
# 7. History payload v2: reload round-trip keeps the turn snapshot
# ---------------------------------------------------------------------------


def test_history_payload_v2_reloads_with_public_snapshots(env):
    from dbgpt_app.openapi.api_v1.agentic_data_api import (
        _build_react_history_payload,
    )
    from dbgpt_app.openapi.api_v1.attachment_react_adapter import (
        build_input_files_v2,
        open_session_attachments,
    )

    first = _ingest(env, name="a.csv")
    second = _ingest(env, name="b.csv", content=b"x,y\n3,4\n")
    ctx = open_session_attachments(
        env.registry,
        owner_id=OWNER,
        session_id=SESSION,
        file_ids=(first.file_id, second.file_id),
    )
    try:
        input_files = build_input_files_v2(ctx.manifests)
    finally:
        ctx.close()

    for final_content, steps in (
        ("分析完成", [{"id": "s1", "status": "done"}]),
        ("React agent failed: boom", [{"id": "s1", "status": "failed"}]),
    ):
        raw = _build_react_history_payload(
            final_content=final_content,
            steps=steps,
            task_plan=[],
            generated_images=[],
            sub_agents=[],
            input_files=input_files,
        )
        reloaded = json.loads(raw)
        assert reloaded["version"] == 2
        assert reloaded["type"] == "react-agent"
        assert reloaded["final_content"] == final_content
        assert [f["file_id"] for f in reloaded["input_files"]] == [
            first.file_id,
            second.file_id,
        ]
        for entry in reloaded["input_files"]:
            assert set(entry) == {
                "file_id",
                "name",
                "size",
                "media_type",
                "kind",
                "status",
                "ordinal",
            }
        # Reloading the stored payload never re-derives files from old turns:
        # later turns resolve fresh from the registry, so a deleted file
        # cannot silently resurrect into a future turn.
        assert first.storage_uri not in raw
        assert first.sha256 not in raw
        assert str(env.work_root) not in raw


def test_history_snapshot_survives_source_file_deletion(env):
    """Immutable snapshots keep old turns readable after the source file is
    gone; reloaded history never depends on live registry state."""
    from dbgpt_app.openapi.api_v1.agentic_data_api import (
        _build_react_history_payload,
    )
    from dbgpt_app.openapi.api_v1.attachment_react_adapter import (
        build_input_files_v2,
        open_session_attachments,
    )

    record = _ingest(env)
    ctx = open_session_attachments(
        env.registry,
        owner_id=OWNER,
        session_id=SESSION,
        file_ids=(record.file_id,),
    )
    try:
        input_files = build_input_files_v2(ctx.manifests)
    finally:
        ctx.close()
    raw = _build_react_history_payload(
        final_content="done",
        steps=[],
        task_plan=[],
        generated_images=[],
        sub_agents=[],
        input_files=input_files,
    )

    assert env.registry.delete_file(
        owner_id=OWNER, session_id=SESSION, file_id=record.file_id
    )

    reloaded = json.loads(raw)
    snapshot = reloaded["input_files"][0]
    assert snapshot["file_id"] == record.file_id
    assert snapshot["name"] == "report.csv"
    assert snapshot["status"] == "ready"


# ---------------------------------------------------------------------------
# 8. Scheduled task: files are frozen on create and re-copied per run
# ---------------------------------------------------------------------------


class _FakeScheduler:
    """In-memory TaskScheduler double (async job writes)."""

    def __init__(self):
        self.jobs = {}

    async def add_job(self, job_id, cron_expression, func, kwargs):
        self.jobs[job_id] = {"cron_expression": cron_expression, "kwargs": kwargs}

    async def remove_job(self, job_id):
        self.jobs.pop(job_id, None)

    def get_job(self, job_id):
        return self.jobs.get(job_id)

    def list_jobs(self):
        return [{"job_id": job_id, "next_run_time": None} for job_id in self.jobs]

    def pause_job(self, job_id):
        pass

    def resume_job(self, job_id):
        pass


@pytest.mark.asyncio
async def test_scheduled_task_freezes_then_replays_immutable_inputs(env, monkeypatch):
    from dbgpt_serve.scheduled_task.api.schemas import (
        ChatReplayPayload,
        CreateTaskRequest,
    )
    from dbgpt_serve.scheduled_task.dao.run_dao import ScheduledRunDao
    from dbgpt_serve.scheduled_task.service.chat_replay_runner import (
        ChatReplayRunner,
    )
    from dbgpt_serve.scheduled_task.service.service import ScheduledTaskService

    first = _ingest(env, name="a.csv")
    second = _ingest(env, name="b.csv", content=b"x,y\n3,4\n")
    scheduler = _FakeScheduler()
    service = ScheduledTaskService(
        scheduler=scheduler,
        runner_callable=lambda task_id: None,
        session_file_registry=env.registry,
    )
    request = CreateTaskRequest(
        task_name="daily compare",
        cron_expression="0 9 * * *",
        payload=ChatReplayPayload(
            version=2,
            user_input="比较这些文件",
            ext_info={
                "file_ids": [first.file_id, second.file_id],
                "session_id": SESSION,
            },
        ),
    )

    created = await service.create_task(request, user_name=OWNER)

    # Creation froze the session files into the task scope with fresh IDs.
    task_id = created.task_id
    stored_payload = created.payload.model_dump()
    frozen_ids = stored_payload["ext_info"]["file_ids"]
    assert len(frozen_ids) == 2
    assert set(frozen_ids).isdisjoint({first.file_id, second.file_id})
    assert "file_path" not in stored_payload["ext_info"]
    # The original session files still exist; frozen copies share their hash.
    task_files = env.registry.list_task_files(owner_id=OWNER, task_id=task_id)
    assert len(task_files) == 2
    assert [f.display_name for f in task_files] == ["a.csv", "b.csv"]
    assert {f.sha256 for f in task_files} == {first.sha256, second.sha256}
    assert {f.source_file_id for f in task_files} == {
        first.file_id,
        second.file_id,
    }
    # Deleting the session sources must not touch the frozen task inputs.
    for record in (first, second):
        assert env.registry.delete_file(
            owner_id=OWNER, session_id=SESSION, file_id=record.file_id
        )
    assert len(env.registry.list_task_files(owner_id=OWNER, task_id=task_id)) == 2

    # ------------------------------------------------------------------
    # Every replay copies the frozen task files into a fresh run session
    # and replays with the fresh session-scoped IDs (twice => two distinct
    # fresh sessions, identical content hashes).
    # ------------------------------------------------------------------
    captured_payloads = []

    async def fake_stream(dialogue):
        captured_payloads.append(
            {
                "conv_uid": dialogue.conv_uid,
                "ext_info": dict(dialogue.ext_info or {}),
            }
        )
        yield 'data: {"type":"final","content":"ran"}'
        yield 'data: {"type":"done"}'

    monkeypatch.setattr(
        "dbgpt_app.openapi.api_v1.agentic_data_api._react_agent_stream",
        fake_stream,
    )
    runner = ChatReplayRunner(session_file_registry=env.registry)
    for _ in range(2):
        await runner.replay_chat_task(task_id)

    runs = ScheduledRunDao().list_by_task_id(task_id, limit=10, offset=0)
    assert len(runs) == 2
    assert {run["status"] for run in runs} == {"success"}
    assert len(captured_payloads) == 2

    fresh_id_sets = []
    for payload, run in zip(reversed(captured_payloads), runs):
        assert payload["conv_uid"] == run["output_conv_uid"]
        fresh_ids = payload["ext_info"]["file_ids"]
        fresh_id_sets.append(set(fresh_ids))
        # Fresh run IDs differ from both task-scoped and session-scoped IDs.
        assert set(fresh_ids).isdisjoint({first.file_id, second.file_id})
        assert set(fresh_ids).isdisjoint(set(frozen_ids))
        # The run session holds copies with identical content hashes.
        run_files = env.registry.list_files(
            owner_id=OWNER, session_id=payload["conv_uid"]
        )
        assert {f.file_id for f in run_files} == set(fresh_ids)
        expected_sha = {
            hashlib.sha256(content).hexdigest()
            for content in (CSV_BYTES, b"x,y\n3,4\n")
        }
        assert {f.sha256 for f in run_files} == expected_sha
    # Two runs never share file IDs (immutability is per-run, not per-task).
    assert fresh_id_sets[0].isdisjoint(fresh_id_sets[1])


# ---------------------------------------------------------------------------
# 9. Share redaction: public payloads only carry display-key snapshots
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_public_share_redacts_v2_input_files(env, monkeypatch):
    from dbgpt_app.openapi.api_v1 import agentic_data_api
    from dbgpt_app.openapi.api_v1.agentic_data_api import (
        _build_react_history_payload,
    )
    from dbgpt_app.openapi.api_v1.attachment_react_adapter import (
        build_input_files_v2,
        open_session_attachments,
    )
    from dbgpt_app.share.models import ShareLinkDao
    from dbgpt_serve.conversation.config import ServeConfig as ConversationConfig
    from dbgpt_serve.conversation.models.models import ServeDao

    record = _ingest(env)
    ctx = open_session_attachments(
        env.registry,
        owner_id=OWNER,
        session_id=SESSION,
        file_ids=(record.file_id,),
    )
    try:
        input_files = build_input_files_v2(ctx.manifests)
    finally:
        ctx.close()
    private_context = _build_react_history_payload(
        final_content="analysis answer",
        steps=[{"id": "s1", "status": "done"}],
        task_plan=[],
        generated_images=[],
        sub_agents=[],
        input_files=input_files,
    )
    # Sanity: the private payload really does carry the resolvable id.
    assert record.file_id in private_context

    share_dao = ShareLinkDao()
    state = {
        "history": [
            SimpleNamespace(role="human", context="分析这些文件", order=0),
            SimpleNamespace(role="view", context=private_context, order=1),
        ]
    }
    conversation_service = SimpleNamespace(
        dao=ServeDao(ConversationConfig()),
        get_history_messages=lambda request: state["history"],
    )
    # Seed the conversation row used by the share ownership check.
    with share_dao.session() as session:
        session.add(
            ChatHistoryEntity(
                conv_uid=SESSION,
                chat_mode="chat_react_agent",
                summary="分析这些文件",
                user_name=OWNER,
            )
        )
    monkeypatch.setattr(agentic_data_api, "_get_share_dao", lambda: share_dao)
    monkeypatch.setattr(
        agentic_data_api, "_get_conversation_service", lambda: conversation_service
    )

    # Owner creates a share link; a foreign user can only view the redacted
    # public form of it.
    created = await agentic_data_api.create_share_link(
        agentic_data_api.ShareCreateRequest(conv_uid=SESSION),
        UserRequest(user_id=OWNER),
    )
    assert created.success is True

    result = await agentic_data_api.get_share_conversation(created.data.token)
    public_context = result.data.messages[1]["context"]
    parsed = json.loads(public_context)
    assert parsed["version"] == 2
    public_files = parsed["input_files"]
    assert len(public_files) == 1
    entry = public_files[0]
    # Public shape: display_key + safe metadata — nothing resolvable.
    assert entry == {
        "display_key": "file-1",
        "name": "report.csv",
        "size": len(CSV_BYTES),
        "media_type": "text/csv",
        "kind": "table",
        "status": "ready",
        "ordinal": 0,
    }
    for marker in (
        record.file_id,
        record.storage_uri,
        record.sha256,
        str(env.work_root),
        "file_id",
        "storage_uri",
        "python_uploads",
        "owner_id",
    ):
        assert marker not in public_context
    # The redacted display key cannot resolve any private registry file.
    assert (
        env.registry.get_file(owner_id=OWNER, session_id=SESSION, file_id="file-1")
        is None
    )
    # Human message passes through untouched.
    assert result.data.messages[0]["context"] == "分析这些文件"
