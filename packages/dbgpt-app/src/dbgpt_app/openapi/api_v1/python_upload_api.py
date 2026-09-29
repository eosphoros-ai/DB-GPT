import logging
import os
import re
import shutil
import stat
import uuid
from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile

from dbgpt._private.config import Config
from dbgpt_app.openapi.api_v1.uploaded_dataset import materialize_uploaded_dataset
from dbgpt_app.openapi.api_v1.uploaded_dataset_registry import (
    UploadedDatasetAccessError,
    UploadedDatasetNotFoundError,
    UploadedDatasetService,
)
from dbgpt_app.openapi.api_view_model import Result
from dbgpt_serve.utils.auth import UserRequest, get_user_from_headers

router = APIRouter()
CFG = Config()
logger = logging.getLogger(__name__)

_UPLOAD_CHUNK_BYTES = 64 * 1024

# Only allow alphanumeric characters, underscores and hyphens in user_id.
# This prevents path traversal via "../" or path separators in the header.
_SAFE_USER_ID_RE = re.compile(r"^[A-Za-z0-9_\-]+$")
_MAX_BATCH_FILES = 16
_MAX_FILE_BYTES = 64 * 1024 * 1024
_MAX_BATCH_BYTES = 256 * 1024 * 1024


def _get_uploaded_dataset_service() -> UploadedDatasetService:
    return UploadedDatasetService()


def _resolve_user_id(user_id: str) -> str:
    """Validate the user_id so it cannot be used for path traversal.

    The user_id is sourced from an HTTP header and used as a path component
    of the upload directory, so it must only contain safe characters.
    """
    if not user_id or not isinstance(user_id, str):
        return "default"
    if not user_id.strip():
        return "default"
    if not _SAFE_USER_ID_RE.fullmatch(user_id):
        raise ValueError(
            "Invalid user_id: only alphanumeric characters, underscores and "
            "hyphens are allowed"
        )
    return user_id


def _resolve_owner_root(base_dir: str, owner_id: str) -> Path:
    """Resolve the owner-only upload root, rejecting escapes.

    The owner id must be a single safe path component: no separators, nulls
    or dot components, so ``python_uploads/<owner>`` can never traverse into
    another owner's root or an arbitrary absolute directory. A pre-planted
    symlinked owner root that resolves outside ``python_uploads`` is
    rejected as well.
    """
    if (
        not owner_id
        or owner_id in (".", "..")
        or "\x00" in owner_id
        or "/" in owner_id
        or "\\" in owner_id
    ):
        raise ValueError("owner id is invalid")

    base_path = Path(base_dir).resolve()
    uploads_root = (base_path / "python_uploads").resolve()
    _assert_inside(base_path, uploads_root)
    uploads_root.mkdir(parents=True, exist_ok=True)

    owner_root = (uploads_root / owner_id).resolve()
    _assert_inside(uploads_root, owner_root)
    owner_root.mkdir(parents=True, exist_ok=True)
    # Re-verify after creation to catch a parent swapped mid-flight.
    resolved = (uploads_root / owner_id).resolve()
    _assert_inside(uploads_root, resolved)
    return resolved


def _assert_inside(root: Path, path: Path) -> None:
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ValueError("path must stay inside the owner upload root") from exc


def _resolve_upload_dir(base_dir: str, user_id: str) -> Path:
    """Compatibility entry point for dataset batches and bundled examples."""
    owner = _resolve_user_id(user_id)
    if os.path.islink(Path(base_dir, "python_uploads", owner)):
        raise ValueError("owner upload root must not be a symlink")
    return _resolve_owner_root(base_dir, owner)


def _resolve_upload_path(owner_root: Path, filename: str) -> Path:
    """Resolve an upload target confined to the authenticated owner root.

    Absolute paths, ``..`` traversal and Windows separators are rejected,
    and no path component between the owner root and the target may be a
    symlink, so uploads never escape the owner root and never overwrite
    through renamed symlink targets.
    """
    owner_root = Path(owner_root).resolve()
    if "\x00" in filename or "\\" in filename:
        raise ValueError("filename contains invalid characters")
    filename_path = Path(filename)
    if filename_path.is_absolute():
        raise ValueError("filename must be a relative path inside upload directory")

    # Walk the lexical (unresolved) components first: any symlink between
    # the owner root and the target is rejected before resolve() can follow
    # it, so uploads never overwrite through renamed symlink targets.
    probe = owner_root
    for part in filename_path.parts:
        probe = probe / part
        if os.path.islink(probe):
            raise ValueError("path must not traverse symlinks")

    file_path = probe.resolve()
    _assert_inside(owner_root, file_path)
    return file_path


