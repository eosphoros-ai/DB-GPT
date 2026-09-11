import os
from pathlib import Path

import aiofiles
from fastapi import File, UploadFile

from dbgpt.configs.model_config import KNOWLEDGE_UPLOAD_ROOT_PATH


def _resolve_conv_file_path(conv_uid: str, file_key: str) -> Path:
    if not conv_uid:
        raise ValueError("conv_uid is required")
    if not file_key:
        raise ValueError("file_key is required")
    if "\x00" in str(file_key):
        raise ValueError("file_key must not contain null bytes")

    upload_dir = (Path(KNOWLEDGE_UPLOAD_ROOT_PATH) / str(conv_uid)).resolve()
    candidate = Path(file_key)
    if candidate.is_absolute():
        resolved = candidate.resolve()
    else:
        resolved = (upload_dir / candidate).resolve()
    try:
        resolved.relative_to(upload_dir)
    except ValueError as exc:
        raise ValueError("file_key must stay inside conversation upload directory") from exc
    return resolved


class FileClient:
    def read_file(self, conv_uid, file_key, is_oss: bool = False):
        file_path = _resolve_conv_file_path(conv_uid, file_key)
        with open(file_path, "rb") as file:
            content = file.read()
        return content

    async def write_file(
        self,
        conv_uid,
        doc_file: UploadFile = File(...),
        is_increment: bool = False,
    ):
        file_key = f"{conv_uid}"
        # Save the uploaded file
        upload_dir = os.path.join(KNOWLEDGE_UPLOAD_ROOT_PATH, file_key)
        os.makedirs(upload_dir, exist_ok=True)
        upload_path = _resolve_conv_file_path(conv_uid, doc_file.filename)
        async with aiofiles.open(upload_path, "wb") as f:
            await f.write(await doc_file.read())

        return False, str(upload_path)

    async def delete_file(self, conv_uid, file_key, is_oss: bool = False):
        file_path = _resolve_conv_file_path(conv_uid, file_key)
        if os.path.exists(file_path):
            os.remove(file_path)
