"""Storage orchestration for owner-aware session files.

The registry sits between the API transport and the persistence seams:

- uploads stream through a :class:`tempfile.SpooledTemporaryFile` in
  configured chunks with a running SHA-256 and mid-stream size enforcement;
- blobs persist through the existing ``FileStorageClient`` under the
  ``session-files`` bucket with random storage keys decoupled from display
  names, so same-name uploads never overwrite;
- DAO rows are created only after the blob exists; on DAO failure the blob is
  deleted, and on blob failure no row is created;
- rows start ``INSPECTING`` and finish ``READY``/``PREVIEW_FAILED`` through
  the bounded :class:`SessionFileInspector` with ``inspection_json`` stored
  as exactly ``{"preview": dict, "truncated": bool}``;
- owner-byte quota is reserved inside :class:`OwnerQuotaLocker`, re-reading
  the committed total inside the lock before the insert so concurrent
  uploads cannot overrun the quota.
"""

import asyncio
import contextlib
import hashlib
import json
import logging
import os
import re
import secrets
import shutil
import stat
import tempfile
import threading
from collections import OrderedDict
from contextlib import contextmanager
from pathlib import Path
from typing import Any, BinaryIO, Iterator, List, Optional, Tuple

from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool

from .config import ServeConfig
from .domain import (
    FileScope,
    SessionFilePrivateRecord,
    SessionFileStatus,
)
from .inspector import InspectionResult, SessionFileInspector, _result_type
from .models.dao import SessionFileDao

logger = logging.getLogger(__name__)

SESSION_FILE_BUCKET = "session-files"

_SAFE_COMPONENT_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._~=-]*")
_SAFE_SUFFIX_RE = re.compile(r"\.[A-Za-z0-9]{1,12}")
_MAX_COMPONENT_BYTES = 128
_MAX_SUFFIX_BYTES = 16
_MAX_OWNER_LOCKS = 4096

_WINDOWS_DEVICE_NAMES = frozenset(
    ["CON", "PRN", "AUX", "NUL"]
    + [f"COM{i}" for i in range(1, 10)]
    + [f"LPT{i}" for i in range(1, 10)]
)


