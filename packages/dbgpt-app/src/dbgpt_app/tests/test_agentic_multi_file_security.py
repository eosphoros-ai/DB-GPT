"""Adversarial contracts for the multi-file agentic flow.

Composes the real seams (in-memory SQLite + fake storage + bounded
inspector doubles + fake agent stream) against hostile inputs:

- cross-owner, wrong-session, forged-task and task-in-session references
  all surface the same non-enumerating 404;
- ``file_ids``/``file_path`` conflict, duplicate and oversized selections
  are rejected deterministically;
- symlink swaps, oversized uploads and slow parsers cannot escape bounds;
- the owner quota is race-proof;
- storage/DAO/copy/scheduler failures compensate with no residue;
- a cancelled request frees every materialized file exactly once;
- per-turn materialized paths may surface in prompts and history (the
  model analyzes files with code_interpreter) but are masked at the
  public share boundary, while storage URIs and hashes never reach
  prompts, history payloads, public shares or log records.
"""

import hashlib
import io
import json
import threading
import time
from pathlib import Path
from types import SimpleNamespace
from typing import List

import pytest
from sqlalchemy.pool import StaticPool

from dbgpt.storage.metadata import db
from dbgpt_app.openapi.api_view_model import ConversationVo
from dbgpt_serve.scheduled_task.models.scheduled_task_model import (  # noqa: F401
    ScheduledTaskEntity,
)
from dbgpt_serve.session_file.config import ServeConfig
from dbgpt_serve.session_file.domain import SessionFileStatus
from dbgpt_serve.session_file.inspector import (
    InspectionLimits,
    SessionFileInspector,
)
from dbgpt_serve.session_file.models.dao import SessionFileDao
from dbgpt_serve.session_file.models.models import SessionFileEntity
from dbgpt_serve.session_file.registry import (
    SessionFileRegistry,
    SessionFileRegistryError,
)
from dbgpt_serve.utils.auth import UserRequest

OWNER = "alice"
OTHER_OWNER = "bob"
SESSION = "sess-sec-1"
OTHER_SESSION = "sess-sec-2"

CSV_BYTES = b"region,sales\nwest,1\neast,2\nsouth,3\nnorth,4\n"
TXT_BYTES = b"hello security"


class _FakeStorageClient:
    """In-memory FileStorageClient seam double with failure knobs."""

    def __init__(self):
        self.saved = {}
        self.fail_next_saves = 0
        self.fail_all_saves = False

    def save_file(
        self,
        bucket,
        file_name,
        file_data,
        storage_type=None,
        custom_metadata=None,
        file_id=None,
    ):
        if self.fail_all_saves:
            raise RuntimeError("storage backend exploded")
        if self.fail_next_saves > 0:
            self.fail_next_saves -= 1
            raise RuntimeError("storage backend exploded")
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
    """Instant, deterministic inspection double (kind by suffix)."""

    _KINDS = {
        ".csv": ("table", "text/csv"),
        ".txt": ("document", "text/plain"),
    }

    async def inspect_async(self, path, declared_media_type=None):
        suffix = Path(path).suffix.lower()
        kind, media_type = self._KINDS.get(
            suffix, ("binary", "application/octet-stream")
        )
        return SimpleNamespace(
            kind=kind,
            media_type=media_type,
            status=SessionFileStatus.READY,
            preview={"columns": ["c"], "rows": [[1]]} if kind == "table" else {},
            truncated=False,
            error_code=None,
            error_message=None,
        )


@pytest.fixture()
def env(tmp_path):
    """Hostile-input test environment over in-memory SQLite."""
    db.init_db(
        "sqlite:///:memory:",
        engine_args={
            "connect_args": {"check_same_thread": False},
            "poolclass": StaticPool,
        },
    )
    db.create_all()
    storage = _FakeStorageClient()
    registry = _make_registry(tmp_path, storage)
    return SimpleNamespace(
        registry=registry,
        storage=storage,
        tmp_path=tmp_path,
        work_root=tmp_path / "work",
    )


