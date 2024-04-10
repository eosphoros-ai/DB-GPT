import logging
from typing import List, Optional, Union

from dbgpt._private.config import Config
from dbgpt.agent.resource.resource_api import AgentResource
from dbgpt.agent.resource.resource_db_api import ResourceDbClient
from dbgpt.component import ComponentType
from dbgpt.util.executor_utils import ExecutorFactory, blocking_func_to_async
from dbgpt.util.tracer import root_tracer

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
        conn = CFG.local_db_manager.get_connector(resource.value)
        return conn.db_type

    async def get_schema_link(
        self, db: str, question: Optional[str] = None
    ) -> Union[str, List[str]]:
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
            conn = CFG.local_db_manager.get_connector(db)
            table_infos = await blocking_func_to_async(
                self._executor, conn.table_simple_info
            )

        return table_infos

    async def query_to_df(self, db: str, sql: str):
        conn = CFG.local_db_manager.get_connector(db)
        return conn.run_to_df(sql)

    async def query(self, db: str, sql: str):
        conn = CFG.local_db_manager.get_connector(db)
        return conn.query_ex(sql)

    async def run_sql(self, db: str, sql: str):
        conn = CFG.local_db_manager.get_connector(db)
        return conn.run(sql)