class SessionFileRegistryError(Exception):
    """Deterministic registry error carrying a stable domain code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class OwnerQuotaLocker:
    """Serialize the per-owner quota check-and-insert critical section.

    The lock guarantees that "re-read the committed owner total, then insert"
    is atomic per owner, so concurrent uploads cannot overrun
    ``max_owner_bytes``. Callers must hold the lock across both the
    :meth:`SessionFileDao.total_owner_size_bytes` read and the row insert.

    MySQL lifecycle: a named lock is taken with
    ``SELECT GET_LOCK(:name, :timeout)`` and released with
    ``SELECT RELEASE_LOCK(:name)`` on a *dedicated* ``NullPool`` connection.
    The lock connection intentionally stays outside the ORM connection pool:
    the critical section may include slow DAO work, and sharing one pooled
    connection here while the DAO checks out another can exhaust the pool
    under concurrent uploads. Named locks are per-connection: they
    auto-release when the connection dies, must never be shared across
    connections, and must never be nested on one connection. The lock name
    mixes a fixed prefix with a truncated owner hash, staying under MySQL's
    64-character named-lock limit.

    SQLite (and tests): an in-process keyed ``threading.Lock`` per owner id.
    Other dialects fall back to the same keyed lock and log a warning.

    The process-local lock map is bounded: it keeps at most
    ``_MAX_OWNER_LOCKS`` owners and evicts the least-recently-used entry
    (preferring locks that are not currently held) before inserting a new
    one, so a long-lived process never grows the map without limit.
    """

    _locks_guard = threading.Lock()
    _locks: "OrderedDict[str, threading.Lock]" = OrderedDict()

    def __init__(self, dao: SessionFileDao, timeout_seconds: float = 10.0):
        self._dao = dao
        self._timeout_seconds = timeout_seconds

    @contextmanager
    def acquire(self, owner_id: str) -> Iterator[None]:
        """Hold the per-owner quota lock for one critical section."""
        dialect = self._dialect_name()
        if dialect == "mysql":
            with self._mysql_named_lock(owner_id):
                yield
        else:
            if dialect not in ("sqlite", "unknown"):
                logger.warning(
                    "OwnerQuotaLocker using process-local lock for dialect %s",
                    dialect,
                )
            with self._keyed_threading_lock(owner_id):
                yield

    def _dialect_name(self) -> str:
        engine = getattr(self._dao._db_manager, "engine", None)
        if engine is None:
            return "unknown"
        return engine.dialect.name

    @classmethod
    def _lock_for(cls, owner_id: str) -> threading.Lock:
        """Return the per-owner lock, evicting LRU entries beyond the cap."""
        with cls._locks_guard:
            lock = cls._locks.get(owner_id)
            if lock is not None:
                cls._locks.move_to_end(owner_id)
                return lock
            if len(cls._locks) >= _MAX_OWNER_LOCKS:
                cls._evict_lru_owner_lock()
            lock = threading.Lock()
            cls._locks[owner_id] = lock
            return lock

    @classmethod
    def _evict_lru_owner_lock(cls) -> None:
        """Evict the oldest idle lock; the caller must hold the guard."""
        for candidate in list(cls._locks.keys()):
            if not cls._locks[candidate].locked():
                del cls._locks[candidate]
                return
        # Pathological case: every lock is currently held. Evict the oldest
        # anyway to keep the map bounded.
        oldest = next(iter(cls._locks))
        logger.warning(
            "All %d owner quota locks are held; evicting the oldest entry",
            _MAX_OWNER_LOCKS,
        )
        del cls._locks[oldest]

    @contextmanager
    def _keyed_threading_lock(self, owner_id: str) -> Iterator[None]:
        lock = self._lock_for(owner_id)
        with lock:
            yield

    @contextmanager
    def _mysql_named_lock(self, owner_id: str) -> Iterator[None]:
        engine = self._dao._db_manager.engine
        owner_hash = hashlib.sha256(owner_id.encode("utf-8")).hexdigest()[:32]
        lock_name = f"dbgpt_session_file_quota_{owner_hash}"
        # Keep the named lock off the shared ORM pool: GET/RELEASE_LOCK are
        # per-connection and the critical section also performs DAO work.
        lock_engine = create_engine(engine.url, poolclass=NullPool)
        try:
            with lock_engine.connect() as connection:
                cursor = connection.connection.cursor()
                try:
                    cursor.execute(
                        "SELECT GET_LOCK(%s, %s)",
                        (lock_name, int(self._timeout_seconds)),
                    )
                    acquired = cursor.fetchone()[0]
                finally:
                    cursor.close()
                if acquired != 1:
                    raise SessionFileRegistryError(
                        "QUOTA_LOCK_TIMEOUT",
                        "Could not acquire the owner quota lock.",
                    )
                try:
                    yield
                finally:
                    cursor = connection.connection.cursor()
                    try:
                        cursor.execute("SELECT RELEASE_LOCK(%s)", (lock_name,))
                    finally:
                        cursor.close()
        finally:
            lock_engine.dispose()


def _run_coro_blocking(coro) -> Any:
    """Drive a bounded coroutine from synchronous registry code.

    ``inspect_async`` is the mandated inspection entry point; the registry is
    synchronous, so the coroutine runs through ``asyncio.run``. When called
    from a thread that already owns a running loop, the coroutine is executed
    on a dedicated helper thread with its own loop instead.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    result: List[Any] = []
    errors: List[BaseException] = []

    def _runner() -> None:
        try:
            result.append(asyncio.run(coro))
        except BaseException as error:  # noqa: BLE001 - re-raised below
            errors.append(error)

    thread = threading.Thread(
        target=_runner, name="session-file-registry-async", daemon=True
    )
    thread.start()
    thread.join()
    if errors:
        raise errors[0]
    return result[0]