def _make_registry(tmp_path, storage, inspector=None, **config_overrides):
    return SessionFileRegistry(
        storage_client=storage,
        dao=SessionFileDao(),
        inspector=inspector or _FakeBoundedInspector(),
        config=ServeConfig(**config_overrides),
        work_root=tmp_path / "work",
    )


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


def _all_rows():
    with SessionFileDao().session(commit=False) as session:
        return session.query(SessionFileEntity).all()


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


def _open(env, owner, session, ids):
    from dbgpt_app.openapi.api_v1.attachment_react_adapter import (
        open_session_attachments,
    )

    return open_session_attachments(
        env.registry, owner_id=owner, session_id=session, file_ids=tuple(ids)
    )


# ---------------------------------------------------------------------------
# Ownership and scope: one indistinguishable 404 for every failure
# ---------------------------------------------------------------------------


def _assert_not_found(error):
    assert error.status_code == 404
    assert error.code == "SESSION_FILE_NOT_FOUND"
    assert error.message == "File not found."


def test_cross_owner_id_is_indistinguishable_from_missing(env):
    from dbgpt_app.openapi.api_v1.attachment_react_adapter import (
        AttachmentInputError,
    )

    foreign = _ingest(env, owner=OTHER_OWNER)
    for file_id in (foreign.file_id, "sf_never_existed"):
        with pytest.raises(AttachmentInputError) as exc_info:
            _open(env, OWNER, SESSION, [file_id])
        _assert_not_found(exc_info.value)


def test_wrong_session_scope_yields_identical_404(env):
    from dbgpt_app.openapi.api_v1.attachment_react_adapter import (
        AttachmentInputError,
    )

    record = _ingest(env, session=OTHER_SESSION)
    with pytest.raises(AttachmentInputError) as exc_info:
        _open(env, OWNER, SESSION, [record.file_id])
    _assert_not_found(exc_info.value)


def test_task_scoped_id_cannot_be_replayed_as_session_file(env):
    """A forged reference to a task-scoped id inside a chat session is the
    same generic 404 as a missing id — ids never leak the owning scope."""
    from dbgpt_app.openapi.api_v1.attachment_react_adapter import (
        AttachmentInputError,
    )

    source = _ingest(env)
    copies = env.registry.copy_session_to_task(
        owner_id=OWNER,
        session_id=SESSION,
        file_ids=[source.file_id],
        task_id="task-forged-1",
    )
    with pytest.raises(AttachmentInputError) as exc_info:
        _open(env, OWNER, SESSION, [copies[0].file_id])
    _assert_not_found(exc_info.value)


# ---------------------------------------------------------------------------
# Input normalization: conflict / duplicates / overflow
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_file_ids_and_file_path_conflict_rejected_400(env, monkeypatch):
    from fastapi import HTTPException

    from dbgpt_app.openapi.api_v1 import agentic_data_api

    _bind_registry(monkeypatch, env.registry)
    with pytest.raises(HTTPException) as exc_info:
        await agentic_data_api.chat_react_agent(
            _dialogue({"file_ids": ["sf_a"], "file_path": "/legacy/a.csv"}),
            UserRequest(user_id=OWNER),
        )
    assert exc_info.value.status_code == 400
    assert "file_ids" in str(exc_info.value.detail)
    assert "file_path" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_task_creation_with_conflicting_file_inputs_fails(env):
    from dbgpt_serve.scheduled_task.api.schemas import (
        ChatReplayPayload,
        CreateTaskRequest,
    )
    from dbgpt_serve.scheduled_task.service.service import ScheduledTaskService

    service = ScheduledTaskService(session_file_registry=env.registry)
    request = CreateTaskRequest(
        task_name="conflict",
        cron_expression="0 9 * * *",
        payload=ChatReplayPayload(
            version=2,
            user_input="q",
            ext_info={
                "file_ids": ["sf_a"],
                "file_path": "/legacy/a.csv",
                "session_id": SESSION,
            },
        ),
    )
    with pytest.raises(ValueError, match="CONFLICTING_FILE_INPUTS"):
        await service.create_task(request, user_name=OWNER)
    assert _all_rows() == []


