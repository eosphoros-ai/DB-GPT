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

        upload_dir = os.path.join(base_dir, "python_uploads", user_id)
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
