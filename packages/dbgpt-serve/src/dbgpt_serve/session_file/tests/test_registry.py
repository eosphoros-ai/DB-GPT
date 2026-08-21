"""Contract tests for the session file registry storage orchestration."""

import hashlib
import importlib
import io
import json
import os
import stat
import threading
import uuid
from pathlib import Path
from types import SimpleNamespace
from typing import Callable, Dict, List, Optional, Tuple

import pytest
from sqlalchemy.pool import NullPool, StaticPool

from dbgpt.storage.metadata import db
from dbgpt_serve.session_file.config import ServeConfig
from dbgpt_serve.session_file.domain import FileScope, SessionFileStatus
from dbgpt_serve.session_file.inspector import SessionFileInspector
from dbgpt_serve.session_file.models.dao import SessionFileDao
from dbgpt_serve.session_file.models.models import SessionFileEntity  # noqa: F401
from dbgpt_serve.session_file.registry import (
    OwnerQuotaLocker,
    SessionFileRegistry,
    SessionFileRegistryError,
)

OWNER = "alice"
OTHER_OWNER = "bob"
SESSION = "sess-1"
OTHER_SESSION = "sess-2"
CSV_CONTENT = b"colA,colB\n1,2\n"


class _StrictChunkStream:
    """Binary stream double that forbids unbounded reads.

    Any ``read()`` without an explicit positive size is a contract violation:
    the registry must never pull an entire upload into memory.
    """

    def __init__(self, payload: bytes):
        self._buffer = io.BytesIO(payload)
        self.max_read_size = 0
        self.unbounded_reads = 0

    def read(self, size=-1):
        if size is None or size < 0:
            self.unbounded_reads += 1
            raise AssertionError("registry performed an unbounded read()")
        self.max_read_size = max(self.max_read_size, size)
        return self._buffer.read(size)

    def seek(self, offset, whence=0):
        return self._buffer.seek(offset, whence)

    def tell(self):
        return self._buffer.tell()

    def readable(self) -> bool:
        return True

    def close(self):
        self._buffer.close()


class _FakeStorageClient:
    """In-memory FileStorageClient seam double with strict chunked reads."""

    def __init__(self, chunk_size: int = 8):
        self._chunk_size = chunk_size
        self.saved: Dict[str, bytes] = {}
        self.save_calls = 0
        self.deleted_uris: List[str] = []
        self.fail_save: Optional[Exception] = None
        self.save_hook: Optional[Callable[[], None]] = None

    def save_file(
        self,
        bucket,
        file_name,
        file_data,
        storage_type=None,
        custom_metadata=None,
        file_id=None,
    ):
        self.save_calls += 1
        if self.fail_save is not None:
            raise self.fail_save
        if self.save_hook is not None:
            self.save_hook()
        file_id = file_id or uuid.uuid4().hex
        chunks: List[bytes] = []
        while chunk := file_data.read(self._chunk_size):
            chunks.append(chunk)
        uri = f"dbgpt-fs://local/{bucket}/{file_id}"
        self.saved[uri] = b"".join(chunks)
        return uri

    def get_file(self, uri):
        if uri not in self.saved:
            raise FileNotFoundError(f"No such blob: {uri}")
        metadata = SimpleNamespace(
            file_id=uri.rsplit("/", 1)[-1],
            file_size=len(self.saved[uri]),
            file_hash="-1",
            uri=uri,
        )
        return io.BytesIO(self.saved[uri]), metadata

    def delete_file(self, uri):
        self.deleted_uris.append(uri)
        return self.saved.pop(uri, None) is not None

    def get_file_metadata_by_uri(self, uri):
        if uri not in self.saved:
            return None
        return SimpleNamespace(
            file_id=uri.rsplit("/", 1)[-1],
            file_size=len(self.saved[uri]),
            uri=uri,
        )


def _config(**overrides) -> ServeConfig:
    values = dict(
        max_files_per_upload=5,
        max_file_bytes=1024,
        max_upload_bytes=4096,
        max_owner_bytes=8 * 1024,
        upload_concurrency_advice=2,
        upload_chunk_bytes=8,
        upload_spool_bytes=64,
        download_chunk_bytes=8,
        max_file_name_bytes=64,
    )
    values.update(overrides)
    return ServeConfig(**values)


