import logging
import os
import re
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from dbgpt._private.config import Config
from dbgpt_app.openapi.api_view_model import Result
from dbgpt_serve.utils.auth import UserRequest, get_user_from_headers

router = APIRouter()
CFG = Config()
logger = logging.getLogger(__name__)

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


def _resolve_upload_dir(base_dir: str, user_id: str) -> str:
    """Build the per-user upload directory and verify it stays within
    ``<base_dir>/python_uploads`` to prevent path traversal via user_id.
    """
    base_path = Path(base_dir).resolve()
    uploads_root = (base_path / "python_uploads").resolve()
    try:
        uploads_root.relative_to(base_path)
    except ValueError as exc:
        raise ValueError(
            "python_uploads resolves to a path outside the base directory"
        ) from exc
    upload_dir = (uploads_root / user_id).resolve()
    try:
        upload_dir.relative_to(uploads_root)
    except ValueError as exc:
        raise ValueError(
            "user_id resolves to a path outside the upload directory"
        ) from exc
    return str(upload_dir)


def _resolve_upload_path(upload_dir: str, filename: str) -> str:
    upload_dir_path = Path(upload_dir).resolve()
    filename_path = Path(filename)
    if filename_path.is_absolute():
        raise ValueError("filename must be a relative path inside upload directory")

    file_path = (upload_dir_path / filename_path).resolve()
    try:
        file_path.relative_to(upload_dir_path)
    except ValueError as exc:
        raise ValueError("filename must stay inside upload directory") from exc
    return str(file_path)


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
            upload_dir = _resolve_upload_dir(base_dir, user_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        os.makedirs(upload_dir, exist_ok=True)

        file_path = _resolve_upload_path(upload_dir, file.filename)

        # Re-verify the resolved file path is still inside upload_dir after
        # directory creation.  This mitigates TOCTOU races where a symlink is
        # planted between the containment check and the actual write.
        if not Path(file_path).resolve().is_relative_to(Path(upload_dir).resolve()):
            raise HTTPException(
                status_code=400,
                detail="Resolved file path escapes the upload directory",
            )

        # Read file content and write to disk
        content = await file.read()
        if not content:
            return Result.failed(msg="Uploaded file is empty")

        with open(file_path, "wb") as buffer:
            buffer.write(content)

        abs_path = os.path.abspath(file_path)
        logger.info(f"File uploaded successfully to {abs_path} ({len(content)} bytes)")

        return Result.succ(abs_path)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"File upload failed: {e}")
        return Result.failed(msg=f"Upload error: {str(e)}")
