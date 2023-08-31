import json
import time
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
    ChartList,
    ChartDetail,
    ChatChartEditContext,
    ChatSqlEditContext,
    DbTable,
)

from pilot.openapi.api_v1.editor.sql_editor import DataNode, ChartRunData, SqlRunData
from pilot.memory.chat_history.duckdb_history import DuckdbHistoryMemory
from pilot.scene.message import OnceConversation
from pilot.scene.chat_dashboard.data_loader import DashboardDataLoader
from pilot.scene.chat_db.data_loader import DbDataLoader

router = APIRouter()
CFG = Config()
CHAT_FACTORY = ChatFactory()
logger = build_logger("api_editor_v1", LOGDIR + "api_editor_v1.log")


@router.get("/v1/editor/db/tables", response_model=Result[DbTable])
async def get_editor_tables(
    db_name: str, page_index: int, page_size: int, search_str: str = ""
):
    logger.info(f"get_editor_tables:{db_name},{page_index},{page_size},{search_str}")
    db_conn = CFG.LOCAL_DB_MANAGE.get_connect(db_name)
    tables = db_conn.get_table_names()
    db_node: DataNode = DataNode(title=db_name, key=db_name, type="db")
    for table in tables:
        table_node: DataNode = DataNode(title=table, key=table, type="table")
        db_node.children.append(table_node)
        fields = db_conn.get_fields(table)
        for field in fields:
            table_node.children.append(
                DataNode(
                    title=field[0],
                    key=field[0],
                    type=field[1],
                    default_value=field[2],
                    can_null=field[3],
                    comment=field[-1],
                )
            )

    return Result.succ(db_node)


@router.get("/v1/editor/sql/rounds", response_model=Result[ChatDbRounds])
async def get_editor_sql_rounds(con_uid: str):
    logger.info("get_editor_sql_rounds:{con_uid}")
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
                round: ChatDbRounds = ChatDbRounds(
                    round=once["chat_order"],
                    db_name=once["param_value"],
                    round_name=round_name,
                )
                result.append(round)
    return Result.succ(result)


@router.get("/v1/editor/sql", response_model=Result[dict])
async def get_editor_sql(con_uid: str, round: int):
    logger.info(f"get_editor_sql:{con_uid},{round}")
    history_mem = DuckdbHistoryMemory(con_uid)
    history_messages: List[OnceConversation] = history_mem.get_messages()
    if history_messages:
        for once in history_messages:
            if int(once["chat_order"]) == round:
                for element in once["messages"]:
                    if element["type"] == "ai":
                        logger.info(
                            f'history ai json resp:{element["data"]["content"]}'
                        )
                        context = (
                            element["data"]["content"]
                            .replace("\\n", " ")
                            .replace("\n", " ")
                        )
                        return Result.succ(json.loads(context))
    return Result.faild(msg="not have sql!")


@router.post("/v1/editor/sql/run", response_model=Result[SqlRunData])
async def editor_sql_run(run_param: dict = Body()):
    logger.info(f"editor_sql_run:{run_param}")
    db_name = run_param["db_name"]
    sql = run_param["sql"]
    if not db_name and not sql:
        return Result.faild("SQL run param error！")
    conn = CFG.LOCAL_DB_MANAGE.get_connect(db_name)

    try:
        start_time = time.time() * 1000
        colunms, sql_result = conn.query_ex(sql)
        # 计算执行耗时
        end_time = time.time() * 1000
        sql_run_data: SqlRunData = SqlRunData(
            result_info="",
            run_cost=(end_time - start_time) / 1000,
            colunms=colunms,
            values=sql_result,
        )
        return Result.succ(sql_run_data)
    except Exception as e:
        return Result.succ(
            SqlRunData(result_info=str(e), run_cost=0, colunms=[], values=[])
        )


@router.post("/v1/sql/editor/submit")
async def sql_editor_submit(sql_edit_context: ChatSqlEditContext = Body()):
    logger.info(f"sql_editor_submit:{sql_edit_context.__dict__}")
    history_mem = DuckdbHistoryMemory(sql_edit_context.conv_uid)
    history_messages: List[OnceConversation] = history_mem.get_messages()
    if history_messages:
        conn = CFG.LOCAL_DB_MANAGE.get_connect(sql_edit_context.db_name)

        edit_round = list(
            filter(
                lambda x: x["chat_order"] == sql_edit_context.conv_round,
                history_messages,
            )
        )[0]
        if edit_round:
            for element in edit_round["messages"]:
                if element["type"] == "ai":
                    db_resp = json.loads(element["data"]["content"])
                    db_resp["thoughts"] = sql_edit_context.new_speak
                    db_resp["sql"] = sql_edit_context.new_sql
                    element["data"]["content"] = json.dumps(db_resp)
                if element["type"] == "view":
                    data_loader = DbDataLoader()
                    element["data"]["content"] = data_loader.get_table_view_by_conn(
                        conn.run(sql_edit_context.new_sql), sql_edit_context.new_speak
                    )
            history_mem.update(history_messages)
            return Result.succ(None)
    return Result.faild(msg="Edit Faild!")


@router.get("/v1/editor/chart/list", response_model=Result[ChartList])
async def get_editor_chart_list(con_uid: str):
    logger.info(
        f"get_editor_sql_rounds:{con_uid}",
    )
    history_mem = DuckdbHistoryMemory(con_uid)
    history_messages: List[OnceConversation] = history_mem.get_messages()
    if history_messages:
        last_round = max(history_messages, key=lambda x: x["chat_order"])
        db_name = last_round["param_value"]
        for element in last_round["messages"]:
            if element["type"] == "ai":
                chart_list: ChartList = ChartList(
                    round=last_round["chat_order"],
                    db_name=db_name,
                    charts=json.loads(element["data"]["content"]),
                )
                return Result.succ(chart_list)
    return Result.faild(msg="Not have charts!")


