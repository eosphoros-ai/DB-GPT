from functools import cache
from typing import List, Optional, Union

from fastapi import (
    APIRouter,
    Depends,
    Form,
    HTTPException,
    Query,
    UploadFile,
)
from fastapi.security.http import HTTPAuthorizationCredentials, HTTPBearer

from dbgpt.component import SystemApp
from dbgpt.util import PaginationResult
from dbgpt_ext.rag.chunk_manager import ChunkParameters
from dbgpt_serve.core import Result, blocking_func_to_async
from dbgpt_serve.rag.api.schemas import (
    DocumentServeRequest,
    DocumentServeResponse,
    KnowledgeRetrieveRequest,
    KnowledgeSpaceStatsResponse,
    KnowledgeSyncRequest,
    SpaceServeRequest,
    SpaceServeResponse,
)
from dbgpt_serve.rag.config import SERVE_SERVICE_COMPONENT_NAME, ServeConfig
from dbgpt_serve.rag.service.service import Service

router = APIRouter()

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


@router.get("/health", dependencies=[Depends(check_api_key)])
async def health():
    """Health check endpoint"""
    return {"status": "ok"}


@router.get("/test_auth", dependencies=[Depends(check_api_key)])
async def test_auth():
    """Test auth endpoint"""
    return {"status": "ok"}


@router.post("/spaces")
async def create(
    request: SpaceServeRequest,
    service: Service = Depends(get_service),
) -> Result:
    """Create a new Space entity

    Args:
        request (SpaceServeRequest): The request
        service (Service): The service
    Returns:
        ServerResponse: The response
    """
    return Result.succ(service.create_space(request))


@router.put("/spaces", dependencies=[Depends(check_api_key)])
async def update(
    request: SpaceServeRequest, service: Service = Depends(get_service)
) -> Result:
    """Update a Space entity

    Args:
        request (SpaceServeRequest): The request
        service (Service): The service
    Returns:
        ServerResponse: The response
    """
    return Result.succ(service.update_space(request))


@router.delete(
    "/spaces/{space_id}",
    response_model=Result[None],
    dependencies=[Depends(check_api_key)],
)
async def delete(
    space_id: str, service: Service = Depends(get_service)
) -> Result[None]:
    """Delete a Space entity

    Args:
        request (SpaceServeRequest): The request
        service (Service): The service
    Returns:
        ServerResponse: The response
    """
    # TODO: Delete the files in the space
    res = await blocking_func_to_async(global_system_app, service.delete, space_id)
    return Result.succ(res)


@router.get(
    "/spaces/{space_id}",
    response_model=Result[List],
)
async def query(
    space_id: str,
    service: Service = Depends(get_service),
) -> Result[List[SpaceServeResponse]]:
    """Query Space entities

    Args:
        request (SpaceServeRequest): The request
        service (Service): The service
    Returns:
        List[ServeResponse]: The response
    """
    request = {"id": space_id}
    return Result.succ(service.get(request))


@router.get(
    "/spaces",
    response_model=Result[PaginationResult[SpaceServeResponse]],
)
async def query_page(
    page: int = Query(default=1, description="current page"),
    page_size: int = Query(default=20, description="page size"),
    service: Service = Depends(get_service),
) -> Result[PaginationResult[SpaceServeResponse]]:
    """Query Space entities

    Args:
        page (int): The page number
        page_size (int): The page size
        service (Service): The service
    Returns:
        ServerResponse: The response
    """
    return Result.succ(service.get_list_by_page({}, page, page_size))


@router.post("/spaces/{space_id}/retrieve")
async def space_retrieve(
    space_id: int,
    request: KnowledgeRetrieveRequest,
    service: Service = Depends(get_service),
) -> Result:
    """Create a new Document entity

    Args:
        space_id (int): The space id
        request (SpaceServeRequest): The request
        service (Service): The service
    Returns:
        ServerResponse: The response
    """
    request.space_id = space_id
    space_request = {
        "id": space_id,
    }
    space = service.get(space_request)
    if not space:
        raise HTTPException(status_code=404, detail="Space not found")
    return Result.succ(await service.retrieve(request, space))