def _trusted_inspector() -> SessionFileInspector:
    """Inspector whose built-in parsers stay on the trusted in-thread path."""
    base = SessionFileInspector()
    return SessionFileInspector(
        optional_import=importlib.import_module,
        parsers={
            ".csv": base._parse_delimited,
            ".tsv": base._parse_delimited,
            ".json": base._parse_json,
            ".jsonl": base._parse_json,
            ".txt": base._parse_text,
            ".md": base._parse_text,
        },
    )


@pytest.fixture(autouse=True)
def _database():
    db.init_db(
        "sqlite:///:memory:",
        engine_args={
            "connect_args": {"check_same_thread": False},
            "poolclass": StaticPool,
        },
    )
    db.create_all()
    yield


def _make_registry(
    work_root: Path,
    storage: Optional[_FakeStorageClient] = None,
    config: Optional[ServeConfig] = None,
    inspector: Optional[SessionFileInspector] = None,
) -> SessionFileRegistry:
    return SessionFileRegistry(
        storage_client=storage or _FakeStorageClient(),
        dao=SessionFileDao(),
        inspector=inspector or _trusted_inspector(),
        config=config or _config(),
        work_root=work_root,
    )


@pytest.fixture()
def storage() -> _FakeStorageClient:
    return _FakeStorageClient()


@pytest.fixture()
def registry(tmp_path, storage) -> SessionFileRegistry:
    return _make_registry(tmp_path / "work", storage=storage)


def _stream(content: bytes) -> _StrictChunkStream:
    return _StrictChunkStream(content)


def _ingest(
    registry: SessionFileRegistry,
    name: str = "report.csv",
    content: bytes = CSV_CONTENT,
    owner: str = OWNER,
    session: str = SESSION,
    media: str = "text/csv",
    size_bytes: Optional[int] = None,
) -> Tuple[object, _StrictChunkStream]:
    stream = _stream(content)
    record = registry.ingest(
        owner_id=owner,
        session_id=session,
        display_name=name,
        media_type=media,
        stream=stream,
        size_bytes=len(content) if size_bytes is None else size_bytes,
    )
    return record, stream


def _dao_rows(dao: SessionFileDao, scope: FileScope):
    return dao.list_by_scope(scope)


class TestIngestStreaming:
    """Ingest must stream strictly in configured chunks, never in full."""

    def test_stream_reads_are_bounded_by_configured_chunk(self, registry):
        record, stream = _ingest(registry)

        assert stream.unbounded_reads == 0
        assert 0 < stream.max_read_size <= registry.config.upload_chunk_bytes
        assert stream.max_read_size > 0
        assert record.size_bytes == len(CSV_CONTENT)
        assert record.sha256 == hashlib.sha256(CSV_CONTENT).hexdigest()

    def test_blob_bytes_and_row_persisted_together(self, registry, storage):
        record, _ = _ingest(registry)

        assert storage.saved, "blob must be stored through the storage client"
        assert len(storage.saved) == 1
        uri, content = next(iter(storage.saved.items()))
        assert uri == record.storage_uri
        assert content == CSV_CONTENT
        persisted = registry.get_file(
            owner_id=OWNER, session_id=SESSION, file_id=record.file_id
        )
        assert persisted is not None
        assert persisted.display_name == "report.csv"

    def test_random_storage_key_is_decoupled_from_display_name(self, registry):
        record, _ = _ingest(registry)

        blob_name = record.storage_uri.rsplit("/", 1)[-1]
        assert record.file_id.startswith("sf_")
        assert blob_name == record.file_id
        assert "report.csv" not in blob_name

    def test_same_display_name_never_overwrites_existing_file(self, registry, storage):
        first, _ = _ingest(registry)
        second, _ = _ingest(registry)

        assert first.file_id != second.file_id
        assert first.ordinal == 0
        assert second.ordinal == 1
        assert len(storage.saved) == 2
        scope = FileScope(OWNER, session_id=SESSION)
        assert len(_dao_rows(registry.dao, scope)) == 2

    def test_oversize_upload_rejected_mid_stream_without_persistence(
        self, registry, storage
    ):
        payload = b"x" * (registry.config.max_file_bytes + 1)

        with pytest.raises(SessionFileRegistryError) as excinfo:
            _ingest(registry, content=payload)

        assert excinfo.value.code == "FILE_TOO_LARGE"
        assert storage.saved == {}
        assert registry.list_files(owner_id=OWNER, session_id=SESSION) == []

    def test_declared_size_mismatch_rejected_without_persistence(
        self, registry, storage
    ):
        with pytest.raises(SessionFileRegistryError) as excinfo:
            _ingest(registry, size_bytes=len(CSV_CONTENT) - 1)
        assert excinfo.value.code == "SIZE_MISMATCH"
        with pytest.raises(SessionFileRegistryError) as excinfo:
            _ingest(registry, size_bytes=len(CSV_CONTENT) + 1)
        assert excinfo.value.code == "SIZE_MISMATCH"

        assert storage.saved == {}
        assert registry.list_files(owner_id=OWNER, session_id=SESSION) == []

    def test_blob_failure_leaves_no_dao_row(self, registry, storage):
        storage.fail_save = RuntimeError("backend unavailable")

        with pytest.raises(RuntimeError, match="backend unavailable"):
            _ingest(registry)

        assert registry.list_files(owner_id=OWNER, session_id=SESSION) == []

    def test_dao_failure_deletes_blob_and_propagates(
        self, registry, storage, monkeypatch
    ):
        def _boom(_request):
            raise ValueError("simulated dao failure")

        monkeypatch.setattr(registry.dao, "create", _boom)

        with pytest.raises(ValueError, match="simulated dao failure"):
            _ingest(registry)

        assert storage.saved == {}
        assert len(storage.deleted_uris) == 1
        assert registry.list_files(owner_id=OWNER, session_id=SESSION) == []


