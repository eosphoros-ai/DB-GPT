import io
import json
import uuid
from functools import cache
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.security.http import HTTPAuthorizationCredentials, HTTPBearer
from starlette.responses import JSONResponse, StreamingResponse

from dbgpt.component import SystemApp
from dbgpt.util import PaginationResult
from dbgpt_serve.core import Result

from ..config import SERVE_SERVICE_COMPONENT_NAME, ServeConfig
from ..service.service import Service
from .schemas import MessageVo, ServeRequest, ServerResponse

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
    request: Request = None,
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
    if request.url.path.startswith("/api/v1"):
        return None

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
    "/query",
    response_model=Result[ServerResponse],
    dependencies=[Depends(check_api_key)],
)
async def query(
    request: ServeRequest, service: Service = Depends(get_service)
) -> Result[ServerResponse]:
    """Query Conversation entities

    Args:
        request (ServeRequest): The request
        service (Service): The service
    Returns:
        ServerResponse: The response
    """
    return Result.succ(service.get(request))


@router.post(
    "/new",
    response_model=Result[ServerResponse],
    dependencies=[Depends(check_api_key)],
)
async def dialogue_new(
    chat_mode: str = "chat_normal",
    app_code: str = None,
    user_name: str = None,
    user_id: str = None,
    sys_code: str = None,
):
    user_name = user_name or user_id
    unique_id = uuid.uuid1()
    res = ServerResponse(
        user_input="",
        conv_uid=str(unique_id),
        chat_mode=chat_mode,
        app_code=app_code,
        user_name=user_name,
        sys_code=sys_code,
    )
    return Result.succ(res)


@router.post(
    "/delete",
    dependencies=[Depends(check_api_key)],
)
async def delete(con_uid: str, service: Service = Depends(get_service)):
    """Delete a Conversation entity

    Args:
        con_uid (str): The conversation UID
        service (Service): The service
    """
    service.delete(ServeRequest(conv_uid=con_uid))
    return Result.succ(None)


@router.post(
    "/clear",
    dependencies=[Depends(check_api_key)],
)
async def clear(
    con_uid: str,
    service: Service = Depends(get_service),
):
    """Clear a Conversation entity

    Args:
        con_uid (str): The conversation UID
        service (Service): The service
    """
    service.clear(ServeRequest(conv_uid=con_uid))
    return Result.succ(None)


@router.post(
    "/query_page",
    response_model=Result[PaginationResult[ServerResponse]],
    dependencies=[Depends(check_api_key)],
)
async def query_page(
    request: ServeRequest,
    page: Optional[int] = Query(default=1, description="current page"),
    page_size: Optional[int] = Query(default=10, description="page size"),
    service: Service = Depends(get_service),
) -> Result[PaginationResult[ServerResponse]]:
    """Query Conversation entities

    Args:
        request (ServeRequest): The request
        page (int): The page number
        page_size (int): The page size
        service (Service): The service
    Returns:
        ServerResponse: The response
    """
    return Result.succ(service.get_list_by_page(request, page, page_size))


@router.get(
    "/list",
    response_model=Result[List[ServerResponse]],
    dependencies=[Depends(check_api_key)],
)
async def list_latest_conv(
    user_name: str = None,
    user_id: str = None,
    sys_code: str = None,
    page: Optional[int] = Query(default=1, description="current page"),
    page_size: Optional[int] = Query(default=10, description="page size"),
    service: Service = Depends(get_service),
) -> Result[List[ServerResponse]]:
    """Return latest conversations"""
    request = ServeRequest(
        user_name=user_name or user_id,
        sys_code=sys_code,
    )
    return Result.succ(service.get_list_by_page(request, page, page_size).items)


@router.get(
    "/messages/history",
    response_model=Result[List[MessageVo]],
    dependencies=[Depends(check_api_key)],
)
async def get_history_messages(con_uid: str, service: Service = Depends(get_service)):
    """Get the history messages of a conversation"""
    return Result.succ(service.get_history_messages(ServeRequest(conv_uid=con_uid)))


@router.get(
    "/export_messages",
    dependencies=[Depends(check_api_key)],
)
async def export_all_messages(
    user_name: Optional[str] = None,
    user_id: Optional[str] = None,
    sys_code: Optional[str] = None,
    format: Literal["file", "json"] = Query(
        "file", description="response format(file or json)"
    ),
    service: Service = Depends(get_service),
):
    """Export all conversations and messages for a user

    Args:
        user_name (str): The user name
        user_id (str): The user id (alternative to user_name)
        sys_code (str): The system code
        format (str): The format of the response, either 'file' or 'json', defaults to
            'file'

    Returns:
        A dictionary containing all conversations and their messages
    """
    # 1. Get all conversations for the user
    request = ServeRequest(
        user_name=user_name or user_id,
        sys_code=sys_code,
    )

    # Initialize pagination variables
    page = 1
    page_size = 100  # Adjust based on your needs
    all_conversations = []

    # Paginate through all conversations
    while True:
        pagination_result = service.get_list_by_page(request, page, page_size)
        all_conversations.extend(pagination_result.items)

        if page >= pagination_result.total_pages:
            break
        page += 1

    # 2. For each conversation, get all messages
    result = {
        "user_name": user_name or user_id,
        "sys_code": sys_code,
        "total_conversations": len(all_conversations),
        "conversations": [],
    }

    for conv in all_conversations:
        messages = service.get_history_messages(ServeRequest(conv_uid=conv.conv_uid))
        conversation_data = {
            "conv_uid": conv.conv_uid,
            "chat_mode": conv.chat_mode,
            "app_code": conv.app_code,
            "create_time": conv.gmt_created,
            "update_time": conv.gmt_modified,
            "total_messages": len(messages),
            "messages": [msg.dict() for msg in messages],
        }
        result["conversations"].append(conversation_data)

    if format == "json":
        return JSONResponse(content=result)
    else:
        file_name = (
            f"conversation_export_{user_name or user_id or 'dbgpt'}_"
            f"{sys_code or 'dbgpt'}"
        )
        # Return the json file
        return StreamingResponse(
            io.BytesIO(
                json.dumps(result, ensure_ascii=False, indent=4).encode("utf-8")
            ),
            media_type="application/file",
            headers={"Content-Disposition": f"attachment;filename={file_name}.json"},
        )


def init_endpoints(system_app: SystemApp, config: ServeConfig) -> None:
    """Initialize the endpoints"""
    global global_system_app
    system_app.register(Service, config=config)
    global_system_app = system_app