@router.post("/documents")
async def create_document(
    doc_name: str = Form(...),
    doc_type: str = Form(...),
    space_id: str = Form(...),
    content: Optional[str] = Form(None),
    doc_file: Union[UploadFile, str] = Form(None),
    service: Service = Depends(get_service),
) -> Result:
    """Create a new Document entity

    Args:
        request (SpaceServeRequest): The request
        service (Service): The service
    Returns:
        ServerResponse: The response
    """
    request = DocumentServeRequest(
        doc_name=doc_name,
        doc_type=doc_type,
        content=content,
        doc_file=doc_file,
        space_id=space_id,
    )
    res = await blocking_func_to_async(
        global_system_app, service.create_document, request
    )
    return Result.succ(res)


@router.get(
    "/documents/{document_id}",
    response_model=Result[List],
)
async def query(
    document_id: int,
    service: Service = Depends(get_service),
) -> Result[List[SpaceServeResponse]]:
    """Query Space entities

    Args:
        request (SpaceServeRequest): The request
        service (Service): The service
    Returns:
        List[ServeResponse]: The response
    """
    request = {"id": document_id}
    return Result.succ(service.get_document(request))


@router.get(
    "/documents",
    response_model=Result[PaginationResult[SpaceServeResponse]],
)
async def query_page(
    page: int = Query(default=1, description="current page"),
    page_size: int = Query(default=20, description="page size"),
    service: Service = Depends(get_service),
) -> Result[PaginationResult[DocumentServeResponse]]:
    """Query Space entities

    Args:
        page (int): The page number
        page_size (int): The page size
        service (Service): The service
    Returns:
        ServerResponse: The response
    """
    return Result.succ(service.get_document_list_page({}, page, page_size))


@router.post("/documents/chunks/add")
async def add_documents_chunks(
    doc_name: str = Form(...),
    space_id: int = Form(...),
    content: List[str] = Form(None),
    service: Service = Depends(get_service),
) -> Result:
    """ """


@router.post("/documents/sync", dependencies=[Depends(check_api_key)])
async def sync_documents(
    requests: List[KnowledgeSyncRequest], service: Service = Depends(get_service)
) -> Result:
    """Create a new Document entity

    Args:
        request (SpaceServeRequest): The request
        service (Service): The service
    Returns:
        ServerResponse: The response
    """
    return Result.succ(service.sync_document(requests))


@router.post("/documents/batch_sync")
async def sync_documents(
    requests: List[KnowledgeSyncRequest],
    service: Service = Depends(get_service),
) -> Result:
    """Create a new Document entity

    Args:
        request (SpaceServeRequest): The request
        service (Service): The service
    Returns:
        ServerResponse: The response
    """
    return Result.succ(service.sync_document(requests))


@router.post("/documents/{document_id}/sync")
async def sync_document(
    document_id: int,
    request: KnowledgeSyncRequest,
    service: Service = Depends(get_service),
) -> Result:
    """Create a new Document entity

    Args:
        request (SpaceServeRequest): The request
        service (Service): The service
    Returns:
        ServerResponse: The response
    """
    request.doc_id = document_id
    if request.chunk_parameters is None:
        request.chunk_parameters = ChunkParameters(chunk_strategy="Automatic")
    return Result.succ(service.sync_document([request]))


@router.delete(
    "/documents/{document_id}",
    dependencies=[Depends(check_api_key)],
    response_model=Result[None],
)
async def delete_document(
    document_id: str, service: Service = Depends(get_service)
) -> Result[None]:
    """Delete a Space entity

    Args:
        request (SpaceServeRequest): The request
        service (Service): The service
    Returns:
        ServerResponse: The response
    """
    # TODO: Delete the files of the document
    res = await blocking_func_to_async(
        global_system_app, service.delete_document, document_id
    )
    return Result.succ(res)