class TestIngestCompensation:
    """Any failure after the DAO row exists compensates row and blob."""

    def test_materialize_failure_compensates_row_and_blob(
        self, registry, storage, monkeypatch
    ):
        from contextlib import contextmanager

        @contextmanager
        def _failing_materialize(scope, source, suffix=""):
            raise SessionFileRegistryError(
                "MATERIALIZE_FAILED", "simulated materialize failure"
            )
            yield  # pragma: no cover

        monkeypatch.setattr(registry, "materialize_local_file", _failing_materialize)

        with pytest.raises(SessionFileRegistryError) as excinfo:
            _ingest(registry)

        assert excinfo.value.code == "MATERIALIZE_FAILED"
        assert registry.list_files(owner_id=OWNER, session_id=SESSION) == []
        assert storage.saved == {}
        assert len(storage.deleted_uris) == 1
        assert registry.dao.total_owner_size_bytes(OWNER) == 0

    def test_finalize_failure_compensates_row_and_blob(
        self, registry, storage, monkeypatch
    ):
        def _failing_update(*args, **kwargs):
            raise ValueError("simulated finalize failure")

        monkeypatch.setattr(registry.dao, "update_status", _failing_update)

        with pytest.raises(SessionFileRegistryError) as excinfo:
            _ingest(registry)

        assert excinfo.value.code == "FINALIZE_FAILED"
        assert registry.list_files(owner_id=OWNER, session_id=SESSION) == []
        assert storage.saved == {}
        assert len(storage.deleted_uris) == 1
        assert registry.dao.total_owner_size_bytes(OWNER) == 0


class TestIngestInspection:
    """Row starts INSPECTING, then bounded inspection drives final state."""

    def test_row_transitions_inspecting_to_ready(self, registry, monkeypatch):
        statuses: List[str] = []
        original_create = registry.dao.create
        original_update = registry.dao.update_status

        def _create_spy(request):
            statuses.append(f"create:{request['status']}")
            return original_create(request)

        def _update_spy(file_id, scope, status, **kwargs):
            statuses.append(f"update:{SessionFileStatus(status).value}")
            return original_update(file_id, scope, status, **kwargs)

        monkeypatch.setattr(registry.dao, "create", _create_spy)
        monkeypatch.setattr(registry.dao, "update_status", _update_spy)

        record, _ = _ingest(registry)

        assert statuses == [
            f"create:{SessionFileStatus.INSPECTING.value}",
            f"update:{SessionFileStatus.READY.value}",
        ]
        assert record.status == SessionFileStatus.READY

    def test_inspection_json_shape_is_exactly_preview_and_truncated(self, registry):
        record, _ = _ingest(registry)

        payload = json.loads(record.inspection_json)
        assert set(payload.keys()) == {"preview", "truncated"}
        assert isinstance(payload["preview"], dict)
        assert payload["preview"], "csv preview must contain parsed rows"
        assert payload["truncated"] is False

    def test_preview_failure_uses_safe_error_code_and_message(self, registry):
        record, _ = _ingest(
            registry, name="evil.exe", content=b"MZ\x90\x00", media=None
        )

        assert record.status == SessionFileStatus.PREVIEW_FAILED
        assert record.error_code == "UNSUPPORTED_TYPE"
        assert record.error_message == "The file type is not supported."
        assert record.media_type == "application/octet-stream"
        payload = json.loads(record.inspection_json)
        assert payload == {"preview": {}, "truncated": False}


