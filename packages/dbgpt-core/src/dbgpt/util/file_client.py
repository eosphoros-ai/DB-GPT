import os

import aiofiles
from fastapi import File, UploadFile

from dbgpt.configs.model_config import KNOWLEDGE_UPLOAD_ROOT_PATH


class FileClient:
    def _resolve_file_path(self, file_key) -> str:
        """Resolve a file_key and ensure it stays inside the upload root.

        Prevent arbitrary file read / delete (path traversal) by requiring the
        real path of ``file_key`` to be under KNOWLEDGE_UPLOAD_ROOT_PATH. The
        resolution keeps the original relative/absolute semantics of ``open``,
        so existing callers (file preview, excel chat) are unaffected.
        """
        allowed_root = os.path.abspath(KNOWLEDGE_UPLOAD_ROOT_PATH)
        resolved_path = os.path.realpath(file_key)
        if resolved_path != allowed_root and not resolved_path.startswith(
            allowed_root + os.sep
        ):
            raise ValueError(
                f"Refuse to access file outside the upload directory: {file_key}"
            )
        return resolved_path

    def read_file(self, conv_uid, file_key, is_oss: bool = False):
        # File path
        with open(self._resolve_file_path(file_key), "rb") as file:
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
        upload_path = os.path.join(upload_dir, doc_file.filename)
        async with aiofiles.open(upload_path, "wb") as f:
            await f.write(await doc_file.read())

        return False, upload_path

    async def delete_file(self, conv_uid, file_key, is_oss: bool = False):
        # File path
        file_path = self._resolve_file_path(file_key)
        if os.path.exists(file_path):
            os.remove(file_path)
