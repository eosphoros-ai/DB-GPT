import logging

from fastapi import APIRouter, Depends

from dbgpt.app.openapi.api_view_model import Result
from dbgpt.serve.agent.app.recommend_question.recommend_question import (
    RecommendQuestion,
    RecommendQuestionDao,
)
from dbgpt.serve.utils.auth import UserRequest, get_user_from_headers

router = APIRouter()
logger = logging.getLogger(__name__)

recommend_question_dao = RecommendQuestionDao()


@router.post("/v1/question/create")
async def create(
    recommend_question: RecommendQuestion,
    user_info: UserRequest = Depends(get_user_from_headers),
):
    try:
        if user_info.user_id is not None:
            recommend_question.user_code = user_info.user_id
        return Result.succ(recommend_question_dao.create(recommend_question))
    except Exception as ex:
        return Result.failed(code="E000X", msg=f"create question error: {ex}")


@router.get("/v1/question/list")
async def query(
    valid: str = None,
    app_code: str = None,
    chat_mode: str = None,
    is_hot_question: str = None,
    user_info: UserRequest = Depends(get_user_from_headers),
):
    try:
        return Result.succ(
            recommend_question_dao.list_questions(
                RecommendQuestion(
                    valid=valid,
                    app_code=app_code,
                    chat_mode=chat_mode,
                    is_hot_question=is_hot_question,
                )
            )
        )
    except Exception as ex:
        return Result.failed(code="E000X", msg=f"query questions error: {ex}")


@router.post("/v1/question/update")
async def update(
    recommend_question: RecommendQuestion,
    user_info: UserRequest = Depends(get_user_from_headers),
):
    try:
        if user_info.user_id is not None:
            recommend_question.user_code = user_info.user_id
        recommend_question_dao.update_question(recommend_question)
        return Result.succ([])
    except Exception as ex:
        return Result.failed(code="E000X", msg=f"update question error: {ex}")


@router.post("/v1/question/delete")
async def delete(
    recommend_question: RecommendQuestion,
    user_info: UserRequest = Depends(get_user_from_headers),
):
    try:
        recommend_question_dao.delete_question(recommend_question)
        return Result.succ([])
    except Exception as ex:
        return Result.failed(code="E000X", msg=f"delete question error: {ex}")