class TestScopedAcl:
    """Session/task scopes and owners are hard isolation boundaries."""

    def test_list_is_ordered_and_scoped(self, registry):
        first, _ = _ingest(registry, name="a.csv")
        second, _ = _ingest(registry, name="b.csv")
        _ingest(registry, name="other.csv", session=OTHER_SESSION)

        records = registry.list_files(owner_id=OWNER, session_id=SESSION)

        assert [r.file_id for r in records] == [first.file_id, second.file_id]
        other = registry.list_files(owner_id=OWNER, session_id=OTHER_SESSION)
        assert len(other) == 1
        assert registry.list_files(owner_id=OTHER_OWNER, session_id=SESSION) == []

    def test_get_file_hides_other_owner_and_missing_ids(self, registry):
        record, _ = _ingest(registry)

        assert (
            registry.get_file(
                owner_id=OTHER_OWNER, session_id=SESSION, file_id=record.file_id
            )
            is None
        )
        assert (
            registry.get_file(owner_id=OWNER, session_id=SESSION, file_id="sf_missing")
            is None
        )

    def test_task_scope_records_are_invisible_to_session_scope(self, registry):
        source, _ = _ingest(registry)
        registry.copy_session_to_task(
            owner_id=OWNER,
            session_id=SESSION,
            file_ids=[source.file_id],
            task_id="task-1",
        )

        task_records = registry.list_task_files(owner_id=OWNER, task_id="task-1")
        assert len(task_records) == 1
        task_file_id = task_records[0].file_id

        # Task-scope rows are invisible and undeletable through session scope.
        assert (
            registry.get_file(owner_id=OWNER, session_id=SESSION, file_id=task_file_id)
            is None
        )
        assert (
            registry.delete_file(
                owner_id=OWNER, session_id=SESSION, file_id=task_file_id
            )
            is False
        )
        assert (
            registry.open_download(
                owner_id=OWNER, session_id=SESSION, file_id=task_file_id
            )
            is None
        )
        # Session listing does not leak task copies.
        session_records = registry.list_files(owner_id=OWNER, session_id=SESSION)
        assert [r.file_id for r in session_records] == [source.file_id]

    def test_delete_removes_row_and_blob(self, registry, storage):
        record, _ = _ingest(registry)

        assert (
            registry.delete_file(
                owner_id=OWNER, session_id=SESSION, file_id=record.file_id
            )
            is True
        )

        assert storage.saved == {}
        assert record.storage_uri in storage.deleted_uris
        assert registry.list_files(owner_id=OWNER, session_id=SESSION) == []
        # Second delete is a quiet miss.
        assert (
            registry.delete_file(
                owner_id=OWNER, session_id=SESSION, file_id=record.file_id
            )
            is False
        )

    def test_open_download_streams_stored_bytes(self, registry):
        record, _ = _ingest(registry)

        opened = registry.open_download(
            owner_id=OWNER, session_id=SESSION, file_id=record.file_id
        )

        assert opened is not None
        stream, opened_record = opened
        with stream:
            chunks = []
            while chunk := stream.read(registry.config.download_chunk_bytes):
                chunks.append(chunk)
        assert b"".join(chunks) == CSV_CONTENT
        assert opened_record.file_id == record.file_id


