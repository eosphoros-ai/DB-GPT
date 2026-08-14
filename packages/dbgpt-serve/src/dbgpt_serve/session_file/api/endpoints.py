"""Owner-aware session file API transport.

The router is intentionally self-contained: domain errors are converted to
``Result`` envelopes by a custom route class, so mounting the router never
depends on app-level exception handlers. Storage orchestration (quota locks,
streaming ingest compensation, materialization, task/session copy) is
implemented by the future registry behind :class:`SessionFileServiceLike`;
until ``init_endpoints`` binds a service, every storage-backed endpoint fails
closed with ``SESSION_FILE_SERVICE_UNAVAILABLE``.
"""

import json
import logging
import tempfile
from functools import cache
from typing import BinaryIO, List, Optional, Protocol, Tuple, Union
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, Header, Query, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.routing import APIRoute
from fastapi.security.http import HTTPAuthorizationCredentials, HTTPBearer
from starlette.concurrency import run_in_threadpool
from starlette.requests import Request

from dbgpt.component import SystemApp
from dbgpt_serve.core import Result

from ..config import ServeConfig
from ..domain import SessionFilePrivateRecord, SessionFileStatus
from ..registry import _MAX_COMPONENT_BYTES, SessionFileRegistryError
from .schemas import (
    SessionFileCapabilitiesResponse,
    SessionFileErrorCode,
    SessionFilePreviewResponse,
    SessionFileResponse,
)

logger = logging.getLogger(__name__)