@router.get(
    "/{space_id}/stats",
    response_model=Result[KnowledgeSpaceStatsResponse],
)
async def get_space_stats(
    space_id: str,
) -> Result[KnowledgeSpaceStatsResponse]:
    """Get aggregate statistics for a knowledge space.

    Returns document count, chunk count, sync progress (for GitRepo spaces),
    and graph statistics (vertex/edge/community counts).
    """
    import json
    import logging

    from sqlalchemy import func

    from ..models.code_graph_db import CodeGraphMetaDao
    from ..models.document_db import KnowledgeDocumentDao, KnowledgeDocumentEntity
    from ..models.models import KnowledgeSpaceDao, KnowledgeSpaceEntity

    logger = logging.getLogger(__name__)

    # Resolve space by ID or name
    space_dao = KnowledgeSpaceDao()
    if str(space_id).isdigit():
        spaces = space_dao.get_knowledge_space(KnowledgeSpaceEntity(id=int(space_id)))
    else:
        spaces = space_dao.get_knowledge_space(KnowledgeSpaceEntity(name=space_id))

    if not spaces:
        raise HTTPException(status_code=404, detail=f"Space '{space_id}' not found")

    space = spaces[0]

    # Document and chunk stats
    doc_dao = KnowledgeDocumentDao()
    session = doc_dao.get_raw_session()
    try:
        result = (
            session.query(
                func.count(KnowledgeDocumentEntity.id),
                func.coalesce(func.sum(KnowledgeDocumentEntity.chunk_size), 0),
            )
            .filter(KnowledgeDocumentEntity.space == space.name)
            .first()
        )
        doc_count = result[0] if result else 0
        chunk_count = int(result[1] or 0) if result else 0
    finally:
        session.close()

    # Graph stats
    meta_dao = CodeGraphMetaDao()
    graph_meta = meta_dao.get_by_knowledge_id(space.name)

    # Sync status (for GitRepo spaces)
    sync_info: dict = {}
    if space.domain_type == "GitRepo":
        try:
            from ..service.git_repo_sync_service import GitRepoSyncService

            service = get_service()
            sync_service = GitRepoSyncService(service)
            sync_info = sync_service.get_index_status(knowledge_id=space.name)
        except Exception:
            logger.warning(f"Failed to get sync status for space '{space.name}'")

    # Parse index_methods
    index_methods = None
    if space.index_methods:
        try:
            index_methods = json.loads(space.index_methods)
        except (json.JSONDecodeError, TypeError):
            index_methods = None

    return Result.succ(
        KnowledgeSpaceStatsResponse(
            name=space.name,
            domain_type=space.domain_type,
            vector_type=space.vector_type,
            index_methods=index_methods,
            desc=space.desc,
            document_count=doc_count,
            chunk_count=chunk_count,
            sync_status=sync_info.get("status"),
            sync_total_files=sync_info.get("total_files"),
            sync_finished=sync_info.get("finished"),
            sync_running=sync_info.get("running"),
            sync_failed=sync_info.get("failed"),
            sync_todo=sync_info.get("todo"),
            repo_url=sync_info.get("repo_url"),
            branch=sync_info.get("branch"),
            graph_vertex_count=graph_meta.vertex_count if graph_meta else None,
            graph_edge_count=graph_meta.edge_count if graph_meta else None,
            graph_community_count=graph_meta.community_count if graph_meta else None,
            graph_build_status=graph_meta.build_status if graph_meta else None,
        )
    )


def init_endpoints(system_app: SystemApp, config: ServeConfig) -> None:
    """Initialize the endpoints"""
    global global_system_app
    system_app.register(Service, config=config)
    global_system_app = system_app