@pytest.mark.asyncio
async def test_duplicate_file_ids_are_deduplicated_before_resolution(env):
    from dbgpt_app.openapi.api_v1.attachment_react_adapter import (
        prepare_react_attachments,
    )

    first = _ingest(env, name="a.csv")
    second = _ingest(env, name="b.csv", content=b"x,y\n3,4\n")

    ctx = await prepare_react_attachments(
        _dialogue({"file_ids": [first.file_id, second.file_id, first.file_id]}),
        owner_id=OWNER,
        registry=env.registry,
    )
    try:
        assert [m.file_id for m in ctx.manifests] == [first.file_id, second.file_id]
    finally:
        ctx.close()


@pytest.mark.asyncio
async def test_file_count_overflow_rejected_at_chat(env, monkeypatch):
    from fastapi import HTTPException

    from dbgpt_app.openapi.api_v1 import agentic_data_api

    _bind_registry(monkeypatch, env.registry)
    overflowing = [f"sf_{index}" for index in range(21)]
    with pytest.raises(HTTPException) as exc_info:
        await agentic_data_api.chat_react_agent(
            _dialogue({"file_ids": overflowing}),
            UserRequest(user_id=OWNER),
        )
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_file_count_overflow_rejected_at_task_creation(env):
    from dbgpt_serve.scheduled_task.api.schemas import (
        ChatReplayPayload,
        CreateTaskRequest,
    )
    from dbgpt_serve.scheduled_task.service.service import ScheduledTaskService

    service = ScheduledTaskService(session_file_registry=env.registry)
    request = CreateTaskRequest(
        task_name="overflow",
        cron_expression="0 9 * * *",
        payload=ChatReplayPayload(
            version=2,
            user_input="q",
            ext_info={
                "file_ids": [f"sf_{index}" for index in range(21)],
                "session_id": SESSION,
            },
        ),
    )
    with pytest.raises(ValueError, match="TOO_MANY_FILES"):
        await service.create_task(request, user_name=OWNER)
    assert _all_rows() == []


# ---------------------------------------------------------------------------
# Forged task ids: creation freeze and replay supply chains
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_task_with_foreign_session_files_fails_closed(env):
    """Bob cannot freeze Alice's session files into his scheduled task."""
    from dbgpt_serve.scheduled_task.api.schemas import (
        ChatReplayPayload,
        CreateTaskRequest,
    )
    from dbgpt_serve.scheduled_task.dao.task_dao import ScheduledTaskDao
    from dbgpt_serve.scheduled_task.service.service import ScheduledTaskService

    record = _ingest(env, owner=OWNER)
    service = ScheduledTaskService(session_file_registry=env.registry)
    request = CreateTaskRequest(
        task_name="forged",
        cron_expression="0 9 * * *",
        payload=ChatReplayPayload(
            version=2,
            user_input="q",
            ext_info={
                "file_ids": [record.file_id],
                "session_id": SESSION,
            },
        ),
    )
    with pytest.raises(ValueError):
        await service.create_task(request, user_name=OTHER_OWNER)
    # Neither a task row nor any frozen file was persisted.
    assert ScheduledTaskDao().get_list({}) == []
    assert {row.file_id for row in _all_rows()} == {record.file_id}


def test_replay_never_reads_files_from_a_forged_task_scope(env):
    """`copy_task_to_session` for a task id owned by someone else fails
    closed instead of copying foreign content into the run session."""
    source = _ingest(env, owner=OWNER)
    copies = env.registry.copy_session_to_task(
        owner_id=OWNER,
        session_id=SESSION,
        file_ids=[source.file_id],
        task_id="task-real-owner",
    )
    assert copies

    with pytest.raises(SessionFileRegistryError) as exc_info:
        env.registry.copy_task_to_session(
            owner_id=OTHER_OWNER, task_id="task-real-owner", session_id="run-x"
        )
    assert exc_info.value.code == "SESSION_FILE_NOT_FOUND"
    assert env.registry.list_files(owner_id=OTHER_OWNER, session_id="run-x") == []


# ---------------------------------------------------------------------------
# Symlink swap: the materialization path refuses planted escapes
# ---------------------------------------------------------------------------


