"""Persist already-authorized chat attachments for recoverable dashboard queries."""

from contextlib import ExitStack
from pathlib import Path

from fastapi import UploadFile

from dbgpt_serve.utils.auth import UserRequest


async def prepare_dashboard_files(
    *, attachment_ctx, legacy_paths, owner_id, conversation_id
):
    """Accept only paths resolved by the chat attachment/legacy ownership checks."""
    from ..python_upload_api import python_files_upload

    if attachment_ctx is not None:
        files = [
            (manifest.name, attachment_ctx.local_paths[manifest.file_id])
            for manifest in attachment_ctx.manifests
        ]
    else:
        files = [(Path(path).name, path) for path in legacy_paths]
    with ExitStack() as opened:
        uploads = [
            UploadFile(filename=name, file=opened.enter_context(open(path, "rb")))
            for name, path in files
        ]
        # Reuse bounded CSV/Excel parsing, isolation, datasource registration and
        # rollback. Durable copies outlive the per-turn temporary files.
        result = await python_files_upload(
            files=uploads,
            conv_uid=conversation_id,
            user_token=UserRequest(user_id=owner_id),
        )
    if not result.success or not result.data:
        raise ValueError(result.err_msg or "Could not prepare the uploaded dataset.")
    return result.data
