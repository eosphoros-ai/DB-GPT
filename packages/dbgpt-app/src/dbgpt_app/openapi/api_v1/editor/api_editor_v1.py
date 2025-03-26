import json
import logging
import re
import time
from typing import Dict, List

from fastapi import APIRouter, Body, Depends

from dbgpt._private.config import Config
from dbgpt.core.interface.message import OnceConversation
from dbgpt_app.openapi.api_v1.editor._chat_history.chat_hisotry_factory import (
    ChatHistory,
)
from dbgpt_app.openapi.api_v1.editor.service import EditorService
from dbgpt_app.openapi.api_v1.editor.sql_editor import (
    ChartRunData,
    DataNode,
    SqlRunData,
)
from dbgpt_app.openapi.api_view_model import Result
from dbgpt_app.openapi.editor_view_model import (
    ChartDetail,
    ChartList,
    ChatChartEditContext,
    ChatDbRounds,
    ChatSqlEditContext,
)
from dbgpt_app.scene import ChatFactory
from dbgpt_app.scene.chat_dashboard.data_loader import DashboardDataLoader
from dbgpt_serve.conversation.serve import Serve as ConversationServe

router = APIRouter()
CFG = Config()
CHAT_FACTORY = ChatFactory()

logger = logging.getLogger(__name__)


def get_conversation_serve() -> ConversationServe:
    return ConversationServe.get_instance(CFG.SYSTEM_APP)


def get_edit_service() -> EditorService:
    return EditorService.get_instance(CFG.SYSTEM_APP)


@router.get("/v1/editor/db/tables", response_model=Result[DataNode])
async def get_editor_tables(
    db_name: str, page_index: int, page_size: int, search_str: str = ""
):
    logger.info(f"get_editor_tables:{db_name},{page_index},{page_size},{search_str}")
    db_conn = CFG.local_db_manager.get_connector(db_name)
    tables = db_conn.get_table_names()
    db_node: DataNode = DataNode(title=db_name, key=db_name, type="db")
    for table in tables:
        table_node: DataNode = DataNode(title=table, key=table, type="table")
        db_node.children.append(table_node)
        fields = db_conn.get_fields(table, db_name)
        for field in fields:
            table_node.children.append(
                DataNode(
                    title=field[0],
                    key=field[0],
                    type=field[1],
                    default_value=field[2],
                    can_null=field[3] or "YES",
                    comment=str(field[-1]),
                )
            )

    return Result.succ(db_node)


@router.get("/v1/editor/sql/rounds", response_model=Result[List[ChatDbRounds]])
async def get_editor_sql_rounds(
    con_uid: str, editor_service: EditorService = Depends(get_edit_service)
):
    logger.info("get_editor_sql_rounds:{con_uid}")
    try:
        chat_rounds = editor_service.get_editor_sql_rounds(con_uid)
        return Result.succ(data=chat_rounds)
    except Exception as e:
        logger.exception("Get editor sql rounds failed!")
        return Result.failed(msg=str(e))


@router.get("/v1/editor/sql", response_model=Result[List[Dict]])
async def get_editor_sql(
    con_uid: str, round: int, editor_service: EditorService = Depends(get_edit_service)
):
    logger.info(f"get_editor_sql:{con_uid},{round}")
    context = editor_service.get_editor_sql_by_round(con_uid, round)
    if context:
        return Result.succ(context)
    return Result.failed(msg="not have sql!")


@router.post("/v1/editor/sql/run", response_model=Result[SqlRunData])
async def editor_sql_run(run_param: dict = Body()):
    logger.info(f"editor_sql_run:{run_param}")
    db_name = run_param["db_name"]
    sql = run_param["sql"]
    if not db_name and not sql:
        return Result.failed(msg="SQL run param error！")

    # Validate database type and prevent dangerous operations
    conn = CFG.local_db_manager.get_connector(db_name)
    db_type = getattr(conn, "db_type", "").lower()

    # Block dangerous operations for DuckDB
    if db_type == "duckdb":
        # Block file operations and system commands
        dangerous_keywords = [
            # File operations
            "copy",
            "export",
            "import",
            "load",
            "install",
            "read_",
            "write_",
            "save",
            "from_",
            "to_",
            # System commands
            "create_",
            "drop_",
            ".execute(",
            "system",
            "shell",
            # Additional DuckDB specific operations
            "attach",
            "detach",
            "pragma",
            "checkpoint",
            "load_extension",
            "unload_extension",
            # File paths
            "/'",
            "'/'",
            "\\",
            "://",
        ]
        sql_lower = sql.lower().replace(" ", "")  # Remove spaces to prevent bypass
        if any(keyword in sql_lower for keyword in dangerous_keywords):
            logger.warning(f"Blocked dangerous SQL operation attempt: {sql}")
            return Result.failed(msg="Operation not allowed for security reasons")

        # Additional check for file path patterns
        if re.search(r"['\"].*[/\\].*['\"]", sql):
            logger.warning(f"Blocked file path in SQL: {sql}")
            return Result.failed(msg="File operations not allowed")

    try:
        start_time = time.time() * 1000
        # Add timeout protection
        colunms, sql_result = conn.query_ex(sql, timeout=30)
        # Convert result type safely
        sql_result = [
            tuple(str(x) if x is not None else None for x in row) for row in sql_result
        ]
        # Calculate execution time
        end_time = time.time() * 1000
        sql_run_data: SqlRunData = SqlRunData(
            result_info="",
            run_cost=(end_time - start_time) / 1000,
            colunms=colunms,
            values=sql_result,
        )
        return Result.succ(sql_run_data)
    except Exception as e:
        logger.error(f"editor_sql_run exception: {str(e)}", exc_info=True)
        return Result.succ(
            SqlRunData(result_info=str(e), run_cost=0, colunms=[], values=[])
        )