def _validate_batch_filename(filename: str) -> str:
    """Return a safe leaf filename for one item in a multi-file upload."""

    if not filename or not isinstance(filename, str):
        raise ValueError("filename is empty")
    if filename in {".", ".."} or "/" in filename or "\\" in filename:
        raise ValueError("batch filenames must not contain path separators")
    filename_path = Path(filename)
    if filename_path.is_absolute() or filename_path.name != filename:
        raise ValueError("batch filenames must be plain file names")
    return filename


def _safe_remove_batch_dir(batch_dir: Path, upload_dir: Path) -> None:
    """Remove a failed generated batch directory without escaping uploads."""

    try:
        resolved_batch = batch_dir.resolve()
        resolved_upload = upload_dir.resolve()
        resolved_batch.relative_to(resolved_upload)
    except (OSError, ValueError):
        logger.error(
            "Refusing to clean upload path outside user directory: %s", batch_dir
        )
        return
    if resolved_batch.name.startswith("batch-"):
        shutil.rmtree(resolved_batch, ignore_errors=True)


def _register_uploaded_dataset(
    database_name: str,
    database_path: Path,
    user_id: str,
) -> None:
    """Register one generated SQLite dataset with DB-GPT's datasource manager.

    The storage DAO used by the upstream project logs and swallows insert
    errors, so registration is verified explicitly before returning success.
    This keeps a later Agent turn from receiving a database name that cannot
    actually be opened.
    """

    if CFG.SYSTEM_APP is None:
        raise RuntimeError("DB-GPT system application is not initialized")

    from dbgpt_serve.datasource.manages import ConnectorManager

    manager = ConnectorManager.get_instance(CFG.SYSTEM_APP)
    if manager.storage.get_by_names(database_name) is not None:
        raise ValueError(f"Generated datasource already exists: {database_name}")

    try:
        manager.storage.add_file_db(
            database_name,
            "sqlite",
            str(database_path),
            comment=(
                "Generated from one bounded multi-file upload. Relationship "
                "candidates are hints and must be validated before joining."
            ),
            user_id=user_id,
        )
        if manager.storage.get_by_names(database_name) is None:
            raise RuntimeError("Uploaded dataset could not be registered")
        manager.invalidate_connector(database_name)
    except Exception:
        # The upstream DAO may insert successfully and then fail while the
        # connector cache is being invalidated. Do not leave metadata pointing
        # at a batch directory that the endpoint will remove during rollback.
        try:
            if manager.storage.get_by_names(database_name) is not None:
                manager.storage.delete_db(database_name)
        except Exception:
            logger.exception(
                "Failed to roll back datasource metadata for %s", database_name
            )
        try:
            manager.invalidate_connector(database_name)
        except Exception:
            logger.exception(
                "Failed to invalidate rolled-back datasource %s", database_name
            )
        raise


def _unregister_uploaded_dataset(database_name: str) -> None:
    """Best-effort rollback for a generated datasource registration."""

    if CFG.SYSTEM_APP is None:
        return
    from dbgpt_serve.datasource.manages import ConnectorManager

    manager = ConnectorManager.get_instance(CFG.SYSTEM_APP)
    try:
        if manager.storage.get_by_names(database_name) is not None:
            manager.storage.delete_db(database_name)
    finally:
        try:
            manager.invalidate_connector(database_name)
        except Exception:
            logger.exception(
                "Failed to invalidate rolled-back datasource %s", database_name
            )


