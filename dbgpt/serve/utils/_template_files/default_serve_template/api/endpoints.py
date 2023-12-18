from typing import Optional, List
from fastapi import APIRouter, Depends, Query

from dbgpt.component import SystemApp
from dbgpt.serve.core import Result
from dbgpt.util import PaginationResult
from .schemas import ServeRequest, ServerResponse
from ..service.service import Service
from ..config import APP_NAME, SERVE_APP_NAME, ServeConfig, SERVE_SERVICE_COMPONENT_NAME

router = APIRouter()

# Add your API endpoints here

global_system_app: Optional[SystemApp] = None


def get_service() -> Service:
    """Get the service instance"""
    return global_system_app.get_component(SERVE_SERVICE_COMPONENT_NAME, Service)


@router.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "ok"}


@router.post("/", response_model=Result[ServerResponse])
async def create(
    request: ServeRequest, service: Service = Depends(get_service)
) -> Result[ServerResponse]:
    """Create a new {__template_app_name__hump__} entity

    Args:
        request (ServeRequest): The request
        service (Service): The service
    Returns:
        ServerResponse: The response
    """
    return Result.succ(service.create(request))


@router.put("/", response_model=Result[ServerResponse])
async def update(
    request: ServeRequest, service: Service = Depends(get_service)
) -> Result[ServerResponse]:
    """Update a {__template_app_name__hump__} entity

    Args:
        request (ServeRequest): The request
        service (Service): The service
    Returns:
        ServerResponse: The response
    """
    return Result.succ(service.update(request))


@router.post("/query", response_model=Result[ServerResponse])
async def query(
    request: ServeRequest, service: Service = Depends(get_service)
) -> Result[ServerResponse]:
    """Query {__template_app_name__hump__} entities

    Args:
        request (ServeRequest): The request
        service (Service): The service
    Returns:
        ServerResponse: The response
    """
    return Result.succ(service.get(request))


@router.post("/query_page", response_model=Result[PaginationResult[ServerResponse]])
async def query_page(
    request: ServeRequest,
    page: Optional[int] = Query(default=1, description="current page"),
    page_size: Optional[int] = Query(default=20, description="page size"),
    service: Service = Depends(get_service),
) -> Result[PaginationResult[ServerResponse]]:
    """Query {__template_app_name__hump__} entities

    Args:
        request (ServeRequest): The request
        page (int): The page number
        page_size (int): The page size
        service (Service): The service
    Returns:
        ServerResponse: The response
    """
    return Result.succ(service.get_list_by_page(request, page, page_size))


def init_endpoints(system_app: SystemApp) -> None:
    """Initialize the endpoints"""
    global global_system_app
    system_app.register(Service)
    global_system_app = system_app