class TestScopeCopies:
    """Session/task copies are atomic, byte-identical, lineage-preserving."""

    def test_copy_session_to_task_preserves_bytes_and_lineage(self, registry, storage):
        first, _ = _ingest(registry, name="a.csv")
        second, _ = _ingest(registry, name="b.csv")

        copied = registry.copy_session_to_task(
            owner_id=OWNER,
            session_id=SESSION,
            file_ids=[first.file_id, second.file_id],
            task_id="task-1",
        )

        assert len(copied) == 2
        by_name = {record.display_name: record for record in copied}
        for source in (first, second):
            clone = by_name[source.display_name]
            assert clone.task_id == "task-1"
            assert clone.session_id is None
            assert clone.file_id != source.file_id
            assert clone.source_file_id == source.file_id
            assert clone.ordinal == source.ordinal
            assert clone.sha256 == source.sha256
            assert clone.size_bytes == source.size_bytes
            assert clone.media_type == source.media_type
            assert clone.file_kind == source.file_kind
            assert clone.status == source.status
            assert clone.inspection_json == source.inspection_json
            blob = storage.saved[clone.storage_uri]
            assert blob == storage.saved[source.storage_uri]

    def test_copy_task_to_session_round_trip(self, registry, storage):
        source, _ = _ingest(registry)
        task_copies = registry.copy_session_to_task(
            owner_id=OWNER,
            session_id=SESSION,
            file_ids=[source.file_id],
            task_id="task-9",
        )

        back = registry.copy_task_to_session(
            owner_id=OWNER, task_id="task-9", session_id=OTHER_SESSION
        )

        assert len(back) == 1
        clone = back[0]
        assert clone.session_id == OTHER_SESSION
        assert clone.task_id is None
        assert clone.source_file_id == task_copies[0].file_id
        assert clone.sha256 == source.sha256
        assert storage.saved[clone.storage_uri] == CSV_CONTENT
        assert clone.ordinal == 0
        # Original scope stays untouched.
        assert [
            r.file_id for r in registry.list_files(owner_id=OWNER, session_id=SESSION)
        ] == [source.file_id]

    def test_copy_is_atomic_when_middle_blob_fails(self, registry, storage):
        first, _ = _ingest(registry, name="a.csv")
        second, _ = _ingest(registry, name="b.csv")
        before_rows = len(registry.list_task_files(owner_id=OWNER, task_id="task-x"))

        original_save = storage.save_file
        calls = {"count": 0}

        def _flaky_save(*args, **kwargs):
            calls["count"] += 1
            if calls["count"] == 2:
                raise RuntimeError("backend write failed")
            return original_save(*args, **kwargs)

        storage.save_file = _flaky_save

        with pytest.raises(RuntimeError, match="backend write failed"):
            registry.copy_session_to_task(
                owner_id=OWNER,
                session_id=SESSION,
                file_ids=[first.file_id, second.file_id],
                task_id="task-x",
            )

        # No new rows, no remaining new blobs: compensation removed the first
        # copy after the second one failed.
        assert (
            len(registry.list_task_files(owner_id=OWNER, task_id="task-x"))
            == before_rows
        )
        assert len(storage.saved) == 2  # only the two original blobs remain
        assert len(storage.deleted_uris) >= 1

    def test_copy_missing_file_fails_without_side_effects(self, registry):
        with pytest.raises(SessionFileRegistryError) as excinfo:
            registry.copy_session_to_task(
                owner_id=OWNER,
                session_id=SESSION,
                file_ids=["sf_missing"],
                task_id="task-x",
            )
        assert excinfo.value.code == "SESSION_FILE_NOT_FOUND"
        assert registry.list_task_files(owner_id=OWNER, task_id="task-x") == []


