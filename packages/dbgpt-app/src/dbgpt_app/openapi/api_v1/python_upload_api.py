import logging
import os
from pathlib import Path

from fastapi import APIRouter, Depends, File, UploadFile

from dbgpt._private.config import Config
from dbgpt_app.openapi.api_view_model import Result
from dbgpt_serve.utils.auth import UserRequest, get_user_from_headers

router = APIRouter()
CFG = Config()
logger = logging.getLogger(__name__)


def _resolve_upload_dir(base_dir: str, user_id: str) -> str:
    """Resolve the per-user upload directory under ``python_uploads``.

    ``user_id`` originates from an untrusted request header, so it must be
    treated as a single, opaque directory name. Rejecting anything that is not
    a single non-".."/non-absolute path segment (and verifying containment)
    prevents path traversal such as ``user_id: ../../../tmp`` from escaping the
    uploads root and writing files to arbitrary locations on the server.
    """
    uploads_root = (Path(base_dir) / "python_uploads").resolve()
    user_path = Path(user_id)
    if user_path.is_absolute() or len(user_path.parts) != 1 or user_id in (".", ".."):
        raise ValueError("user_id must be a single safe path segment")

    upload_dir = (uploads_root / user_path).resolve()
    try:
        upload_dir.relative_to(uploads_root)
    except ValueError as exc:
        raise ValueError("user_id must stay inside the uploads directory") from exc
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

        user_id = user_token.user_id or "default"
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
        except ValueError:
            return Result.failed(msg="Invalid user identifier")
        os.makedirs(upload_dir, exist_ok=True)

        file_path = _resolve_upload_path(upload_dir, file.filename)

        # Read file content and write to disk
        content = await file.read()
        if not content:
            return Result.failed(msg="Uploaded file is empty")

        with open(file_path, "wb") as buffer:
            buffer.write(content)

        abs_path = os.path.abspath(file_path)
        logger.info(f"File uploaded successfully to {abs_path} ({len(content)} bytes)")

        return Result.succ(abs_path)
    except Exception as e:
        logger.exception(f"File upload failed: {e}")
        return Result.failed(msg=f"Upload error: {str(e)}")