@router.post("/v1/sql/editor/submit")
async def sql_editor_submit(
    sql_edit_context: ChatSqlEditContext = Body(),
    editor_service: EditorService = Depends(get_edit_service),
):
    logger.info(f"sql_editor_submit:{sql_edit_context.__dict__}")

    conn = CFG.local_db_manager.get_connector(sql_edit_context.db_name)
    try:
        editor_service.sql_editor_submit_and_save(sql_edit_context, conn)
        return Result.succ(None)
    except Exception as e:
        logger.error(f"edit sql exception!{str(e)}")
        return Result.failed(msg=f"Edit sql exception!{str(e)}")


@router.get("/v1/editor/chart/list", response_model=Result[ChartList])
async def get_editor_chart_list(
    con_uid: str,
    editor_service: EditorService = Depends(get_edit_service),
):
    logger.info(
        f"get_editor_sql_rounds:{con_uid}",
    )
    chart_list = editor_service.get_editor_chart_list(con_uid)
    if chart_list:
        return Result.succ(chart_list)
    return Result.failed(msg="Not have charts!")


@router.post("/v1/editor/chart/info", response_model=Result[ChartDetail])
async def get_editor_chart_info(
    param: dict = Body(), editor_service: EditorService = Depends(get_edit_service)
):
    logger.info(f"get_editor_chart_info:{param}")
    conv_uid = param["con_uid"]
    chart_title = param["chart_title"]
    return editor_service.get_editor_chart_info(conv_uid, chart_title, CFG)


@router.post("/v1/editor/chart/run", response_model=Result[ChartRunData])
async def editor_chart_run(run_param: dict = Body()):
    logger.info(f"editor_chart_run:{run_param}")
    db_name = run_param["db_name"]
    sql = run_param["sql"]
    chart_type = run_param["chart_type"]

    # Validate input parameters
    if not db_name or not sql or not chart_type:
        return Result.failed("Required parameters missing")

    try:
        # Validate database type and prevent dangerous operations
        db_conn = CFG.local_db_manager.get_connector(db_name)
        db_type = getattr(db_conn, "db_type", "").lower()

        # Block dangerous operations for DuckDB
        if db_type == "duckdb":
            # Block file operations and system commands
            dangerous_keywords = [
                # File operations
                "copy",
                "export",
                "import",
                "load",
                "install",
                "read_",
                "write_",
                "save",
                "from_",
                "to_",
                # System commands
                "create_",
                "drop_",
                ".execute(",
                "system",
                "shell",
                # Additional DuckDB specific operations
                "attach",
                "detach",
                "pragma",
                "checkpoint",
                "load_extension",
                "unload_extension",
                # File paths
                "/'",
                "'/'",
                "\\",
                "://",
            ]
            sql_lower = sql.lower().replace(" ", "")  # Remove spaces to prevent bypass
            if any(keyword in sql_lower for keyword in dangerous_keywords):
                logger.warning(
                    f"Blocked dangerous SQL operation attempt in chart: {sql}"
                )
                return Result.failed(msg="Operation not allowed for security reasons")

            # Additional check for file path patterns
            if re.search(r"['\"].*[/\\].*['\"]", sql):
                logger.warning(f"Blocked file path in chart SQL: {sql}")
                return Result.failed(msg="File operations not allowed")

        dashboard_data_loader: DashboardDataLoader = DashboardDataLoader()

        start_time = time.time() * 1000

        # Execute query with timeout
        colunms, sql_result = db_conn.query_ex(sql, timeout=30)

        # Safely convert and process results
        field_names, chart_values = dashboard_data_loader.get_chart_values_by_data(
            colunms,
            [
                tuple(str(x) if x is not None else None for x in row)
                for row in sql_result
            ],
            sql,
        )

        # Calculate execution time
        end_time = time.time() * 1000
        sql_run_data: SqlRunData = SqlRunData(
            result_info="",
            run_cost=(end_time - start_time) / 1000,
            colunms=colunms,
            values=[list(row) for row in sql_result],
        )
        return Result.succ(
            ChartRunData(
                sql_data=sql_run_data, chart_values=chart_values, chart_type=chart_type
            )
        )
    except Exception as e:
        logger.exception("Chart sql run failed!")
        sql_result = SqlRunData(result_info=str(e), run_cost=0, colunms=[], values=[])
        return Result.succ(
            ChartRunData(sql_data=sql_result, chart_values=[], chart_type=chart_type)
        )


@router.post("/v1/chart/editor/submit", response_model=Result[bool])
async def chart_editor_submit(chart_edit_context: ChatChartEditContext = Body()):
    logger.info(f"sql_editor_submit:{chart_edit_context.__dict__}")

    chat_history_fac = ChatHistory()
    history_mem = chat_history_fac.get_store_instance(chart_edit_context.conv_uid)
    history_messages: List[OnceConversation] = history_mem.get_messages()
    if history_messages:
        dashboard_data_loader: DashboardDataLoader = DashboardDataLoader()
        db_conn = CFG.local_db_manager.get_connector(chart_edit_context.db_name)

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
                return Result.failed(msg=f"Edit chart exception!{str(e)}")
            history_mem.update(history_messages)
            return Result.succ(None)
    return Result.failed(msg="Edit Failed!")
