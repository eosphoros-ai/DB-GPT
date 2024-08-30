import asyncio
import logging
from functools import cache
from typing import List, Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile
from fastapi.security.http import HTTPAuthorizationCredentials, HTTPBearer
from starlette.responses import StreamingResponse

from dbgpt.component import SystemApp
from dbgpt.serve.core import Result, blocking_func_to_async
from dbgpt.util import PaginationResult

from ..config import APP_NAME, SERVE_APP_NAME, SERVE_SERVICE_COMPONENT_NAME, ServeConfig
from ..service.service import Service
from .schemas import (
    FileMetadataBatchRequest,
    FileMetadataResponse,
    ServeRequest,
    ServerResponse,
    UploadFileResponse,
)

router = APIRouter()
logger = logging.getLogger(__name__)

# Add your API endpoints here

global_system_app: Optional[SystemApp] = None


def get_service() -> Service:
    """Get the service instance"""
    return global_system_app.get_component(SERVE_SERVICE_COMPONENT_NAME, Service)


get_bearer_token = HTTPBearer(auto_error=False)


@cache
def _parse_api_keys(api_keys: str) -> List[str]:
    """Parse the string api keys to a list

    Args:
        api_keys (str): The string api keys

    Returns:
        List[str]: The list of api keys
    """
    if not api_keys:
        return []
    return [key.strip() for key in api_keys.split(",")]


async def check_api_key(
    auth: Optional[HTTPAuthorizationCredentials] = Depends(get_bearer_token),
    service: Service = Depends(get_service),
) -> Optional[str]:
    """Check the api key

    If the api key is not set, allow all.

    Your can pass the token in you request header like this:

    .. code-block:: python

        import requests

        client_api_key = "your_api_key"
        headers = {"Authorization": "Bearer " + client_api_key}
        res = requests.get("http://test/hello", headers=headers)
        assert res.status_code == 200

    """
    if service.config.api_keys:
        api_keys = _parse_api_keys(service.config.api_keys)
        if auth is None or (token := auth.credentials) not in api_keys:
            raise HTTPException(
                status_code=401,
                detail={
                    "error": {
                        "message": "",
                        "type": "invalid_request_error",
                        "param": None,
                        "code": "invalid_api_key",
                    }
                },
            )
        return token
    else:
        # api_keys not set; allow all
        return None


@router.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "ok"}


@router.get("/test_auth", dependencies=[Depends(check_api_key)])
async def test_auth():
    """Test auth endpoint"""
    return {"status": "ok"}


@router.post(
    "/files/{bucket}",
    response_model=Result[List[UploadFileResponse]],
    dependencies=[Depends(check_api_key)],
)
async def upload_files(
    bucket: str,
    files: List[UploadFile],
    user_name: Optional[str] = Query(default=None, description="user name"),
    sys_code: Optional[str] = Query(default=None, description="system code"),
    service: Service = Depends(get_service),
) -> Result[List[UploadFileResponse]]:
    """Upload files by a list of UploadFile."""
    logger.info(f"upload_files: bucket={bucket}, files={files}")
    results = await blocking_func_to_async(
        global_system_app,
        service.upload_files,
        bucket,
        "distributed",
        files,
        user_name,
        sys_code,
    )
    return Result.succ(results)


@router.get("/files/{bucket}/{file_id}", dependencies=[Depends(check_api_key)])
async def download_file(
    bucket: str, file_id: str, service: Service = Depends(get_service)
):
    """Download a file by file_id."""
    logger.info(f"download_file: bucket={bucket}, file_id={file_id}")
    file_data, file_metadata = await blocking_func_to_async(
        global_system_app, service.download_file, bucket, file_id
    )
    file_name_encoded = quote(file_metadata.file_name)

    def file_iterator(raw_iter):
        with raw_iter:
            while chunk := raw_iter.read(
                service.config.file_server_download_chunk_size
            ):
                yield chunk

    response = StreamingResponse(
        file_iterator(file_data), media_type="application/octet-stream"
    )
    response.headers[
        "Content-Disposition"
    ] = f"attachment; filename={file_name_encoded}"
    return response


@router.delete("/files/{bucket}/{file_id}", dependencies=[Depends(check_api_key)])
async def delete_file(
    bucket: str, file_id: str, service: Service = Depends(get_service)
):
    """Delete a file by file_id."""
    await blocking_func_to_async(
        global_system_app, service.delete_file, bucket, file_id
    )
    return Result.succ(None)


@router.get(
    "/files/metadata",
    response_model=Result[FileMetadataResponse],
    dependencies=[Depends(check_api_key)],
)
async def get_file_metadata(
    uri: Optional[str] = Query(None, description="File URI"),
    bucket: Optional[str] = Query(None, description="Bucket name"),
    file_id: Optional[str] = Query(None, description="File ID"),
    service: Service = Depends(get_service),
) -> Result[FileMetadataResponse]:
    """Get file metadata by URI or by bucket and file_id."""
    if not uri and not (bucket and file_id):
        raise HTTPException(
            status_code=400,
            detail="Either uri or (bucket and file_id) must be provided",
        )

    metadata = await blocking_func_to_async(
        global_system_app, service.get_file_metadata, uri, bucket, file_id
    )
    return Result.succ(metadata)


@router.post(
    "/files/metadata/batch",
    response_model=Result[List[FileMetadataResponse]],
    dependencies=[Depends(check_api_key)],
)
async def get_files_metadata_batch(
    request: FileMetadataBatchRequest, service: Service = Depends(get_service)
) -> Result[List[FileMetadataResponse]]:
    """Get metadata for multiple files by URIs or bucket and file_id pairs."""
    if not request.uris and not request.bucket_file_pairs:
        raise HTTPException(
            status_code=400,
            detail="Either uris or bucket_file_pairs must be provided",
        )

    batch_req = []
    if request.uris:
        for uri in request.uris:
            batch_req.append((uri, None, None))
    elif request.bucket_file_pairs:
        for pair in request.bucket_file_pairs:
            batch_req.append((None, pair.bucket, pair.file_id))
    else:
        raise HTTPException(
            status_code=400,
            detail="Either uris or bucket_file_pairs must be provided",
        )

    batch_req_tasks = [
        blocking_func_to_async(
            global_system_app, service.get_file_metadata, uri, bucket, file_id
        )
        for uri, bucket, file_id in batch_req
    ]

    metadata_list = await asyncio.gather(*batch_req_tasks)
    if not metadata_list:
        raise HTTPException(
            status_code=404,
            detail="File metadata not found",
        )
    return Result.succ(metadata_list)


def init_endpoints(system_app: SystemApp) -> None:
    """Initialize the endpoints"""
    global global_system_app
    system_app.register(Service)
    global_system_app = system_app