class TestOwnerQuota:
    """Owner-byte quota reservation is atomic and race-free."""

    def test_quota_exceeded_fails_without_side_effects(self, tmp_path, storage):
        registry = _make_registry(
            tmp_path / "work", storage=storage, config=_config(max_owner_bytes=45)
        )
        for index in range(3):
            _ingest(registry, name=f"f{index}.csv")

        with pytest.raises(SessionFileRegistryError) as excinfo:
            _ingest(registry, name="overflow.csv")
        assert excinfo.value.code == "QUOTA_EXCEEDED"

        records = registry.list_files(owner_id=OWNER, session_id=SESSION)
        assert len(records) == 3
        assert len(storage.saved) == 3
        total = sum(r.size_bytes for r in records)
        assert total == 3 * len(CSV_CONTENT)

    def test_disabled_quota_allows_overflow(self, tmp_path, storage):
        # A negative max_owner_bytes disables quota accounting; uploads that
        # would normally exceed the limit must all succeed and persist.
        registry = _make_registry(
            tmp_path / "work", storage=storage, config=_config(max_owner_bytes=-1)
        )
        for index in range(6):
            _ingest(registry, name=f"f{index}.csv")

        records = registry.list_files(owner_id=OWNER, session_id=SESSION)
        assert len(records) == 6
        assert len(storage.saved) == 6
        total = sum(r.size_bytes for r in records)
        assert total == 6 * len(CSV_CONTENT)

    def test_delete_session_files_clears_scope(self, tmp_path, storage):
        registry = _make_registry(tmp_path / "work", storage=storage, config=_config())
        for index in range(3):
            _ingest(registry, name=f"f{index}.csv")
        assert len(registry.list_files(owner_id=OWNER, session_id=SESSION)) == 3

        removed = registry.delete_session_files(owner_id=OWNER, session_id=SESSION)

        assert removed == 3
        assert registry.list_files(owner_id=OWNER, session_id=SESSION) == []
        assert len(storage.saved) == 0  # blobs deleted too

    def test_quota_counts_copies_towards_owner_total(self, tmp_path, storage):
        registry = _make_registry(
            tmp_path / "work", storage=storage, config=_config(max_owner_bytes=20)
        )
        record, _ = _ingest(registry, name="a.csv")

        with pytest.raises(SessionFileRegistryError) as excinfo:
            registry.copy_session_to_task(
                owner_id=OWNER,
                session_id=SESSION,
                file_ids=[record.file_id],
                task_id="task-q",
            )
        assert excinfo.value.code == "QUOTA_EXCEEDED"
        assert registry.list_task_files(owner_id=OWNER, task_id="task-q") == []

    def test_concurrent_ingest_never_overruns_quota(self, tmp_path):
        # Separate pooled connections per thread need a file-backed database;
        # StaticPool would serialize every thread onto one connection.
        db_path = tmp_path / "quota_race.db"
        db.init_db(f"sqlite:///{db_path}")
        db.create_all()
        quota = 45
        payload = b"x" * 13
        storage = _FakeStorageClient()
        registry = _make_registry(
            tmp_path / "work",
            storage=storage,
            config=_config(max_owner_bytes=quota),
        )
        worker_count = 8
        barrier = threading.Barrier(worker_count)
        outcomes: List[Optional[str]] = [None] * worker_count

        def _worker(index: int) -> None:
            barrier.wait(timeout=10)
            try:
                registry.ingest(
                    owner_id=OWNER,
                    session_id=SESSION,
                    display_name=f"race_{index}.csv",
                    media_type=None,
                    stream=_stream(payload),
                    size_bytes=len(payload),
                )
                outcomes[index] = "ok"
            except SessionFileRegistryError as error:
                outcomes[index] = error.code

        threads = [
            threading.Thread(target=_worker, args=(index,))
            for index in range(worker_count)
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=30)
        assert not any(t.is_alive() for t in threads)

        # CSV extension here is arbitrary; .csv payloads are plain bytes.
        committed = registry.dao.total_owner_size_bytes(OWNER)
        assert committed <= quota, f"quota overrun: committed {committed} > {quota}"
        assert committed % len(payload) == 0
        succeeded = outcomes.count("ok")
        assert succeeded == committed // len(payload)
        assert outcomes.count("QUOTA_EXCEEDED") == worker_count - succeeded
        # Persisted rows and blobs match the committed byte total exactly.
        rows = registry.list_files(owner_id=OWNER, session_id=SESSION)
        assert len(rows) == succeeded
        assert len(storage.saved) == succeeded

    def test_locker_uses_keyed_threading_lock_for_sqlite(self):
        dao = SessionFileDao()
        locker = OwnerQuotaLocker(dao)
        assert locker._dialect_name() == "sqlite"
        first = {}
        second = {}
        with locker._locks_guard:
            locker._locks.setdefault(OTHER_OWNER, threading.Lock())

        def _acquire_other() -> None:
            acquired = locker._locks[OTHER_OWNER].acquire(blocking=False)
            second["acquired"] = acquired
            if acquired:
                locker._locks[OTHER_OWNER].release()

        with locker.acquire(OWNER):
            first["held"] = True
            # A different owner's lock must remain free while OWNER is held.
            t = threading.Thread(target=_acquire_other)
            t.start()
            t.join(timeout=5)
        assert first["held"] is True
        assert second.get("acquired") is True


