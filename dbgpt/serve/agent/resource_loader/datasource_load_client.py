import logging
from typing import Any, Dict, List, Optional, Tuple, Union

from dbgpt._private.config import Config
from dbgpt.agent.resource.resource_api import AgentResource, ResourceType
from dbgpt.agent.resource.resource_db_api import ResourceDbClient
from dbgpt.component import ComponentType
from dbgpt.util.executor_utils import ExecutorFactory, blocking_func_to_async
from dbgpt.util.tracer import root_tracer, trace

CFG = Config()

logger = logging.getLogger(__name__)


class DatasourceLoadClient(ResourceDbClient):
    def __init__(self):
        super().__init__()
        # The executor to submit blocking function
        self._executor = CFG.SYSTEM_APP.get_component(
            ComponentType.EXECUTOR_DEFAULT, ExecutorFactory
        ).create()

    def get_data_type(self, resource: AgentResource) -> str:
        conn = CFG.LOCAL_DB_MANAGE.get_connect(resource.value)
        return conn.db_type

    async def a_get_schema_link(self, db: str, question: Optional[str] = None) -> str:
        try:
            from dbgpt.rag.summary.db_summary_client import DBSummaryClient
        except ImportError:
            raise ValueError("Could not import DBSummaryClient. ")
        client = DBSummaryClient(system_app=CFG.SYSTEM_APP)
        table_infos = None
        try:
            with root_tracer.start_span("ChatWithDbAutoExecute.get_db_summary"):
                table_infos = await blocking_func_to_async(
                    self._executor,
                    client.get_db_summary,
                    db,
                    question,
                    CFG.KNOWLEDGE_SEARCH_TOP_SIZE,
                )
        except Exception as e:
            print("db summary find error!" + str(e))
        if not table_infos:
            conn = CFG.LOCAL_DB_MANAGE.get_connect(db)
            table_infos = await blocking_func_to_async(
                self._executor, conn.table_simple_info
            )

        return table_infos

    async def a_query_to_df(self, db: str, sql: str):
        conn = CFG.LOCAL_DB_MANAGE.get_connect(db)
        return conn.run_to_df(sql)

    async def a_query(self, db: str, sql: str):
        conn = CFG.LOCAL_DB_MANAGE.get_connect(db)
        return conn.query_ex(sql)

    async def a_run_sql(self, db: str, sql: str):
        conn = CFG.LOCAL_DB_MANAGE.get_connect(db)
        return conn.run(sql)