class SessionFileApiError(Exception):
    """Deterministic transport error carrying a stable domain code."""

    def __init__(
        self,
        status_code: int,
        code: Union[SessionFileErrorCode, str],
        message: str,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.err_code = code.value if isinstance(code, SessionFileErrorCode) else code
        self.message = message


class _SessionFileApiRoute(APIRoute):
    """Route class converting :class:`SessionFileApiError` to envelopes."""

    def get_route_handler(self):
        original_handler = super().get_route_handler()

        async def handler(request: Request):
            try:
                return await original_handler(request)
            except SessionFileApiError as error:
                return JSONResponse(
                    status_code=error.status_code,
                    content=Result.failed(
                        msg=error.message, err_code=error.err_code
                    ).to_dict(),
                )

        return handler


router = APIRouter(route_class=_SessionFileApiRoute)


class SessionFileServiceLike(Protocol):
    """Storage orchestration seam implemented by the session file registry."""

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
        """Persist one transport-validated upload for the owner scope."""
        ...

    def list_files(
        self, *, owner_id: str, session_id: str
    ) -> List[SessionFilePrivateRecord]:
        """List an owner's session files in stable upload order."""
        ...

    def get_file(
        self, *, owner_id: str, session_id: str, file_id: str
    ) -> Optional[SessionFilePrivateRecord]:
        """Return a file for the exact owner scope, otherwise ``None``."""
        ...

    def open_download(
        self, *, owner_id: str, session_id: str, file_id: str
    ) -> Optional[Tuple[BinaryIO, SessionFilePrivateRecord]]:
        """Open the stored bytes for an exact owner scope."""
        ...

    def delete_file(self, *, owner_id: str, session_id: str, file_id: str) -> bool:
        """Delete a file for the exact owner scope."""
        ...


global_system_app: Optional[SystemApp] = None
_service_instance: Optional[SessionFileServiceLike] = None
_config_instance: Optional[ServeConfig] = None


def init_endpoints(
    system_app: SystemApp,
    service: SessionFileServiceLike,
    config: Optional[ServeConfig] = None,
) -> None:
    """Bind the storage service and config called by the Serve layer."""
    global global_system_app, _service_instance, _config_instance
    global_system_app = system_app
    _service_instance = service
    _config_instance = config or ServeConfig()


def _reset_endpoints() -> None:
    """Unbind module state; used by tests and lifecycle teardown."""
    global global_system_app, _service_instance, _config_instance
    global_system_app = None
    _service_instance = None
    _config_instance = None


def get_session_file_service() -> SessionFileServiceLike:
    """FastAPI dependency returning the bound storage service, failing closed."""
    if _service_instance is None:
        raise SessionFileApiError(
            503,
            SessionFileErrorCode.SESSION_FILE_SERVICE_UNAVAILABLE,
            "Session file storage is not available.",
        )
    return _service_instance


def get_session_file_config() -> ServeConfig:
    """FastAPI dependency returning server-owned limits."""
    return _config_instance or ServeConfig()


_get_bearer_token = HTTPBearer(auto_error=False)


@cache
def _parse_api_keys(api_keys: str) -> List[str]:
    """Parse the string api keys to a list.

    Mirrors ``dbgpt_serve.file.api.endpoints._parse_api_keys`` so the
    session file routes consume configured api_keys the same way.
    """
    if not api_keys:
        return []
    return [key.strip() for key in api_keys.split(",")]


async def check_api_key(
    auth: Optional[HTTPAuthorizationCredentials] = Depends(_get_bearer_token),
    config: ServeConfig = Depends(get_session_file_config),
) -> Optional[str]:
    """Check the Bearer token against the configured api_keys.

    If the api key is not set, allow all. Aligned with
    ``dbgpt_serve.file.api.endpoints.check_api_key``.
    """
    if config.api_keys:
        api_keys = _parse_api_keys(config.api_keys)
        if auth is None or auth.credentials not in api_keys:
            raise SessionFileApiError(
                401,
                SessionFileErrorCode.MISSING_AUTH_OWNER,
                "A valid API key is required.",
            )
        return auth.credentials
    return None


def get_authenticated_owner(
    user_id: Optional[str] = Header(None),
    _checked_key: Optional[str] = Depends(check_api_key),
    config: ServeConfig = Depends(get_session_file_config),
) -> str:
    """Resolve the owner strictly from headers; never from the client.

    When the server has ``api_keys`` configured, a missing or blank
    ``user-id`` header is always a 401 and owners are capped at the
    persistence/materialization scope-component limit. When the server runs
    without ``api_keys`` (anonymous lightweight deployments), a missing or
    blank ``user-id`` header falls back to the codebase-wide shared owner
    ``"001"``, mirroring ``get_user_from_headers`` so the module behaves
    identically to every other serve in that mode.
    """
    owner = user_id.strip() if user_id else ""
    if not owner:
        if config.api_keys:
            raise SessionFileApiError(
                401,
                SessionFileErrorCode.MISSING_AUTH_OWNER,
                "An authenticated owner is required.",
            )
        owner = "001"
    if (
        len(owner) > _MAX_COMPONENT_BYTES
        or len(owner.encode("utf-8")) > _MAX_COMPONENT_BYTES
    ):
        raise SessionFileApiError(
            401,
            SessionFileErrorCode.MISSING_AUTH_OWNER,
            "The authenticated owner is invalid.",
        )
    return owner


def _require_session_id(raw_session_id: Optional[str]) -> str:
    if raw_session_id is None:
        raise SessionFileApiError(
            400,
            SessionFileErrorCode.MISSING_SESSION_ID,
            "A session_id is required.",
        )
    session_id = raw_session_id.strip()
    if not session_id:
        raise SessionFileApiError(
            400,
            SessionFileErrorCode.INVALID_SESSION_ID,
            "The session_id is invalid.",
        )
    if (
        "\x00" in session_id
        or "/" in session_id
        or "\\" in session_id
        or session_id in (".", "..")
        or len(session_id.encode("utf-8")) > _MAX_COMPONENT_BYTES
    ):
        raise SessionFileApiError(
            400,
            SessionFileErrorCode.INVALID_SESSION_ID,
            "The session_id is invalid.",
        )
    return session_id


_REGISTRY_STATUS_BY_CODE = {
    "FILE_TOO_LARGE": 413,
    "BATCH_TOO_LARGE": 413,
    "TOO_MANY_FILES": 400,
    "SIZE_MISMATCH": 400,
    "QUOTA_EXCEEDED": 409,
    "QUOTA_LOCK_TIMEOUT": 503,
    "MATERIALIZE_FAILED": 500,
    "FINALIZE_FAILED": 500,
}


def _translate_registry_error(
    error: SessionFileRegistryError,
) -> SessionFileApiError:
    """Map one registry code to a stable HTTP status and envelope code."""
    status = _REGISTRY_STATUS_BY_CODE.get(error.code)
    if status is not None:
        return SessionFileApiError(status, error.code, error.message)
    if error.code.startswith("INVALID_"):
        return SessionFileApiError(400, error.code, error.message)
    logger.warning("Unmapped session file registry code: %s", error.code)
    return SessionFileApiError(
        500,
        SessionFileErrorCode.SESSION_FILE_INTERNAL,
        "Session file operation failed.",
    )


async def _rollback_ingested(
    service: SessionFileServiceLike,
    owner_id: str,
    session_id: str,
    records: List[SessionFilePrivateRecord],
) -> None:
    """Delete files ingested earlier in the same failed upload request."""
    for record in reversed(records):
        try:
            await run_in_threadpool(
                service.delete_file,
                owner_id=owner_id,
                session_id=session_id,
                file_id=record.file_id,
            )
        except Exception:
            logger.exception("Failed to roll back session file %s", record.file_id)


async def _fetch_required_file(
    service: SessionFileServiceLike,
    owner_id: str,
    session_id: str,
    file_id: str,
) -> SessionFilePrivateRecord:
    """Fetch or 404 off the event loop, mapping registry codes."""
    try:
        return await run_in_threadpool(
            _get_required_file, service, owner_id, session_id, file_id
        )
    except SessionFileRegistryError as error:
        raise _translate_registry_error(error) from error


def _validate_display_name(filename: Optional[str], config: ServeConfig) -> str:
    if not filename or not filename.strip():
        raise SessionFileApiError(
            400,
            SessionFileErrorCode.INVALID_FILE_NAME,
            "Every upload must include a file name.",
        )
    if "\x00" in filename or "/" in filename or "\\" in filename:
        raise SessionFileApiError(
            400,
            SessionFileErrorCode.INVALID_FILE_NAME,
            "The file name is invalid.",
        )
    if len(filename.encode("utf-8")) > config.max_file_name_bytes:
        raise SessionFileApiError(
            400,
            SessionFileErrorCode.FILE_NAME_TOO_LONG,
            f"File name exceeds {config.max_file_name_bytes} bytes: {filename}",
        )
    return filename


async def _spool_upload(
    upload: UploadFile, config: ServeConfig
) -> Tuple[BinaryIO, int]:
    """Stream one upload into a spool, enforcing the per-file size cap."""
    spool = tempfile.SpooledTemporaryFile(max_size=config.upload_spool_bytes)
    size = 0
    while chunk := await upload.read(config.upload_chunk_bytes):
        size += len(chunk)
        if size > config.max_file_bytes:
            spool.close()
            raise SessionFileApiError(
                413,
                SessionFileErrorCode.FILE_TOO_LARGE,
                f"File exceeds {config.max_file_bytes} bytes: {upload.filename}",
            )
        spool.write(chunk)
    spool.seek(0)
    return spool, size


def _get_required_file(
    service: SessionFileServiceLike,
    owner_id: str,
    session_id: str,
    file_id: str,
) -> SessionFilePrivateRecord:
    record = service.get_file(owner_id=owner_id, session_id=session_id, file_id=file_id)
    if record is None:
        raise SessionFileApiError(
            404,
            SessionFileErrorCode.SESSION_FILE_NOT_FOUND,
            "File not found.",
        )
    return record


@router.post("", response_model=Result[List[SessionFileResponse]])
async def upload_session_files(
    session_id: Optional[str] = Form(None),
    files: Optional[List[UploadFile]] = File(None),
    owner_id: str = Depends(get_authenticated_owner),
    service: SessionFileServiceLike = Depends(get_session_file_service),
    config: ServeConfig = Depends(get_session_file_config),
):
    """Upload 1..N files for a session; each returns a public manifest."""
    session = _require_session_id(session_id)
    if not files:
        raise SessionFileApiError(
            400,
            SessionFileErrorCode.EMPTY_FILE_UPLOAD,
            "At least one file is required.",
        )
    if len(files) > config.max_files_per_upload:
        raise SessionFileApiError(
            400,
            SessionFileErrorCode.TOO_MANY_FILES,
            f"At most {config.max_files_per_upload} files per upload.",
        )

    spooled: List[Tuple[BinaryIO, str, Optional[str], int]] = []
    total_bytes = 0
    for upload in files:
        name = _validate_display_name(upload.filename, config)
        spool, size = await _spool_upload(upload, config)
        total_bytes += size
        if total_bytes > config.max_upload_bytes:
            spool.close()
            raise SessionFileApiError(
                413,
                SessionFileErrorCode.REQUEST_TOO_LARGE,
                f"Upload exceeds {config.max_upload_bytes} bytes in total.",
            )
        if size == 0:
            spool.close()
            raise SessionFileApiError(
                400,
                SessionFileErrorCode.EMPTY_FILE,
                f"Empty file: {name}",
            )
        spooled.append((spool, name, upload.content_type, size))

    responses: List[SessionFileResponse] = []
    ingested: List[SessionFilePrivateRecord] = []
    try:
        for spool, name, media_type, size in spooled:
            record = await run_in_threadpool(
                service.ingest,
                owner_id=owner_id,
                session_id=session,
                display_name=name,
                media_type=media_type,
                stream=spool,
                size_bytes=size,
            )
            ingested.append(record)
            responses.append(SessionFileResponse.from_private_record(record))
    except Exception as error:
        # Any failure rolls back files ingested earlier in this request so
        # a client retry never duplicates earlier successes.
        await _rollback_ingested(service, owner_id, session, ingested)
        if isinstance(error, SessionFileApiError):
            raise
        if isinstance(error, SessionFileRegistryError):
            raise _translate_registry_error(error) from error
        logger.exception("Session file ingest failed")
        raise SessionFileApiError(
            500,
            SessionFileErrorCode.SESSION_FILE_INTERNAL,
            "Session file ingest failed.",
        ) from error
    finally:
        for spool, _, _, _ in spooled:
            spool.close()
    return Result.succ(responses)


@router.get("", response_model=Result[List[SessionFileResponse]])
async def list_session_files(
    session_id: Optional[str] = Query(None),
    owner_id: str = Depends(get_authenticated_owner),
    service: SessionFileServiceLike = Depends(get_session_file_service),
):
    """List an owner's session files in stable upload order."""
    session = _require_session_id(session_id)
    try:
        records = await run_in_threadpool(
            service.list_files, owner_id=owner_id, session_id=session
        )
    except SessionFileRegistryError as error:
        raise _translate_registry_error(error) from error
    return Result.succ(
        [
            SessionFileResponse.from_private_record(record)
            for record in records
            if record is not None
        ]
    )


@router.get("/capabilities", response_model=Result[SessionFileCapabilitiesResponse])
async def get_capabilities(
    owner_id: str = Depends(get_authenticated_owner),
    config: ServeConfig = Depends(get_session_file_config),
):
    """Expose server-owned upload limits and parser capabilities."""
    del owner_id  # Authentication only; capabilities are not owner specific.
    return Result.succ(SessionFileCapabilitiesResponse.from_config(config))


@router.get("/{file_id}", response_model=Result[SessionFileResponse])
async def get_session_file(
    file_id: str,
    session_id: Optional[str] = Query(None),
    owner_id: str = Depends(get_authenticated_owner),
    service: SessionFileServiceLike = Depends(get_session_file_service),
):
    """Return public metadata for an owner-scoped file."""
    session = _require_session_id(session_id)
    record = await _fetch_required_file(service, owner_id, session, file_id)
    return Result.succ(SessionFileResponse.from_private_record(record))


@router.get("/{file_id}/preview", response_model=Result[SessionFilePreviewResponse])
async def preview_session_file(
    file_id: str,
    session_id: Optional[str] = Query(None),
    owner_id: str = Depends(get_authenticated_owner),
    service: SessionFileServiceLike = Depends(get_session_file_service),
):
    """Return bounded inspection preview data for an owner-scoped file."""
    session = _require_session_id(session_id)
    record = await _fetch_required_file(service, owner_id, session, file_id)
    if record.status in (SessionFileStatus.UPLOADING, SessionFileStatus.INSPECTING):
        raise SessionFileApiError(
            409,
            SessionFileErrorCode.PREVIEW_NOT_READY,
            "File preview is not ready yet.",
        )
    if record.status == SessionFileStatus.FAILED:
        raise SessionFileApiError(
            409,
            SessionFileErrorCode.SESSION_FILE_FAILED,
            "File processing failed.",
        )
    inspection: Optional[dict] = None
    if record.inspection_json:
        try:
            loaded = json.loads(record.inspection_json)
        except ValueError as error:
            logger.exception("Invalid inspection payload for %s", record.file_id)
            raise SessionFileApiError(
                500,
                SessionFileErrorCode.SESSION_FILE_INTERNAL,
                "Stored preview data is invalid.",
            ) from error
        if isinstance(loaded, dict):
            inspection = loaded
    if inspection is None:
        raise SessionFileApiError(
            409,
            SessionFileErrorCode.PREVIEW_NOT_READY,
            "File preview is not ready yet.",
        )
    preview = inspection.get("preview")
    if not isinstance(preview, dict):
        preview = {}
    return Result.succ(
        SessionFilePreviewResponse(
            file_id=record.file_id,
            name=record.display_name,
            media_type=record.media_type,
            kind=record.file_kind,
            status=record.status.value,
            truncated=bool(inspection.get("truncated")),
            preview=preview,
            error_code=record.error_code,
        )
    )


@router.get("/{file_id}/download")
async def download_session_file(
    file_id: str,
    session_id: Optional[str] = Query(None),
    owner_id: str = Depends(get_authenticated_owner),
    service: SessionFileServiceLike = Depends(get_session_file_service),
    config: ServeConfig = Depends(get_session_file_config),
):
    """Stream stored bytes as an attachment for an owner-scoped file."""
    session = _require_session_id(session_id)
    try:
        opened = await run_in_threadpool(
            service.open_download,
            owner_id=owner_id,
            session_id=session,
            file_id=file_id,
        )
    except SessionFileRegistryError as error:
        raise _translate_registry_error(error) from error
    if opened is None:
        raise SessionFileApiError(
            404,
            SessionFileErrorCode.SESSION_FILE_NOT_FOUND,
            "File not found.",
        )
    stream, record = opened

    def file_iterator(source: BinaryIO):
        with source:
            while chunk := source.read(config.download_chunk_bytes):
                yield chunk

    response = StreamingResponse(
        file_iterator(stream), media_type="application/octet-stream"
    )
    response.headers["Content-Disposition"] = (
        f"attachment; filename*=UTF-8''{quote(record.display_name)}"
    )
    return response


@router.delete("/{file_id}", response_model=Result[dict])
async def delete_session_file(
    file_id: str,
    session_id: Optional[str] = Query(None),
    owner_id: str = Depends(get_authenticated_owner),
    service: SessionFileServiceLike = Depends(get_session_file_service),
):
    """Delete an owner-scoped session file and its stored bytes."""
    session = _require_session_id(session_id)
    try:
        deleted = await run_in_threadpool(
            service.delete_file,
            owner_id=owner_id,
            session_id=session,
            file_id=file_id,
        )
    except SessionFileRegistryError as error:
        raise _translate_registry_error(error) from error
    if not deleted:
        raise SessionFileApiError(
            404,
            SessionFileErrorCode.SESSION_FILE_NOT_FOUND,
            "File not found.",
        )
    return Result.succ({"file_id": file_id})
