import json
from fastapi import (
    APIRouter,
    Body,
)

from typing import List

from pilot.configs.config import Config

from pilot.scene.chat_factory import ChatFactory
from pilot.configs.model_config import LOGDIR
from pilot.utils import build_logger

from pilot.openapi.api_view_model import (
    Result,
)
from pilot.openapi.editor_view_model import (
    ChatDbRounds,
    ChartDetail,
    ChatChartEditContext,
    ChatSqlEditContext,
    DbTable
)

from pilot.openapi.api_v1.editor.sql_editor import DataNode,ChartRunData,SqlRunData
from pilot.memory.chat_history.duckdb_history import DuckdbHistoryMemory
from pilot.scene.message import OnceConversation
from pilot.scene.chat_dashboard.data_loader import DashboardDataLoader


router = APIRouter()
CFG = Config()
CHAT_FACTORY = ChatFactory()
logger = build_logger("api_editor_v1", LOGDIR + "api_editor_v1.log")


@router.get("/v1/editor/db/tables", response_model=Result[DbTable])
async def get_editor_tables(db_name: str, page_index: int, page_size: int, search_str: str = ""):
    logger.info("get_editor_tables:{},{},{},{}", db_name, page_index, page_size, search_str)
    db_conn = CFG.LOCAL_DB_MANAGE.get_connect(db_name)
    tables = db_conn.get_table_names()
    db_node: DataNode = DataNode(title=db_name, key=db_name, type="db")
    for table in tables:
        table_node: DataNode = DataNode(title=table, key=table, type="table")
        db_node.children.append(table_node)
        fields = db_conn.get_fields("transaction_order")
        for field in fields:
            table_node.children.append(
                DataNode(title=field[0], key=field[0], type=field[1], default_value=field[2], can_null=field[3],
                         comment=field[-1]))

    return Result.succ(db_node)


@router.get("/v1/editor/sql/rounds", response_model=Result[ChatDbRounds])
async def get_editor_sql_rounds(con_uid: str):
    logger.info("get_editor_sql_rounds:{}", con_uid)
    history_mem = DuckdbHistoryMemory(con_uid)
    history_messages: List[OnceConversation] = history_mem.get_messages()
    if history_messages:
        result: List = []
        for once in history_messages:
            round_name: str = ""
            for element in once["messages"]:
                if element["type"] == "human":
                    round_name = element["data"]["content"]
            if once.get("param_value"):
                round: ChatDbRounds = ChatDbRounds(round=once["chat_order"], db_name=once["param_value"],
                                                   round_name=round_name)
                result.append(round)
    return Result.succ(result)


@router.get("/v1/editor/sql", response_model=Result[dict])
async def get_editor_sql(con_uid: str, round: int):
    logger.info("get_editor_sql:{},{}", con_uid, round)
    history_mem = DuckdbHistoryMemory(con_uid)
    history_messages: List[OnceConversation] = history_mem.get_messages()
    if history_messages:
        for once in history_messages:
            if int(once["chat_order"]) == round:
                for element in once["messages"]:
                    if element["type"] == "ai":
                        return Result.succ(json.loads(element["data"]["content"]))
    return Result.faild("没有获取到可用的SQL返回结构")


@router.post("/v1/editor/sql/run", response_model=Result[List[dict]])
async def editor_sql_run(db_name: str, sql: str):
    logger.info("get_editor_sql_run:{},{}", db_name, sql)
    conn = CFG.LOCAL_DB_MANAGE.get_connect(db_name)
    return Result.succ(conn.run(sql))


@router.post("/v1/sql/editor/submit", response_model=Result)
async def sql_editor_submit(sql_edit_context: ChatSqlEditContext = Body()):
    logger.info(f"sql_editor_submit:{sql_edit_context.__dict__}")
    history_mem = DuckdbHistoryMemory(sql_edit_context.conv_uid)
    history_messages: List[OnceConversation] = history_mem.get_messages()
    if history_messages:
        edit_round  = list(filter(lambda x: x['chat_order'] == sql_edit_context.conv_round, history_messages))[0]
        if edit_round:
            for element in edit_round["messages"]:
                if element["type"] == "ai":
                    element["data"]["content"]=""
                if element["type"] == "view":
                    element["data"]["content"]=""
            history_mem.update(history_messages)
            return Result.succ(None)
    return Result.faild("Edit Faild!")


