import json
import logging
import re
import time
from typing import Dict, List, Tuple

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


def sanitize_sql(sql: str, db_type: str = None) -> Tuple[bool, str, dict]:
    """Simple SQL sanitizer to prevent injection.

    Returns:
        Tuple of (is_safe, reason, params)
    """
    # Normalize SQL (remove comments and excess whitespace)
    sql = re.sub(r"/\*.*?\*/", " ", sql)
    sql = re.sub(r"--.*?$", " ", sql, flags=re.MULTILINE)
    sql = re.sub(r"\s+", " ", sql).strip()

    # Block multiple statements
    if re.search(r";\s*(?!--|\*/|$)", sql):
        return False, "Multiple SQL statements are not allowed", {}

    # Block dangerous operations for all databases
    dangerous_patterns = [
        r"(?i)INTO\s+(?:OUT|DUMP)FILE",
        r"(?i)LOAD\s+DATA",
        r"(?i)SYSTEM",
        r"(?i)EXEC\s+",
        r"(?i)SHELL\b",
        r"(?i)DROP\s+DATABASE",
        r"(?i)DROP\s+USER",
        r"(?i)GRANT\s+",
        r"(?i)REVOKE\s+",
        r"(?i)ALTER\s+(USER|DATABASE)",
    ]

    # Add DuckDB specific patterns
    if db_type == "duckdb":
        dangerous_patterns.extend(
            [
                r"(?i)COPY\b",
                r"(?i)EXPORT\b",
                r"(?i)IMPORT\b",
                r"(?i)INSTALL\b",
                r"(?i)READ_\w+\b",
                r"(?i)WRITE_\w+\b",
                r"(?i)\.EXECUTE\(",
                r"(?i)PRAGMA\b",
            ]
        )

    for pattern in dangerous_patterns:
        if re.search(pattern, sql):
            return False, f"Operation not allowed: {pattern}", {}

    # Allow SELECT, CREATE TABLE, INSERT, UPDATE, and DELETE operations
    # We're no longer restricting to read-only operations
    allowed_operations = re.match(
        r"(?i)^\s*(SELECT|CREATE\s+TABLE|INSERT\s+INTO|UPDATE|DELETE\s+FROM|ALTER\s+TABLE)\b",
        sql,
    )
    if not allowed_operations:
        return (
            False,
            "Operation not supported. Only SELECT, CREATE TABLE, INSERT, UPDATE, "
            "DELETE and ALTER TABLE operations are allowed",
            {},
        )

    # Extract parameters (simplified)
    params = {}
    param_count = 0

    # Extract string literals
    def replace_string(match):
        nonlocal param_count
        param_name = f"param_{param_count}"
        params[param_name] = match.group(1)
        param_count += 1
        return f":{param_name}"

    # Replace string literals with parameters
    parameterized_sql = re.sub(r"'([^']*)'", replace_string, sql)

    return True, parameterized_sql, params


@router.post("/v1/editor/sql/run", response_model=Result[SqlRunData])
async def editor_sql_run(run_param: dict = Body()):
    logger.info(f"editor_sql_run:{run_param}")
    db_name = run_param["db_name"]
    sql = run_param["sql"]

    if not db_name and not sql:
        return Result.failed(msg="SQL run param error！")

    # Get database connection
    conn = CFG.local_db_manager.get_connector(db_name)
    db_type = getattr(conn, "db_type", "").lower()

    # Sanitize and parameterize the SQL query
    is_safe, result, params = sanitize_sql(sql, db_type)
    if not is_safe:
        logger.warning(f"Blocked dangerous SQL: {sql}")
        return Result.failed(msg=f"Operation not allowed: {result}")

    try:
        start_time = time.time() * 1000
        # Use the parameterized query and parameters
        colunms, sql_result = conn.query_ex(result, params=params, timeout=30)
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
async def chart_run(run_param: dict = Body()):
    logger.info(f"chart_run:{run_param}")
    db_name = run_param["db_name"]
    sql = run_param["sql"]
    chart_type = run_param["chart_type"]

    # Get database connection
    db_conn = CFG.local_db_manager.get_connector(db_name)
    db_type = getattr(db_conn, "db_type", "").lower()

    # Sanitize and parameterize the SQL query
    is_safe, result, params = sanitize_sql(sql, db_type)
    if not is_safe:
        logger.warning(f"Blocked dangerous SQL: {sql}")
        return Result.failed(msg=f"Operation not allowed: {result}")

    try:
        start_time = time.time() * 1000
        # Use the parameterized query and parameters
        colunms, sql_result = db_conn.query_ex(result, params=params, timeout=30)
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

        chart_values = []
        for i in range(len(sql_result)):
            row = sql_result[i]
            chart_values.append(
                {
                    "name": row[0],
                    "type": "value",
                    "value": row[1] if len(row) > 1 else "0",
                }
            )

        chart_data: ChartRunData = ChartRunData(
            sql_data=sql_run_data, chart_values=chart_values, chart_type=chart_type
        )
        return Result.succ(chart_data)
    except Exception as e:
        logger.error(f"chart_run exception: {str(e)}", exc_info=True)
        return Result.failed(msg=str(e))


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