def _sanitize_scope_component(value: str) -> str:
    """Validate one path component used inside the materialization root."""
    if not value or not value.strip():
        raise SessionFileRegistryError(
            "INVALID_SCOPE_COMPONENT", "Scope component must not be blank."
        )
    if (
        "\x00" in value
        or "/" in value
        or "\\" in value
        or (os.sep and os.sep in value)
        or (os.altsep and os.altsep in value)
    ):
        raise SessionFileRegistryError(
            "INVALID_SCOPE_COMPONENT",
            "Scope component must not contain path separators or nulls.",
        )
    if value in (".", "..") or not _SAFE_COMPONENT_RE.fullmatch(value):
        raise SessionFileRegistryError(
            "INVALID_SCOPE_COMPONENT", "Scope component is not filesystem-safe."
        )
    if len(value.encode("utf-8")) > _MAX_COMPONENT_BYTES:
        raise SessionFileRegistryError(
            "INVALID_SCOPE_COMPONENT", "Scope component is too long."
        )
    stem = value.split(".", 1)[0].upper()
    if stem in _WINDOWS_DEVICE_NAMES:
        raise SessionFileRegistryError(
            "INVALID_SCOPE_COMPONENT", "Scope component is a reserved device name."
        )
    return value


def _sanitize_suffix(suffix: str) -> str:
    if len(suffix.encode("utf-8")) > _MAX_SUFFIX_BYTES:
        return ""
    if _SAFE_SUFFIX_RE.fullmatch(suffix):
        return suffix.lower()
    return ""


