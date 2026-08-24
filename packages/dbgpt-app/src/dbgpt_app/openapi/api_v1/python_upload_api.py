import logging
import os
import re
import stat
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from dbgpt._private.config import Config
from dbgpt_app.openapi.api_view_model import Result
from dbgpt_serve.utils.auth import UserRequest, get_user_from_headers

router = APIRouter()
CFG = Config()
logger = logging.getLogger(__name__)

_UPLOAD_CHUNK_BYTES = 64 * 1024

# Only allow alphanumeric characters, underscores and hyphens in user_id.
# This prevents path traversal via "../" or path separators in the header.
_SAFE_USER_ID_RE = re.compile(r"^[A-Za-z0-9_\-]+$")


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


def _resolve_upload_path(owner_root: Path, filename: str) -> Path:
    """Resolve an upload target confined to the authenticated owner root.

    Absolute paths, ``..`` traversal and Windows separators are rejected,
    and no path component between the owner root and the target may be a
    symlink, so uploads never escape the owner root and never overwrite
    through renamed symlink targets.
    """
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
