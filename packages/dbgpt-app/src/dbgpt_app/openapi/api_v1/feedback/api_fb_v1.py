from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from fastapi.security.http import HTTPAuthorizationCredentials

from dbgpt_app.openapi.api_v1.dashboard.identity import (
    DBGPTUserIdentityProvider,
    dashboard_production_mode,
)
from dbgpt_app.openapi.api_v1.feedback.feed_back_db import ChatFeedBackDao
from dbgpt_app.openapi.api_v1.feedback.feed_back_model import FeedBackBody
from dbgpt_app.openapi.api_view_model import Result
from dbgpt_serve.feedback.api import endpoints as feedback_serve_endpoints
from dbgpt_serve.feedback.config import SERVE_SERVICE_COMPONENT_NAME
from dbgpt_serve.feedback.service.service import Service as FeedbackService
from dbgpt_serve.utils.auth import UserRequest, get_user_from_headers


async def check_feedback_api_key(
    auth: Optional[HTTPAuthorizationCredentials] = Depends(
        feedback_serve_endpoints.get_bearer_token
    ),
) -> Optional[str]:
    """Enforce configured feedback service API keys when registered."""
    sys_app = feedback_serve_endpoints.global_system_app
    if sys_app is None:
        return None
    service = sys_app.get_component(
        SERVE_SERVICE_COMPONENT_NAME,
        FeedbackService,
        default_component=None,
    )
    if service is None or not service.config.api_keys:
        return None
    api_keys = feedback_serve_endpoints._parse_api_keys(service.config.api_keys)
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


def _resolve_feedback_actor(
    user_token: UserRequest = Depends(get_user_from_headers),
) -> str:
    """Resolve the authenticated caller identity for feedback operations."""
    if (
        dashboard_production_mode()
        and DBGPTUserIdentityProvider._is_development_fallback(user_token)
    ):
        raise HTTPException(status_code=401, detail="Authentication required")
    actor_id = (user_token.user_id or user_token.user_name or "").strip()
    if not actor_id:
        raise HTTPException(status_code=401, detail="Authentication required")
    return actor_id


router = APIRouter(dependencies=[Depends(check_feedback_api_key)])
chat_feed_back = ChatFeedBackDao()


@router.get("/v1/feedback/find", response_model=Result[FeedBackBody])
async def feed_back_find(
    conv_uid: str,
    conv_index: int,
    actor_id: str = Depends(_resolve_feedback_actor),
):
    rt = chat_feed_back.get_chat_feed_back(conv_uid, conv_index, user_name=actor_id)
    if rt is not None:
        return Result.succ(
            FeedBackBody(
                conv_uid=rt.conv_uid,
                conv_index=rt.conv_index,
                question=rt.question,
                knowledge_space=rt.knowledge_space,
                score=rt.score,
                ques_type=rt.ques_type,
                user_name=rt.user_name,
                messages=rt.messages,
            )
        )
    return Result.succ(None)


@router.post("/v1/feedback/commit", response_model=Result[bool])
async def feed_back_commit(
    request: Request,
    feed_back_body: FeedBackBody = Body(),
    actor_id: str = Depends(_resolve_feedback_actor),
):
    if not feed_back_body.conv_uid or feed_back_body.conv_index is None:
        raise HTTPException(
            status_code=422, detail="conv_uid and conv_index are required"
        )
    try:
        chat_feed_back.create_or_update_chat_feed_back(
            feed_back_body, user_name=actor_id
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return Result.succ(True)


@router.get("/v1/feedback/select", response_model=Result[dict])
async def feed_back_select():
    return Result.succ(
        {
            "information": "信息查询",
            "work_study": "工作学习",
            "just_fun": "互动闲聊",
            "others": "其他",
        }
    )