@router.post("/v1/python/file/upload", response_model=Result[str])
async def python_file_upload(
    file: UploadFile = File(...),
    user_token: UserRequest = Depends(get_user_from_headers),
):
    try:
        if not file or not file.filename:
            return Result.failed(msg="No file provided or filename is empty")

        try:
            user_id = _resolve_user_id(user_token.user_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        logger.info(
            f"Uploading file: {file.filename}, content_type: {file.content_type}, "
            f"user: {user_id}"
        )

        # Determine upload base directory
        base_dir = os.getcwd()
        if (
            CFG.SYSTEM_APP
            and hasattr(CFG.SYSTEM_APP, "work_dir")
            and CFG.SYSTEM_APP.work_dir
        ):
            base_dir = CFG.SYSTEM_APP.work_dir

        try:
            owner_root = _resolve_owner_root(base_dir, user_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        try:
            file_path = _resolve_upload_path(owner_root, file.filename)
        except ValueError as exc:
            return Result.failed(msg=str(exc))

        # Empty uploads are rejected before the target file is touched, so
        # an existing regular file is never truncated by an empty request.
        first_chunk = await file.read(_UPLOAD_CHUNK_BYTES)
        if not first_chunk:
            return Result.failed(msg="Uploaded file is empty")

        # Stream the upload in bounded chunks; O_NOFOLLOW (when available)
        # guarantees the open path itself is not a symlink swap-in.
        open_flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
        if hasattr(os, "O_NOFOLLOW"):
            open_flags |= os.O_NOFOLLOW
        fd = os.open(str(file_path), open_flags, 0o600)
        total_bytes = 0
        with os.fdopen(fd, "wb") as buffer:
            buffer.write(first_chunk)
            total_bytes += len(first_chunk)
            while chunk := await file.read(_UPLOAD_CHUNK_BYTES):
                buffer.write(chunk)
                total_bytes += len(chunk)

        # Post-write verification: the accepted file must stay a resolved,
        # regular, non-symlink file under the authenticated owner root.
        resolved = Path(os.path.realpath(file_path))
        _assert_inside(owner_root, resolved)
        mode = os.lstat(resolved).st_mode
        if not stat.S_ISREG(mode) or stat.S_ISLNK(mode):
            raise ValueError("uploaded path is not a regular file")

        abs_path = str(resolved)
        logger.info(f"File uploaded successfully to {abs_path} ({total_bytes} bytes)")

        return Result.succ(abs_path)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"File upload failed: {e}")
        return Result.failed(msg=f"Upload error: {str(e)}")


@router.post("/v1/python/files/upload", response_model=Result[Dict[str, Any]])
async def python_files_upload(
    files: List[UploadFile] = File(...),
    conv_uid: str = Form(...),
    user_token: UserRequest = Depends(get_user_from_headers),
):
    """Upload a bounded group of files as one isolated analysis dataset.

    The single-file endpoint remains unchanged. Batch uploads are placed in a
    unique per-request directory so equal filenames from separate datasets do
    not overwrite each other and table relationships can be reasoned about as
    one stable group.
    """

    batch_dir: Path | None = None
    upload_dir_path: Path | None = None
    registered_database_name: str | None = None
    registered_dataset_id: str | None = None
    user_id: str | None = None
    try:
        if not files:
            return Result.failed(msg="No files provided")
        if not isinstance(conv_uid, str) or not conv_uid.strip() or len(conv_uid) > 255:
            return Result.failed(msg="A valid conversation id is required")
        conv_uid = conv_uid.strip()
        if len(files) > _MAX_BATCH_FILES:
            return Result.failed(
                msg=f"Too many files: maximum {_MAX_BATCH_FILES} files per batch"
            )

        try:
            user_id = _resolve_user_id(user_token.user_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        safe_names: List[str] = []
        seen_names = set()
        for file in files:
            try:
                safe_name = _validate_batch_filename(file.filename or "")
            except ValueError as exc:
                return Result.failed(msg=f"Invalid filename: {str(exc)}")
            duplicate_key = safe_name.casefold()
            if duplicate_key in seen_names:
                return Result.failed(msg=f"Duplicate filename in batch: {safe_name}")
            seen_names.add(duplicate_key)
            safe_names.append(safe_name)

        base_dir = os.getcwd()
        if (
            CFG.SYSTEM_APP
            and hasattr(CFG.SYSTEM_APP, "work_dir")
            and CFG.SYSTEM_APP.work_dir
        ):
            base_dir = CFG.SYSTEM_APP.work_dir

        try:
            upload_dir = _resolve_upload_dir(base_dir, user_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        upload_dir_path = Path(upload_dir).resolve()
        upload_dir_path.mkdir(parents=True, exist_ok=True)
        batch_uuid = uuid.uuid4().hex
        batch_dir = (upload_dir_path / f"batch-{batch_uuid}").resolve()
        batch_dir.relative_to(upload_dir_path)
        batch_dir.mkdir()

        uploaded_paths: List[str] = []
        uploaded_file_meta: List[Dict[str, Any]] = []
        total_bytes = 0
        for file, safe_name in zip(files, safe_names):
            # Read at most one byte past the configured boundary.  This is
            # enough to reject an oversized request without first buffering
            # an arbitrarily large upload in the application process.
            content = await file.read(_MAX_FILE_BYTES + 1)
            if not content:
                raise ValueError(f"Uploaded file is empty: {safe_name}")
            if len(content) > _MAX_FILE_BYTES:
                raise ValueError(
                    f"File exceeds {_MAX_FILE_BYTES // (1024 * 1024)} MB limit: "
                    f"{safe_name}"
                )
            total_bytes += len(content)
            if total_bytes > _MAX_BATCH_BYTES:
                raise ValueError(
                    f"Batch exceeds {_MAX_BATCH_BYTES // (1024 * 1024)} MB limit"
                )

            file_path = Path(_resolve_upload_path(str(batch_dir), safe_name)).resolve()
            file_path.relative_to(batch_dir)
            with file_path.open("wb") as buffer:
                buffer.write(content)
            uploaded_paths.append(str(file_path))
            uploaded_file_meta.append(
                {
                    "file_id": uuid.uuid4().hex,
                    "name": safe_name,
                    "stored_path": str(file_path),
                    "size_bytes": len(content),
                    "content_type": file.content_type or "application/octet-stream",
                }
            )

        logger.info(
            "Uploaded %s files to %s (%s bytes)",
            len(uploaded_paths),
            batch_dir,
            total_bytes,
        )

        database_path = batch_dir / "dataset.sqlite"
        tables, relationship_candidates = materialize_uploaded_dataset(
            uploaded_paths,
            database_path,
        )
        database_name = f"upload_{user_id[:32]}_{batch_uuid[:16]}"
        _register_uploaded_dataset(database_name, database_path, user_id)
        registered_database_name = database_name

        tables_by_source: Dict[str, List[Dict[str, Any]]] = {}
        for table in tables:
            tables_by_source.setdefault(table.source_file, []).append(table.as_dict())
        for item in uploaded_file_meta:
            item["tables"] = tables_by_source.get(str(item["name"]), [])

        dataset_id = uuid.uuid4().hex
        dataset = _get_uploaded_dataset_service().register_ready(
            dataset_id=dataset_id,
            owner_id=user_id,
            conversation_id=conv_uid,
            database_name=database_name,
            database_path=database_path,
            batch_dir=batch_dir,
            files=uploaded_file_meta,
            relationships=relationship_candidates,
        )
        registered_dataset_id = dataset_id

        logger.info(
            "Registered uploaded dataset %s with %s tables and %s relationship "
            "candidates",
            database_name,
            len(tables),
            len(relationship_candidates),
        )
        return Result.succ(dataset.public_dict())
    except HTTPException:
        if registered_dataset_id is not None and user_id is not None:
            _get_uploaded_dataset_service().delete_registry_record(
                registered_dataset_id, user_id
            )
        if registered_database_name is not None:
            _unregister_uploaded_dataset(registered_database_name)
        if batch_dir is not None and upload_dir_path is not None:
            _safe_remove_batch_dir(batch_dir, upload_dir_path)
        raise
    except Exception as exc:
        if registered_dataset_id is not None and user_id is not None:
            try:
                _get_uploaded_dataset_service().delete_registry_record(
                    registered_dataset_id, user_id
                )
            except Exception:
                logger.exception("Failed to roll back uploaded dataset registry")
        if registered_database_name is not None:
            try:
                _unregister_uploaded_dataset(registered_database_name)
            except Exception:
                logger.exception(
                    "Failed to roll back datasource %s", registered_database_name
                )
        if batch_dir is not None and upload_dir_path is not None:
            _safe_remove_batch_dir(batch_dir, upload_dir_path)
        logger.exception("Batch file upload failed: %s", exc)
        return Result.failed(msg=f"Upload error: {str(exc)}")


def _owned_dataset_or_404(
    dataset_id: str,
    user_id: str,
    conversation_id: str,
):
    try:
        return _get_uploaded_dataset_service().resolve_owned(
            dataset_id, user_id, conversation_id
        )
    except (UploadedDatasetNotFoundError, UploadedDatasetAccessError) as exc:
        raise HTTPException(
            status_code=404, detail="Uploaded dataset not found"
        ) from exc


@router.get("/v1/python/datasets/by-conversation/{conv_uid}", response_model=Result)
async def latest_uploaded_dataset_for_conversation(
    conv_uid: str,
    user_token: UserRequest = Depends(get_user_from_headers),
):
    """Restore owned upload metadata when an existing conversation is reopened."""

    try:
        user_id = _resolve_user_id(user_token.user_id)
        dataset = _get_uploaded_dataset_service().latest_for_conversation(
            user_id, conv_uid
        )
        return Result.succ(dataset.public_dict() if dataset is not None else None)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/v1/python/datasets/{dataset_id}", response_model=Result)
async def get_uploaded_dataset(
    dataset_id: str,
    conv_uid: str = Query(...),
    user_token: UserRequest = Depends(get_user_from_headers),
):
    user_id = _resolve_user_id(user_token.user_id)
    dataset = _owned_dataset_or_404(dataset_id, user_id, conv_uid)
    return Result.succ(dataset.public_dict())


@router.get(
    "/v1/python/datasets/{dataset_id}/files/{file_id}/preview",
    response_model=Result,
)
async def preview_uploaded_dataset_file(
    dataset_id: str,
    file_id: str,
    conv_uid: str = Query(...),
    rows: int = Query(50, ge=1, le=100),
    user_token: UserRequest = Depends(get_user_from_headers),
):
    """Return a bounded preview after dataset, owner and conversation checks."""

    user_id = _resolve_user_id(user_token.user_id)
    try:
        preview = _get_uploaded_dataset_service().preview_file(
            dataset_id,
            file_id,
            user_id,
            conv_uid,
            row_limit=rows,
        )
    except (UploadedDatasetNotFoundError, UploadedDatasetAccessError) as exc:
        raise HTTPException(status_code=404, detail="Uploaded file not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return Result.succ(preview)
