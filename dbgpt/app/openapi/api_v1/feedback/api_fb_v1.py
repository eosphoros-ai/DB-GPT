from fastapi import APIRouter, Body, Request

from dbgpt.app.openapi.api_v1.feedback.feed_back_model import FeedBackBody
from dbgpt.app.openapi.api_v1.feedback.feed_back_db import (
    ChatFeedBackDao,
)
from dbgpt.app.openapi.api_view_model import Result

router = APIRouter()
chat_feed_back = ChatFeedBackDao()


@router.get("/v1/feedback/find", response_model=Result[FeedBackBody])
async def feed_back_find(conv_uid: str, conv_index: int):
    rt = chat_feed_back.get_chat_feed_back(conv_uid, conv_index)
    if rt is not None:
        return Result.succ(
            FeedBackBody(
                conv_uid=rt.conv_uid,
                conv_index=rt.conv_index,
                question=rt.question,
                knowledge_space=rt.knowledge_space,
                score=rt.score,
                ques_type=rt.ques_type,
                messages=rt.messages,
            )
        )
    else:
        return Result.succ(None)


@router.post("/v1/feedback/commit", response_model=Result[bool])
async def feed_back_commit(request: Request, feed_back_body: FeedBackBody = Body()):
    chat_feed_back.create_or_update_chat_feed_back(feed_back_body)
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