def test_symlinked_owner_directory_is_rejected_before_any_write(env):
    """A pre-planted symlink at ``work_root/<owner>`` escaping the work root
    must fail the upload closed — no row, no blob, no bytes outside."""
    outside = env.tmp_path / "escape"
    outside.mkdir()
    planted = outside / "stolen.csv"
    planted.write_bytes(CSV_BYTES)
    env.work_root.mkdir(parents=True)
    try:
        (env.work_root / OWNER).symlink_to(outside, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"symlinks unavailable here: {exc}")

    with pytest.raises(SessionFileRegistryError) as exc_info:
        _ingest(env)

    assert exc_info.value.code == "MATERIALIZE_FAILED"
    assert _all_rows() == []
    assert env.storage.saved == {}
    # The escape directory never received a run directory or copied bytes.
    assert list(outside.rglob("run_*")) == []
    assert planted.read_bytes() == CSV_BYTES


# ---------------------------------------------------------------------------
# Adversarial display names: quotes/newlines survive as inert metadata
# ---------------------------------------------------------------------------


def test_quote_and_newline_filename_stays_inert_throughout(env):
    hostile = '季度"sales"\nreport\t(1).csv'
    record = _ingest(env, name=hostile)

    # Display name round-trips byte-identically through DAO read.
    assert record.display_name == hostile
    # The materialized local path uses a random on-disk name — the hostile
    # display name never enters the filesystem layout.
    ctx = _open(env, OWNER, SESSION, [record.file_id])
    try:
        local_name = Path(ctx.local_paths[record.file_id]).name
        assert hostile not in local_name
        assert '"' not in local_name and "\n" not in local_name
        # files_json maps ids to paths; the display name only appears in the
        # prompt manifest as quoted JSON-safe text — never as an unescaped
        # control char.
        prompt = ctx.prompt
        assert "季度" in prompt
        assert "\n" not in prompt.split(f"[{record.file_id}]")[1].split("\n")[
            0
        ].replace(hostile.replace("\n", ""), "")
        mapping = json.loads(Path(ctx.files_json_path).read_text(encoding="utf-8"))
        assert list(mapping) == [record.file_id]
    finally:
        ctx.close()

    # History snapshots serialize without breaking JSON consumers.
    from dbgpt_app.openapi.api_v1.attachment_react_adapter import (
        build_input_files_v2,
    )

    snapshot = build_input_files_v2(tuple(m for m in [_record_manifest(record)]))
    encoded = json.dumps(snapshot, ensure_ascii=False)
    decoded = json.loads(encoded)
    assert decoded[0]["name"] == hostile


def _record_manifest(record):
    from dbgpt_serve.session_file.domain import SessionFileManifest

    return SessionFileManifest(
        file_id=record.file_id,
        name=record.display_name,
        size=record.size_bytes,
        media_type=record.media_type,
        kind=record.file_kind,
        status=record.status,
        ordinal=record.ordinal,
    )


# ---------------------------------------------------------------------------
# Parser bounds: timeouts and oversized inputs fail safe
# ---------------------------------------------------------------------------


def test_slow_parser_hits_timeout_and_file_stays_usable(env):
    """A parser exceeding its wall-clock budget yields ``preview_failed``
    (soft warning) — the stored source remains analyzable and the chat turn
    proceeds instead of hanging or being rejected wholesale."""
    real = SessionFileInspector(limits=InspectionLimits(timeout_seconds=0.05))
    times = {"calls": 0}

    def slow_parser(path, limits):
        times["calls"] += 1
        time.sleep(0.5)
        return ({"columns": ["x"], "rows": [["1"]]}, False)

    slow = SessionFileInspector(
        limits=InspectionLimits(timeout_seconds=0.05),
        parsers={".csv": slow_parser},
        optional_import=real._optional_import,
    )
    registry = _make_registry(env.tmp_path, env.storage, inspector=slow)
    env.registry = registry

    record = _ingest(env)
    assert record.status == SessionFileStatus.PREVIEW_FAILED
    assert record.error_code == "INSPECTION_TIMEOUT"
    assert times["calls"] >= 1

    # preview_failed still passes the adapter accept-list.
    ctx = _open(env, OWNER, SESSION, [record.file_id])
    ctx.close()


