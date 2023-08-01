import os

from fastapi import (
    APIRouter,
    Request,
    Body,
    BackgroundTasks,
)


from typing import List

from pilot.configs.config import Config
from pilot.server.knowledge.service import KnowledgeService

from pilot.scene.chat_factory import ChatFactory
from pilot.configs.model_config import LOGDIR
from pilot.utils import build_logger

from pilot.openapi.api_view_model import (
    Result,
    ConversationVo,
    MessageVo,
    ChatSceneVo,
)
from pilot.openapi.editor_view_model import (
    ChatDbRounds,
    ChartDetail,
    ChatChartEditContext,
    ChatSqlEditContext,
)

from pilot.scene.chat_dashboard.data_preparation.report_schma import ChartData

from pilot.scene.chat_db.auto_execute.out_parser import SqlAction

router = APIRouter()
CFG = Config()
CHAT_FACTORY = ChatFactory()
logger = build_logger("api_editor_v1", LOGDIR + "api_editor_v1.log")


@router.get("/v1/editor/sql/rounds", response_model=Result[ChatDbRounds])
async def get_editor_sql_rounds(con_uid: str):
    return Result.succ(None)


@router.get("/v1/editor/sql", response_model=Result[SqlAction])
async def get_editor_sql(con_uid: str, round: int):
    return Result.succ(None)


@router.get("/v1/editor/chart/details", response_model=Result[ChartDetail])
async def get_editor_sql_rounds(con_uid: str):
    return Result.succ(None)


@router.get("/v1/editor/chart", response_model=Result[ChartDetail])
async def get_editor_chart(con_uid: str, chart_uid: str):
    return Result.succ(None)


@router.post("/v1/editor/sql/run", response_model=Result[List[dict]])
async def get_editor_chart(db_name: str, sql: str):
    return Result.succ(None)


@router.post("/v1/editor/chart/run", response_model=Result[ChartData])
async def get_editor_chart(db_name: str, sql: str):
    return Result.succ(None)


@router.post("/v1/chart/editor/submit", response_model=Result[bool])
async def chart_editor_submit(chart_edit_context: ChatChartEditContext = Body()):
    return Result.succ(None)


@router.post("/v1/sql/editor/submit", response_model=Result[bool])
async def chart_editor_submit(sql_edit_context: ChatSqlEditContext = Body()):
    return Result.succ(None)