@router.post("/v1/editor/chart/info", response_model=Result[ChartDetail])
async def get_editor_chart_info(param: dict = Body()):
    logger.info(f"get_editor_chart_info:{param}")
    conv_uid = param["con_uid"]
    chart_title = param["chart_title"]

    history_mem = DuckdbHistoryMemory(conv_uid)
    history_messages: List[OnceConversation] = history_mem.get_messages()
    if history_messages:
        last_round = max(history_messages, key=lambda x: x["chat_order"])
        db_name = last_round["param_value"]
        if not db_name:
            logger.error(
                "this dashboard dialogue version too old, can't support editor!"
            )
            return Result.faild(
                msg="this dashboard dialogue version too old, can't support editor!"
            )
        for element in last_round["messages"]:
            if element["type"] == "view":
                view_data: dict = json.loads(element["data"]["content"])
                charts: List = view_data.get("charts")
                find_chart = list(
                    filter(lambda x: x["chart_name"] == chart_title, charts)
                )[0]

                conn = CFG.LOCAL_DB_MANAGE.get_connect(db_name)
                detail: ChartDetail = ChartDetail(
                    chart_uid=find_chart["chart_uid"],
                    chart_type=find_chart["chart_type"],
                    chart_desc=find_chart["chart_desc"],
                    chart_sql=find_chart["chart_sql"],
                    db_name=db_name,
                    chart_name=find_chart["chart_name"],
                    chart_value=find_chart["values"],
                    table_value=conn.run(find_chart["chart_sql"]),
                )

                return Result.succ(detail)
    return Result.faild(msg="Can't Find Chart Detail Info!")


@router.post("/v1/editor/chart/run", response_model=Result[ChartRunData])
async def editor_chart_run(run_param: dict = Body()):
    logger.info(f"editor_chart_run:{run_param}")
    db_name = run_param["db_name"]
    sql = run_param["sql"]
    chart_type = run_param["chart_type"]
    if not db_name and not sql:
        return Result.faild("SQL run param error！")
    try:
        dashboard_data_loader: DashboardDataLoader = DashboardDataLoader()
        db_conn = CFG.LOCAL_DB_MANAGE.get_connect(db_name)
        colunms, sql_result = db_conn.query_ex(sql)
        field_names, chart_values = dashboard_data_loader.get_chart_values_by_data(
            colunms, sql_result, sql
        )

        start_time = time.time() * 1000
        # 计算执行耗时
        end_time = time.time() * 1000
        sql_run_data: SqlRunData = SqlRunData(
            result_info="",
            run_cost=(end_time - start_time) / 1000,
            colunms=colunms,
            values=sql_result,
        )
        return Result.succ(
            ChartRunData(
                sql_data=sql_run_data, chart_values=chart_values, chart_type=chart_type
            )
        )
    except Exception as e:
        sql_result = SqlRunData(result_info=str(e), run_cost=0, colunms=[], values=[])
        return Result.succ(
            ChartRunData(sql_data=sql_result, chart_values=[], chart_type=chart_type)
        )


@router.post("/v1/chart/editor/submit", response_model=Result[bool])
async def chart_editor_submit(chart_edit_context: ChatChartEditContext = Body()):
    logger.info(f"sql_editor_submit:{chart_edit_context.__dict__}")
    history_mem = DuckdbHistoryMemory(chart_edit_context.conv_uid)
    history_messages: List[OnceConversation] = history_mem.get_messages()
    if history_messages:
        dashboard_data_loader: DashboardDataLoader = DashboardDataLoader()
        db_conn = CFG.LOCAL_DB_MANAGE.get_connect(chart_edit_context.db_name)

        edit_round = max(history_messages, key=lambda x: x["chat_order"])
        if edit_round:
            try:
                for element in edit_round["messages"]:
                    if element["type"] == "view":
                        view_data: dict = json.loads(element["data"]["content"])
                        charts: List = view_data.get("charts")
                        find_chart = list(
                            filter(
                                lambda x: x["chart_name"]
                                == chart_edit_context.chart_title,
                                charts,
                            )
                        )[0]
                        if chart_edit_context.new_chart_type:
                            find_chart["chart_type"] = chart_edit_context.new_chart_type
                        if chart_edit_context.new_comment:
                            find_chart["chart_desc"] = chart_edit_context.new_comment

                        (
                            field_names,
                            chart_values,
                        ) = dashboard_data_loader.get_chart_values_by_conn(
                            db_conn, chart_edit_context.new_sql
                        )
                        find_chart["chart_sql"] = chart_edit_context.new_sql
                        find_chart["values"] = [value.dict() for value in chart_values]
                        find_chart["column_name"] = field_names

                        element["data"]["content"] = json.dumps(
                            view_data, ensure_ascii=False
                        )
                    if element["type"] == "ai":
                        ai_resp: dict = json.loads(element["data"]["content"])
                        edit_item = list(
                            filter(
                                lambda x: x["title"] == chart_edit_context.chart_title,
                                ai_resp,
                            )
                        )[0]

                        edit_item["sql"] = chart_edit_context.new_sql
                        edit_item["showcase"] = chart_edit_context.new_chart_type
                        edit_item["thoughts"] = chart_edit_context.new_comment
                        element["data"]["content"] = json.dumps(
                            ai_resp, ensure_ascii=False
                        )
            except Exception as e:
                logger.error(f"edit chart exception!{str(e)}", e)
                return Result.faild(msg=f"Edit chart exception!{str(e)}")
            history_mem.update(history_messages)
            return Result.succ(None)
    return Result.faild(msg="Edit Faild!")