def test_oversized_upload_is_rejected_mid_stream_without_persistence(env):
    env.registry = _make_registry(
        env.tmp_path, env.storage, max_file_bytes=len(CSV_BYTES) // 2
    )
    with pytest.raises(SessionFileRegistryError) as exc_info:
        _ingest(env)
    assert exc_info.value.code == "FILE_TOO_LARGE"
    assert _all_rows() == []
    assert env.storage.saved == {}


# ---------------------------------------------------------------------------
# Quota race: concurrent uploads cannot both pass the owner limit
# ---------------------------------------------------------------------------


def test_concurrent_uploads_never_overrun_owner_quota(env, tmp_path):
    quota = len(CSV_BYTES) + 8
    env.registry = _make_registry(env.tmp_path, env.storage, max_owner_bytes=quota)

    barrier = threading.Barrier(2)
    results: List[str] = []
    errors: List[SessionFileRegistryError] = []
    results_lock = threading.Lock()

    def worker(name):
        barrier.wait(timeout=5)
        try:
            record = env.registry.ingest(
                owner_id=OWNER,
                session_id=SESSION,
                display_name=name,
                media_type="text/csv",
                stream=io.BytesIO(CSV_BYTES),
                size_bytes=len(CSV_BYTES),
            )
            with results_lock:
                results.append(record.file_id)
        except SessionFileRegistryError as error:
            with results_lock:
                errors.append(error)

    threads = [
        threading.Thread(target=worker, args=(f"race-{index}.csv",))
        for index in range(2)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    assert not any(thread.is_alive() for thread in threads)

    # At most one upload can pass; the quota actually bound the loser.
    assert len(results) == 1
    assert len(errors) == 1
    assert errors[0].code == "QUOTA_EXCEEDED"
    assert env.registry.dao.total_owner_size_bytes(OWNER) <= quota


# ---------------------------------------------------------------------------
# Failure compensation: storage / DAO / copy / scheduler failures leave
# no residue
# ---------------------------------------------------------------------------


def test_dao_failure_after_blob_save_compensates_blob(env, monkeypatch):
    """A DAO failure after the blob exists must delete the blob and leave
    no row — the two stores never disagree."""
    source = _ingest(env)
    baseline = set(env.storage.saved)

    monkeypatch.setattr(
        env.registry.dao,
        "create",
        lambda request: (_ for _ in ()).throw(RuntimeError("dao exploded")),
    )
    with pytest.raises(RuntimeError):
        _ingest(env, name="second.csv")

    assert set(env.storage.saved) == baseline
    assert {row.file_id for row in _all_rows()} == {source.file_id}


def test_copy_failure_cleans_up_already_copied_blobs(env, tmp_path):
    """A failure on the second copy must roll back the first copy's row and
    blob — no partial task scope survives."""
    first = _ingest(env, name="a.csv")
    second = _ingest(env, name="b.csv", content=b"x,y\n3,4\n")
    baseline = dict(env.storage.saved)
    env.storage.fail_next_saves = 1

    with pytest.raises(RuntimeError):
        env.registry.copy_session_to_task(
            owner_id=OWNER,
            session_id=SESSION,
            file_ids=[first.file_id, second.file_id],
            task_id="task-rollback",
        )

    assert env.registry.list_task_files(owner_id=OWNER, task_id="task-rollback") == []
    # Only the two original blobs remain.
    assert dict(env.storage.saved) == baseline
    # Source rows are untouched.
    assert {row.file_id for row in _all_rows()} == {first.file_id, second.file_id}


@pytest.mark.asyncio
async def test_scheduler_failure_compensates_frozen_task_files(env):
    """If the scheduler write fails after freezing, the task row and all
    frozen files are rolled back."""
    from dbgpt_serve.scheduled_task.api.schemas import (
        ChatReplayPayload,
        CreateTaskRequest,
    )
    from dbgpt_serve.scheduled_task.dao.task_dao import ScheduledTaskDao
    from dbgpt_serve.scheduled_task.service.service import ScheduledTaskService

    class _FailingScheduler:
        async def add_job(self, **kwargs):
            raise RuntimeError("apscheduler exploded")

    first = _ingest(env, name="a.csv")
    baseline_blob_count = len(env.storage.saved)
    service = ScheduledTaskService(
        scheduler=_FailingScheduler(),
        session_file_registry=env.registry,
    )
    request = CreateTaskRequest(
        task_name="rollback",
        cron_expression="0 9 * * *",
        payload=ChatReplayPayload(
            version=2,
            user_input="q",
            ext_info={"file_ids": [first.file_id], "session_id": SESSION},
        ),
    )

    with pytest.raises(RuntimeError):
        await service.create_task(request, user_name=OWNER)

    assert ScheduledTaskDao().get_list({}) == []
    assert {row.file_id for row in _all_rows()} == {first.file_id}
    # Frozen task blobs were compensated too.
    assert len(env.storage.saved) == baseline_blob_count


# ---------------------------------------------------------------------------
# Cancellation: closing the stream mid-turn frees every materialization
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cancelled_stream_closes_attachments_exactly_once(env, monkeypatch):
    """A client cancelling mid-stream (async generator close) must close
    the attachment context exactly once and remove the run directories."""
    from dbgpt_app.openapi.api_v1 import agentic_data_api

    record = _ingest(env)
    ctx = _open(env, OWNER, SESSION, [record.file_id])
    paths = dict(ctx.local_paths)
    files_json = ctx.files_json_path
    for path in list(paths.values()) + [files_json]:
        assert Path(path).exists()

    async def fake_inner(dialogue, tool_mode, attachment_ctx):
        yield 'data: {"type":"chunk","content":"first"}\n\n'
        yield 'data: {"type":"final","content":"never reached"}\n\n'

    monkeypatch.setattr(agentic_data_api, "_react_agent_stream_inner", fake_inner)

    stream = agentic_data_api._react_agent_stream(
        _dialogue({"file_ids": [record.file_id]}), "full", ctx
    )
    first = await stream.__anext__()
    assert "first" in first
    await stream.aclose()

    for path in list(paths.values()) + [files_json]:
        assert not Path(path).exists()
    assert not list(env.work_root.rglob("run_*"))

    # Closing an already-closed stream again is a harmless no-op.
    await stream.aclose()
    for path in list(paths.values()) + [files_json]:
        assert not Path(path).exists()


# ---------------------------------------------------------------------------
# Path hygiene: prompts/history may carry per-turn paths; the share boundary
# masks every server path; storage URIs/hashes never leave the registry
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_materialized_paths_stay_internal_until_share_boundary(
    env, monkeypatch, caplog
):
    """Per-turn materialized paths legitimately surface in prompts and
    history payloads (the model analyzes files with code_interpreter, and
    tracebacks carry paths), but storage URIs/hashes never do — and the
    public share payload masks every server path prefix at the boundary.
    """
    import logging

    from dbgpt_app.openapi.api_v1.agentic_data_api import (
        _build_react_history_payload,
        scrub_react_history_for_share,
    )
    from dbgpt_app.openapi.api_v1.attachment_react_adapter import (
        build_file_context,
        build_input_files_v2,
    )

    _bind_registry(monkeypatch, env.registry)
    record = _ingest(env, name="confidential.csv")
    with caplog.at_level(logging.DEBUG):
        ctx = _open(env, OWNER, SESSION, [record.file_id])
        try:
            prompt = build_file_context(ctx, None)
            # A real turn: tool observations (e.g. tracebacks) carry the
            # materialized path into history steps.
            steps = [
                {
                    "id": "s1",
                    "status": "done",
                    "outputs": [
                        {
                            "output_type": "text",
                            "content": (f"FileNotFoundError: {ctx.primary_local_path}"),
                        }
                    ],
                }
            ]
            raw_history = _build_react_history_payload(
                final_content=f"analyzed {ctx.primary_local_path}",
                steps=steps,
                task_plan=[],
                generated_images=[],
                sub_agents=[],
                input_files=build_input_files_v2(ctx.manifests),
            )
        finally:
            ctx.close()
        scrubbed_share = scrub_react_history_for_share(raw_history)

    # Supply side: prompts and history may carry the per-turn materialized
    # path, but never storage internals.
    for surface, content in {"prompt": prompt, "history": raw_history}.items():
        for marker in (record.storage_uri, record.sha256):
            assert marker not in content, (
                f"{marker!r} leaked into {surface}: {content[:300]}"
            )
    assert ctx.primary_local_path in prompt
    assert ctx.primary_local_path in raw_history
    assert record.file_id in prompt
    assert "confidential.csv" in prompt

    # Trust boundary: the public share payload masks every server path.
    share_forbidden = (
        record.storage_uri,
        record.sha256,
        str(env.work_root),
        str(env.tmp_path),
        ctx.primary_local_path,
        ctx.files_json_path,
        "python_uploads",
    )
    for marker in share_forbidden:
        assert marker not in scrubbed_share, (
            f"{marker!r} leaked into share: {scrubbed_share[:300]}"
        )
    assert "<server-path>" in scrubbed_share

    # Logs stay free of paths and storage internals.
    for marker in (record.storage_uri, record.sha256, ctx.primary_local_path):
        assert marker not in caplog.text


def test_share_scrub_masks_traceback_paths_in_steps(env, monkeypatch):
    """Regression: tool tracebacks embed absolute paths into history steps;
    the share boundary must mask them (work root + home prefixes)."""
    from dbgpt_app.openapi.api_v1.agentic_data_api import (
        _build_react_history_payload,
        scrub_react_history_for_share,
    )

    _bind_registry(monkeypatch, env.registry)
    monkeypatch.setattr(
        "dbgpt.configs.model_config.PILOT_PATH", str(env.tmp_path / "pilot")
    )
    record = _ingest(env)
    ctx = _open(env, OWNER, SESSION, [record.file_id])
    try:
        materialized = ctx.primary_local_path
        traceback_text = (
            "Traceback (most recent call last):\n"
            f'  File "{env.tmp_path}/pilot/tmp/conv/_run.py", line 12\n'
            f"FileNotFoundError: [Errno 2] No such file: '{materialized}'"
        )
        raw_history = _build_react_history_payload(
            final_content=f"read {materialized} failed",
            steps=[
                {
                    "id": "s1",
                    "status": "failed",
                    "outputs": [{"output_type": "text", "content": traceback_text}],
                }
            ],
            task_plan=[],
            generated_images=[],
            sub_agents=[],
            input_files=[],
        )
    finally:
        ctx.close()

    scrubbed = scrub_react_history_for_share(raw_history)

    assert materialized in raw_history  # supply side keeps full fidelity
    assert materialized not in scrubbed
    assert str(env.tmp_path) not in scrubbed
    assert "<server-path>" in scrubbed
    # Structured step content survives scrubbing intact apart from masking.
    parsed = json.loads(scrubbed)
    assert parsed["steps"][0]["status"] == "failed"
    assert "Traceback" in parsed["steps"][0]["outputs"][0]["content"]


def test_history_payload_surfaces_only_public_fields_in_json(env):
    """Every snapshot field set is exactly the public allowlist — even a
    hand-poisoned manifest cannot smuggle internals into history."""
    from dbgpt_app.openapi.api_v1.agentic_data_api import (
        _build_react_history_payload,
    )
    from dbgpt_app.openapi.api_v1.attachment_react_adapter import (
        build_input_files_v2,
    )

    record = _ingest(env)
    poisoned = json.loads(record.storage_uri and "{}" or "{}")
    poisoned["file_id"] = record.file_id
    poisoned["name"] = "a.csv"
    poisoned["size"] = 1
    poisoned["media_type"] = "text/csv"
    poisoned["kind"] = "table"
    poisoned["status"] = "ready"
    poisoned["ordinal"] = 0

    manifests = [_record_manifest(record)]
    snapshot = build_input_files_v2(manifests)
    raw_history = _build_react_history_payload(
        final_content="done",
        steps=[],
        task_plan=[],
        generated_images=[],
        sub_agents=[],
        input_files=snapshot,
    )
    payload = json.loads(raw_history)
    assert set(payload["input_files"][0]) == {
        "file_id",
        "name",
        "size",
        "media_type",
        "kind",
        "status",
        "ordinal",
    }
    assert hashlib.sha256(CSV_BYTES).hexdigest() not in raw_history