class SessionFileRegistry:
    """Orchestrate session file storage, quota, inspection and copies."""

    def __init__(
        self,
        *,
        storage_client: Any,
        dao: SessionFileDao,
        inspector: SessionFileInspector,
        config: ServeConfig,
        work_root: Any,
        quota_locker: Optional[OwnerQuotaLocker] = None,
        file_id_factory: Optional[Any] = None,
    ) -> None:
        self._storage = storage_client
        self._dao = dao
        self._inspector = inspector
        self._config = config
        self._work_root = Path(work_root)
        self._quota_locker = quota_locker or OwnerQuotaLocker(dao)
        self._file_id_factory = file_id_factory or (
            lambda: f"sf_{secrets.token_hex(16)}"
        )

    @property
    def config(self) -> ServeConfig:
        return self._config

    @property
    def dao(self) -> SessionFileDao:
        return self._dao

    @property
    def work_root(self) -> Path:
        return self._work_root

    # ------------------------------------------------------------------
    # Ingest
    # ------------------------------------------------------------------

    def ingest(
        self,
        *,
        owner_id: str,
        session_id: str,
        display_name: str,
        media_type: Optional[str],
        stream: BinaryIO,
        size_bytes: int,
    ) -> SessionFilePrivateRecord:
        """Persist one transport-validated upload for a session scope."""
        scope = FileScope(owner_id, session_id=session_id)
        spool, actual_size, digest = self._spool_upload(stream)
        try:
            if actual_size != size_bytes:
                raise SessionFileRegistryError(
                    "SIZE_MISMATCH",
                    "Declared size does not match the uploaded bytes.",
                )
            file_id = self._allocate_file_id()
            uri = self._save_blob(spool, file_id, display_name, owner_id)
            try:
                with self._quota_locker.acquire(owner_id):
                    self._reserve_owner_quota(owner_id, actual_size)
                    ordinal = len(self._dao.list_by_scope(scope))
                    self._create_row(
                        scope=scope,
                        file_id=file_id,
                        display_name=display_name,
                        storage_uri=uri,
                        size_bytes=actual_size,
                        sha256=digest,
                        ordinal=ordinal,
                        status=SessionFileStatus.INSPECTING,
                        source_file_id=None,
                    )
            except Exception:
                self._delete_blob_quietly(uri)
                raise
            try:
                suffix = Path(display_name).suffix.lower()
                spool.seek(0)
                with self.materialize_local_file(scope, spool, suffix) as staged:
                    result = self._inspect_staged(staged, media_type)
            except SessionFileRegistryError:
                self._compensate_persisted_row(scope, file_id, uri)
                raise
            except Exception as error:
                self._compensate_persisted_row(scope, file_id, uri)
                raise SessionFileRegistryError(
                    "MATERIALIZE_FAILED",
                    "Could not materialize the uploaded file.",
                ) from error
            finally:
                spool.close()
            spool = None
            try:
                self._finalize_inspection(scope, file_id, result)
            except SessionFileRegistryError:
                self._compensate_persisted_row(scope, file_id, uri)
                raise
            except Exception as error:
                self._compensate_persisted_row(scope, file_id, uri)
                raise SessionFileRegistryError(
                    "FINALIZE_FAILED",
                    "Could not persist the inspection outcome.",
                ) from error
            record = self._dao.get_private_file_by_id(file_id, scope)
            if record is None:
                raise SessionFileRegistryError(
                    "INGEST_LOST", "Persisted session file could not be reloaded."
                )
            return record
        finally:
            if spool is not None:
                spool.close()

    def _spool_upload(
        self, stream: BinaryIO
    ) -> Tuple[tempfile.SpooledTemporaryFile, int, str]:
        """Stream an upload into a spool with running hash and size guard."""
        spool = tempfile.SpooledTemporaryFile(max_size=self._config.upload_spool_bytes)
        hasher = hashlib.sha256()
        size = 0
        try:
            while chunk := stream.read(self._config.upload_chunk_bytes):
                size += len(chunk)
                if size > self._config.max_file_bytes:
                    raise SessionFileRegistryError(
                        "FILE_TOO_LARGE",
                        f"File exceeds {self._config.max_file_bytes} bytes.",
                    )
                hasher.update(chunk)
                spool.write(chunk)
            spool.seek(0)
            return spool, size, hasher.hexdigest()
        except Exception:
            spool.close()
            raise

    def _allocate_file_id(self) -> str:
        from .models.models import SessionFileEntity

        for _ in range(5):
            file_id = self._file_id_factory()
            with self._dao.session(commit=False) as session:
                exists = (
                    session.query(SessionFileEntity)
                    .filter(SessionFileEntity.file_id == file_id)
                    .first()
                )
            if exists is None:
                return file_id
        raise SessionFileRegistryError(
            "FILE_ID_CONFLICT", "Could not allocate a unique storage key."
        )

    def _save_blob(
        self,
        spool: BinaryIO,
        file_id: str,
        display_name: str,
        owner_id: str,
    ) -> str:
        spool.seek(0)
        return self._storage.save_file(
            SESSION_FILE_BUCKET,
            display_name,
            spool,
            custom_metadata={"owner_id": owner_id, "display_name": display_name},
            file_id=file_id,
        )

    def _reserve_owner_quota(self, owner_id: str, incoming_bytes: int) -> None:
        """Re-read the committed owner total and reserve bytes atomically.

        Must only be called while holding ``OwnerQuotaLocker`` for the owner.
        """
        if self._config.max_owner_bytes < 0:
            # Negative quota means unlimited; skip the accounting read entirely.
            return
        committed = self._dao.total_owner_size_bytes(owner_id)
        if committed + incoming_bytes > self._config.max_owner_bytes:
            raise SessionFileRegistryError(
                "QUOTA_EXCEEDED",
                f"Owner storage quota of {self._config.max_owner_bytes} "
                "bytes would be exceeded.",
            )

    def _create_row(
        self,
        *,
        scope: FileScope,
        file_id: str,
        display_name: str,
        storage_uri: str,
        size_bytes: int,
        sha256: str,
        ordinal: int,
        status: SessionFileStatus,
        source_file_id: Optional[str],
        inspection_json: Optional[str] = None,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> None:
        kind, detected_media = _result_type(Path(display_name))
        request = {
            "file_id": file_id,
            "owner_id": scope.owner_id,
            "session_id": scope.session_id,
            "task_id": scope.task_id,
            "display_name": display_name,
            "storage_uri": storage_uri,
            "media_type": detected_media,
            "file_kind": kind,
            "size_bytes": size_bytes,
            "sha256": sha256,
            "ordinal": ordinal,
            "status": status.value,
            "inspection_json": inspection_json,
            "error_code": error_code,
            "error_message": error_message,
            "source_file_id": source_file_id,
        }
        self._dao.create(request)

    def _inspect_staged(
        self, path: Path, declared_media_type: Optional[str]
    ) -> InspectionResult:
        try:
            return _run_coro_blocking(
                self._inspector.inspect_async(path, declared_media_type)
            )
        except Exception:
            logger.exception("Session file inspection crashed")
            kind, media_type = _result_type(path)
            return SessionFileInspector._failure(kind, media_type, "CORRUPT_FILE")

    def _finalize_inspection(
        self, scope: FileScope, file_id: str, result: InspectionResult
    ) -> None:
        inspection_json = json.dumps(
            {
                "preview": dict(result.preview),
                "truncated": bool(result.truncated),
            },
            default=str,
        )
        self._dao.update_status(
            file_id,
            scope,
            result.status,
            inspection_json=inspection_json,
            error_code=result.error_code,
            error_message=result.error_message,
        )

    # ------------------------------------------------------------------
    # Reads and deletion (FileScope ACL enforced by the DAO)
    # ------------------------------------------------------------------

    def list_files(
        self, *, owner_id: str, session_id: str
    ) -> List[SessionFilePrivateRecord]:
        """List session files in stable upload order for the exact scope."""
        scope = FileScope(owner_id, session_id=session_id)
        return [
            self._dao.get_private_file_by_id(item.file_id, scope)
            for item in self._dao.list_by_scope(scope)
        ]

    def list_task_files(
        self, *, owner_id: str, task_id: str
    ) -> List[SessionFilePrivateRecord]:
        """List task files in stable order for the exact task scope."""
        scope = FileScope(owner_id, task_id=task_id)
        return [
            self._dao.get_private_file_by_id(item.file_id, scope)
            for item in self._dao.list_by_scope(scope)
        ]

    def get_file(
        self, *, owner_id: str, session_id: str, file_id: str
    ) -> Optional[SessionFilePrivateRecord]:
        """Return a session file for the exact scope, otherwise ``None``."""
        return self._dao.get_private_file_by_id(
            file_id, FileScope(owner_id, session_id=session_id)
        )

    def get_task_file(
        self, *, owner_id: str, task_id: str, file_id: str
    ) -> Optional[SessionFilePrivateRecord]:
        """Return a task file for the exact task scope, otherwise ``None``."""
        return self._dao.get_private_file_by_id(
            file_id, FileScope(owner_id, task_id=task_id)
        )

    def open_download(
        self, *, owner_id: str, session_id: str, file_id: str
    ) -> Optional[Tuple[BinaryIO, SessionFilePrivateRecord]]:
        """Open stored bytes for an exact session scope."""
        record = self.get_file(
            owner_id=owner_id, session_id=session_id, file_id=file_id
        )
        if record is None:
            return None
        try:
            stream, _metadata = self._storage.get_file(record.storage_uri)
        except FileNotFoundError:
            return None
        return stream, record

    def delete_file(self, *, owner_id: str, session_id: str, file_id: str) -> bool:
        """Delete the DAO row then the blob for an exact session scope."""
        return self._delete_in_scope(
            FileScope(owner_id, session_id=session_id), file_id
        )

    def delete_task_file(self, *, owner_id: str, task_id: str, file_id: str) -> bool:
        """Delete the DAO row then the blob for an exact task scope."""
        return self._delete_in_scope(FileScope(owner_id, task_id=task_id), file_id)

    def delete_session_files(self, *, owner_id: str, session_id: str) -> int:
        """Delete all files in a session scope; returns the number removed.

        Used by scheduled-task replay to reclaim the previous run's copied
        files before freezing the current run into a fresh session, so
        run-session copies do not accumulate unbounded on disk.
        """
        scope = FileScope(owner_id, session_id=session_id)
        removed = 0
        for item in self._dao.list_by_scope(scope):
            if self._delete_in_scope(scope, item.file_id):
                removed += 1
        return removed

    def _delete_in_scope(self, scope: FileScope, file_id: str) -> bool:
        record = self._dao.get_private_file_by_id(file_id, scope)
        if record is None:
            return False
        deleted = self._dao.delete_by_file_id(file_id, scope)
        if not deleted:
            return False
        try:
            self._storage.delete_file(record.storage_uri)
        except Exception:
            logger.exception(
                "Failed to delete session file blob for %s", record.file_id
            )
        return True

    def _delete_blob_quietly(self, uri: str) -> None:
        try:
            self._storage.delete_file(uri)
        except Exception:
            logger.exception("Failed to compensate session file blob")

    def _compensate_persisted_row(
        self, scope: FileScope, file_id: str, uri: str
    ) -> None:
        """Roll back a persisted row and its blob after post-create failure.

        Deleting the row also frees the reserved owner quota because the
        committed owner total is derived from persisted rows.
        """
        try:
            self._dao.delete_by_file_id(file_id, scope)
        except Exception:
            logger.exception("Failed to compensate session file row %s", file_id)
        self._delete_blob_quietly(uri)

    # ------------------------------------------------------------------
    # Safe local materialization
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # All-or-nothing scope copies
    # ------------------------------------------------------------------

    def copy_session_to_task(
        self,
        *,
        owner_id: str,
        session_id: str,
        file_ids: List[str],
        task_id: str,
    ) -> List[SessionFilePrivateRecord]:
        """Copy selected session files into a task scope atomically.

        Every copy streams the source blob into a new blob under a new random
        ``file_id`` plus a new row preserving ordinal/kind/hash/display name/
        media type and ``source_file_id`` lineage. Any failure deletes every
        new row and blob created so far.
        """
        source_scope = FileScope(owner_id, session_id=session_id)
        records = [
            self._dao.get_private_file_by_id(file_id, source_scope)
            for file_id in file_ids
        ]
        if any(record is None for record in records):
            raise SessionFileRegistryError("SESSION_FILE_NOT_FOUND", "File not found.")
        return self._copy_into_scope(
            owner_id=owner_id,
            sources=records,
            target_scope=FileScope(owner_id, task_id=task_id),
        )

    def copy_task_to_session(
        self, *, owner_id: str, task_id: str, session_id: str
    ) -> List[SessionFilePrivateRecord]:
        """Copy every task file back into a session scope atomically.

        A scope lookup that yields zero files is treated the same as a
        missing file: fail closed. Replays only call this when the frozen
        payload declares ``file_ids`` — silently copying nothing would let a
        forged (or foreign-owned) task scope run with empty inputs instead
        of surfacing as a failed run.
        """
        source_scope = FileScope(owner_id, task_id=task_id)
        records = [
            self._dao.get_private_file_by_id(item.file_id, source_scope)
            for item in self._dao.list_by_scope(source_scope)
        ]
        if not records or any(record is None for record in records):
            raise SessionFileRegistryError("SESSION_FILE_NOT_FOUND", "File not found.")
        return self._copy_into_scope(
            owner_id=owner_id,
            sources=records,
            target_scope=FileScope(owner_id, session_id=session_id),
        )

    def _copy_into_scope(
        self,
        *,
        owner_id: str,
        sources: List[SessionFilePrivateRecord],
        target_scope: FileScope,
    ) -> List[SessionFilePrivateRecord]:
        if not sources:
            return []
        total_bytes = sum(record.size_bytes for record in sources)
        created_ids: List[str] = []
        created_uris: List[str] = []
        try:
            with self._quota_locker.acquire(owner_id):
                self._reserve_owner_quota(owner_id, total_bytes)
                for source in sources:
                    file_id, uri = self._copy_one_blob(source, owner_id)
                    created_uris.append(uri)
                    self._create_row(
                        scope=target_scope,
                        file_id=file_id,
                        display_name=source.display_name,
                        storage_uri=uri,
                        size_bytes=source.size_bytes,
                        sha256=source.sha256,
                        ordinal=source.ordinal,
                        status=source.status,
                        source_file_id=source.file_id,
                        inspection_json=source.inspection_json,
                        error_code=source.error_code,
                        error_message=source.error_message,
                    )
                    created_ids.append(file_id)
        except Exception:
            for file_id in reversed(created_ids):
                with contextlib.suppress(Exception):
                    self._dao.delete_by_file_id(file_id, target_scope)
            for uri in reversed(created_uris):
                self._delete_blob_quietly(uri)
            raise
        return [
            self._dao.get_private_file_by_id(file_id, target_scope)
            for file_id in created_ids
        ]

    def _copy_one_blob(
        self, source: SessionFilePrivateRecord, owner_id: str
    ) -> Tuple[str, str]:
        """Stream one stored blob into a new blob under a fresh file_id."""
        blob_stream, _metadata = self._storage.get_file(source.storage_uri)
        spool = tempfile.SpooledTemporaryFile(max_size=self._config.upload_spool_bytes)
        try:
            with blob_stream:
                while chunk := blob_stream.read(self._config.upload_chunk_bytes):
                    spool.write(chunk)
            file_id = self._allocate_file_id()
            uri = self._save_blob(spool, file_id, source.display_name, owner_id)
            return file_id, uri
        finally:
            spool.close()

    @contextmanager
    def materialize_local_file(
        self, scope: FileScope, source: BinaryIO, suffix: str = ""
    ) -> Iterator[Path]:
        """Materialize stream bytes under the configured persistent work root.

        The on-disk layout is
        ``<work_root>/<owner>/<session_<id>|task_<id>>/run_<random>/f_<random>``
        with directories ``0o700`` and files ``0o600`` opened with
        ``O_CREAT|O_EXCL|O_NOFOLLOW``. Scope components are strict allowlist
        validated (no separators, nulls, dot-files or device names); parents
        and the resolved final path are verified to stay under the run root;
        bytes are copied in configured chunks; the run directory is always
        removed on exit. The work root is configured, persistent storage —
        never the system temp directory.
        """
        with self._secure_run_dir(scope) as run_dir:
            yield self._write_stream_secure(run_dir, suffix, source)

    def _secure_run_dir(self, scope: FileScope) -> Iterator[Path]:
        owner = _sanitize_scope_component(scope.owner_id)
        if scope.session_id is not None:
            leaf = f"session_{_sanitize_scope_component(scope.session_id)}"
        else:
            leaf = f"task_{_sanitize_scope_component(scope.task_id)}"
        root = self._work_root.resolve()
        base = root / owner / leaf
        # Resolve BEFORE mkdir: a pre-planted symlinked parent that escapes
        # the work root must never receive new directories.
        self._assert_resolved_under(root, base)
        base.mkdir(parents=True, exist_ok=True)
        # Re-verify after creation to catch a parent swapped mid-flight.
        self._assert_resolved_under(root, base)
        run_dir: Optional[Path] = None
        for _ in range(5):
            candidate = base / f"run_{secrets.token_hex(8)}"
            try:
                candidate.mkdir(mode=0o700)
                run_dir = candidate
                break
            except FileExistsError:
                continue
        if run_dir is None:
            raise SessionFileRegistryError(
                "MATERIALIZE_FAILED", "Could not allocate a run directory."
            )
        try:
            yield self._assert_resolved_under(root, run_dir)
        finally:
            shutil.rmtree(run_dir, ignore_errors=True)

    _secure_run_dir = contextmanager(_secure_run_dir)

    def _write_stream_secure(
        self, run_dir: Path, suffix: str, source: BinaryIO
    ) -> Path:
        safe_suffix = _sanitize_suffix(suffix)
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        candidate: Optional[Path] = None
        fd: Optional[int] = None
        for _ in range(5):
            candidate = run_dir / f"f_{secrets.token_hex(8)}{safe_suffix}"
            try:
                fd = os.open(candidate, flags, 0o600)
                break
            except FileExistsError:
                continue
        if fd is None or candidate is None:
            raise SessionFileRegistryError(
                "MATERIALIZE_FAILED", "Could not allocate a materialized file."
            )
        try:
            with os.fdopen(fd, "wb") as stream:
                while chunk := source.read(self._config.upload_chunk_bytes):
                    stream.write(chunk)
            resolved = self._assert_resolved_under(run_dir, candidate)
            mode = os.lstat(resolved).st_mode
            if not stat.S_ISREG(mode) or stat.S_ISLNK(mode):
                raise SessionFileRegistryError(
                    "MATERIALIZE_FAILED", "Materialized path is not a regular file."
                )
            return resolved
        except Exception:
            with contextlib.suppress(OSError):
                os.unlink(candidate)
            raise

    @staticmethod
    def _assert_resolved_under(root: Path, path: Path) -> Path:
        # NOTE: resolve()/realpath defeat symlink races at check time; creating
        # directories is only allowed for the operator-owned work root, so a
        # swapped-in symlink parent is detected here as an escape.
        resolved_root = Path(os.path.realpath(root))
        resolved_path = Path(os.path.realpath(path))
        if (
            resolved_path != resolved_root
            and resolved_root not in resolved_path.parents
        ):
            raise SessionFileRegistryError(
                "MATERIALIZE_FAILED", "Materialized path escapes the work root."
            )
        return resolved_path

    def close(self) -> None:
        """Release registry resources held for the serve lifecycle."""