@router.get("/v1/editor/chart/list", response_model=Result[ChartDetail])
async def get_editor_chart_list(con_uid: str):
    logger.info("get_editor_sql_rounds:{}", con_uid)
    history_mem = DuckdbHistoryMemory(con_uid)
    history_messages: List[OnceConversation] = history_mem.get_messages()
    if history_messages:
        last_round = max(history_messages, key=lambda x: x['chat_order'])
        for element in last_round["messages"]:
            if element["type"] == "ai":
                return Result.succ(json.loads(element["data"]["content"]))

    return Result.faild("没有获取到可用的SQL返回结构")


@router.get("/v1/editor/chart/info", response_model=Result[ChartDetail])
async def get_editor_chart_info(con_uid: str, chart_uid: str):
    logger.info(f"get_editor_sql_rounds:{con_uid}")
    logger.info("get_editor_sql_rounds:{}", con_uid)
    history_mem = DuckdbHistoryMemory(con_uid)
    history_messages: List[OnceConversation] = history_mem.get_messages()
    if history_messages:
        last_round = max(history_messages, key=lambda x: x['chat_order'])
        db_name = last_round["param_value"]
        if not db_name:
            logger.error("this dashboard dialogue version too old, can't support editor!")
            return Result.faild("this dashboard dialogue version too old, can't support editor!")
        for element in last_round["messages"]:
            if element["type"] == "view":
                view_data: dict = json.loads(element["data"]["content"]);
                charts: List = view_data.get("charts")
                find_chart = list(filter(lambda x: x['chart_name'] == chart_uid, charts))[0]

                conn = CFG.LOCAL_DB_MANAGE.get_connect(db_name)
                detail: ChartDetail = ChartDetail(chart_uid=find_chart['chart_uid'],
                                                  chart_type=find_chart['chart_type'],
                                                  chart_desc=find_chart['chart_desc'],
                                                  chart_sql=find_chart['chart_sql'],
                                                  db_name=db_name,
                                                  chart_name=find_chart['chart_name'],
                                                  chart_value=find_chart['values'],
                                                  table_value=conn.run(find_chart['chart_sql'])
                                                  )

                return Result.succ(detail)
    return Result.faild("Can't Find Chart Detail Info!")


@router.post("/v1/editor/chart/run", response_model=Result[ChartRunData])
async def editor_chart_run(db_name: str, sql: str):
    logger.info(f"editor_chart_run:{db_name},{sql}")
    dashboard_data_loader:DashboardDataLoader = DashboardDataLoader()
    db_conn = CFG.LOCAL_DB_MANAGE.get_connect(db_name)

    field_names,chart_values = dashboard_data_loader.get_chart_values_by_db(db_conn, sql)

    sql_run_data:SqlRunData = SqlRunData(result_info="",
                                         run_cost="",
                                         colunms= field_names,
                                         values= db_conn.query_ex(sql)
                                         )
    return Result.succ(ChartRunData(sql_data=sql_run_data,chart_values=chart_values))


@router.post("/v1/chart/editor/submit", response_model=Result[bool])
async def chart_editor_submit(chart_edit_context: ChatChartEditContext = Body()):
    logger.info(f"sql_editor_submit:{chart_edit_context.__dict__}")
    history_mem = DuckdbHistoryMemory(chart_edit_context.conv_uid)
    history_messages: List[OnceConversation] = history_mem.get_messages()
    if history_messages:
        edit_round  = list(filter(lambda x: x['chat_order'] == chart_edit_context.conv_round, history_messages))[0]
        if edit_round:
            for element in edit_round["messages"]:
                if element["type"] == "ai":
                    view_data: dict = json.loads(element["data"]["content"]);
                    charts: List = view_data.get("charts")
                    find_chart = list(filter(lambda x: x['chart_name'] == chart_edit_context.chart_uid, charts))[0]


                if element["type"] == "view":
                    view_data: dict = json.loads(element["data"]["content"]);
                    charts: List = view_data.get("charts")
                    find_chart = list(filter(lambda x: x['chart_name'] == chart_edit_context.chart_uid, charts))[0]


            history_mem.update(history_messages)
            return Result.succ(None)
    return Result.faild("Edit Faild!")
