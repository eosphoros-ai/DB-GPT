import os

import aiofiles
from fastapi import File, UploadFile

from dbgpt.configs.model_config import KNOWLEDGE_UPLOAD_ROOT_PATH


class FileClient:
    def read_file(self, conv_uid, file_key, is_oss: bool = False):
        # File path
        with open(file_key, "rb") as file:
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
        if os.path.exists(file_key):
            os.remove(file_key)