class TestOwnerLockBound:
    """The process-local owner lock map stays bounded with LRU eviction."""

    def test_many_owners_do_not_grow_the_lock_map_unbounded(self, monkeypatch):
        from collections import OrderedDict

        monkeypatch.setattr(OwnerQuotaLocker, "_locks", OrderedDict())
        locker = OwnerQuotaLocker(SessionFileDao())
        cap = 4096
        over_limit = cap + 5

        for index in range(over_limit):
            with locker._keyed_threading_lock(f"owner-{index}"):
                pass

        locks = OwnerQuotaLocker._locks
        assert len(locks) == cap
        # Oldest entries are evicted first; the newest survive.
        assert "owner-0" not in locks
        assert f"owner-{over_limit - 1}" in locks

    def test_lock_object_is_stable_for_an_active_owner(self, monkeypatch):
        from collections import OrderedDict

        monkeypatch.setattr(OwnerQuotaLocker, "_locks", OrderedDict())
        locker = OwnerQuotaLocker(SessionFileDao())

        with locker._keyed_threading_lock("owner-a"):
            first = OwnerQuotaLocker._locks["owner-a"]
        with locker._keyed_threading_lock("owner-a"):
            second = OwnerQuotaLocker._locks["owner-a"]

        assert first is second

    def test_mysql_named_lock_uses_dedicated_null_pool_connection(self, monkeypatch):
        """The MySQL named lock must not occupy the shared ORM pool."""
        from dbgpt_serve.session_file import registry as registry_module

        class _Cursor:
            def __init__(self):
                self.statements = []

            def execute(self, sql, params=None):
                self.statements.append((sql, params))

            def fetchone(self):
                return (1,)

            def close(self):
                return None

        class _Connection:
            def __init__(self):
                self.cursors = []
                self.closed = False

            def cursor(self):
                cursor = _Cursor()
                self.cursors.append(cursor)
                return cursor

            def close(self):
                self.closed = True

        class _Engine:
            def __init__(self):
                self.connection = _Connection()
                self.disposed = False

            def connect(self):
                return self

            def __enter__(self):
                return type(
                    "_SAConnection",
                    (),
                    {"connection": self.connection},
                )()

            def __exit__(self, *args):
                self.connection.close()
                return False

            def dispose(self):
                self.disposed = True

        created = {}

        def _fake_create_engine(url, **kwargs):
            created["url"] = url
            created["kwargs"] = kwargs
            created["engine"] = _Engine()
            return created["engine"]

        monkeypatch.setattr(registry_module, "create_engine", _fake_create_engine)

        class _FakeDbManager:
            engine = type(
                "_MainEngine",
                (),
                {
                    "dialect": type("_Dialect", (), {"name": "mysql"})(),
                    "url": "mysql+pymysql://example/db",
                },
            )()

        class _FakeDao:
            _db_manager = _FakeDbManager()

        locker = OwnerQuotaLocker(_FakeDao())

        with locker.acquire("owner-a"):
            pass

        assert created["kwargs"]["poolclass"] is NullPool
        engine = created["engine"]
        statements = [cursor.statements[0][0] for cursor in engine.connection.cursors]
        assert "SELECT GET_LOCK(%s, %s)" in statements
        assert "SELECT RELEASE_LOCK(%s)" in statements
        assert engine.connection.closed is True
        assert engine.disposed is True


class TestMaterializeLocalFile:
    """Local materialization never escapes the configured work root."""

    def test_materialize_writes_bounded_chunks_and_cleans_up(self, registry):
        scope = FileScope(OWNER, session_id=SESSION)
        payload = b"hello materialized world" * 7
        strict = _stream(payload)

        with registry.materialize_local_file(scope, strict, ".txt") as path:
            assert path.exists()
            resolved_root = registry.work_root.resolve()
            # The materialized file lives under the CONFIGURED work root (the
            # registry never picks the system temp dir on its own).
            assert resolved_root in path.resolve().parents
            assert path.read_bytes() == payload
            assert stat.S_IMODE(os.lstat(path).st_mode) == 0o600
            run_dir = path.parent
            assert run_dir.name.startswith("run_")
            mode = stat.S_IMODE(os.lstat(run_dir).st_mode)
            assert mode & 0o777 == 0o700
        assert not run_dir.exists(), "run directory must be cleaned up"
        assert strict.max_read_size <= registry.config.upload_chunk_bytes

    def test_materialize_cleans_up_on_consumer_error(self, registry):
        scope = FileScope(OWNER, session_id=SESSION)
        observed: List[Path] = []
        with pytest.raises(RuntimeError, match="consumer failed"):
            with registry.materialize_local_file(
                scope, _stream(b"data"), ".txt"
            ) as path:
                observed.append(path)
                raise RuntimeError("consumer failed")
        assert observed and not observed[0].parent.exists()

    @pytest.mark.parametrize(
        "bad_owner",
        ["a/b", "a\\b", "bad\x00name", ".", "..", "CON", "NUL.txt"],
    )
    def test_materialize_rejects_unsafe_scope_components(self, registry, bad_owner):
        scope = FileScope(bad_owner, session_id=SESSION)
        with pytest.raises(SessionFileRegistryError) as excinfo:
            with registry.materialize_local_file(scope, _stream(b"x")):
                pass
        assert excinfo.value.code == "INVALID_SCOPE_COMPONENT"

    @pytest.mark.parametrize("bad_session", ["s/1", "sess\\ion", "../..", "PRN"])
    def test_materialize_rejects_unsafe_session_ids(self, registry, bad_session):
        # FileScope itself accepts these ids; the materializer must refuse to
        # put them on disk.
        with pytest.raises(SessionFileRegistryError) as excinfo:
            with registry.materialize_local_file(
                FileScope(OWNER, session_id=bad_session), _stream(b"x")
            ):
                pass
        assert excinfo.value.code == "INVALID_SCOPE_COMPONENT"

    def test_materialize_rejects_symlink_escape_of_work_root(self, tmp_path, storage):
        registry = _make_registry(tmp_path / "work", storage=storage)
        outside = tmp_path / "outside"
        outside.mkdir()
        owner_dir = registry.work_root / OWNER
        registry.work_root.mkdir(parents=True, exist_ok=True)
        os.symlink(outside, owner_dir)

        with pytest.raises(SessionFileRegistryError) as excinfo:
            with registry.materialize_local_file(
                FileScope(OWNER, session_id=SESSION), _stream(b"data"), ".txt"
            ):
                pass
        assert excinfo.value.code == "MATERIALIZE_FAILED"
        assert list(outside.iterdir()) == []

    def test_materialize_never_overwrites_preexisting_candidate(
        self, tmp_path, storage, monkeypatch
    ):
        # Deterministic token makes run dir and candidate names predictable.
        monkeypatch.setattr(
            "dbgpt_serve.session_file.registry.secrets.token_hex",
            lambda _n: "ab" * 8,
        )
        registry = _make_registry(tmp_path / "work", storage=storage)
        run_dir = registry.work_root / OWNER / f"session_{SESSION}" / f"run_{'ab' * 8}"
        run_dir.mkdir(parents=True)
        sentinel = run_dir / f"f_{'ab' * 8}.txt"
        sentinel.write_bytes(b"pre-existing")

        with pytest.raises(SessionFileRegistryError) as excinfo:
            with registry.materialize_local_file(
                FileScope(OWNER, session_id=SESSION), _stream(b"payload"), ".txt"
            ):
                pass
        assert excinfo.value.code == "MATERIALIZE_FAILED"
        assert sentinel.read_bytes() == b"pre-existing"

    def test_write_stream_secure_refuses_symlinked_candidate(
        self, tmp_path, storage, monkeypatch
    ):
        # White-box: O_EXCL|O_NOFOLLOW must never follow a planted symlink.
        monkeypatch.setattr(
            "dbgpt_serve.session_file.registry.secrets.token_hex",
            lambda _n: "ab" * 8,
        )
        registry = _make_registry(tmp_path / "work", storage=storage)
        run_dir = tmp_path / "work" / "run"
        run_dir.mkdir(parents=True)
        evil_target = tmp_path / "evil_target.txt"
        os.symlink(evil_target, run_dir / f"f_{'ab' * 8}.txt")

        with pytest.raises(SessionFileRegistryError) as excinfo:
            registry._write_stream_secure(run_dir, ".txt", _stream(b"payload"))
        assert excinfo.value.code == "MATERIALIZE_FAILED"
        assert not evil_target.exists()


class TestRealFileStorageClient:
    """The registry persists through the existing FileStorageClient seam."""

    def test_ingest_round_trip_with_local_backend(self, tmp_path):
        from dbgpt.core.interface.file import (
            FileStorageClient,
            FileStorageSystem,
            LocalFileStorage,
        )

        backend = LocalFileStorage(base_path=str(tmp_path / "blobstore"))
        client = FileStorageClient(
            storage_system=FileStorageSystem({backend.storage_type: backend})
        )
        registry = _make_registry(tmp_path / "work", storage=client)

        record = registry.ingest(
            owner_id=OWNER,
            session_id=SESSION,
            display_name="report.csv",
            media_type="text/csv",
            stream=_stream(CSV_CONTENT),
            size_bytes=len(CSV_CONTENT),
        )

        assert record.storage_uri.startswith("dbgpt-fs://local/session-files/")
        blob_path = tmp_path / "blobstore" / "session-files" / record.file_id
        assert blob_path.read_bytes() == CSV_CONTENT
        opened = registry.open_download(
            owner_id=OWNER, session_id=SESSION, file_id=record.file_id
        )
        assert opened is not None
        stream, _ = opened
        with stream:
            assert stream.read(1024) == CSV_CONTENT
        assert (
            registry.delete_file(
                owner_id=OWNER, session_id=SESSION, file_id=record.file_id
            )
            is True
        )
        assert not blob_path.exists()
