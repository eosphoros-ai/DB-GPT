from typing import Dict

from dbgpt.component import SystemApp, logger
from dbgpt.util.executor_utils import blocking_func_to_async
from dbgpt.util.tracer import trace
from dbgpt_app.scene import BaseChat, ChatScene
from dbgpt_serve.datasource.manages import ConnectorManager


class ChatWithDbQA(BaseChat):
    chat_scene: str = ChatScene.ChatWithDbQA.value()

    keep_end_rounds = 5

    """As a DBA, Chat DB Module, chat with combine DB meta schema """

    def __init__(self, chat_param: Dict, system_app: SystemApp = None):
        """Chat DB Module Initialization
        Args:
           - chat_param: Dict
            - chat_session_id: (str) chat session_id
            - current_user_input: (str) current user input
            - model_name:(str) llm model name
            - select_param:(str) dbname
        """
        self.db_name = chat_param["select_param"]
        chat_param["chat_mode"] = ChatScene.ChatWithDbQA
        super().__init__(chat_param=chat_param, system_app=system_app)

        if self.db_name:
            local_db_manager = ConnectorManager.get_instance(self.system_app)
            self.database = local_db_manager.get_connector(self.db_name)
            self.tables = self.database.get_table_names()
        if self.database.is_graph_type():
            # When the current graph database retrieves source data from ChatDB, the
            # topk uses the sum of node table and edge table.
            self.top_k = len(self.tables["vertex_tables"]) + len(
                self.tables["edge_tables"]
            )
        else:
            print(self.database.db_type)
            self.top_k = (
                self.web_config.rag.knowledge_search_top_k
                if len(self.tables) > self.web_config.rag.knowledge_search_top_k
                else len(self.tables)
            )

    @trace()
    async def generate_input_values(self) -> Dict:
        try:
            from dbgpt_serve.datasource.service.db_summary_client import DBSummaryClient
        except ImportError:
            raise ValueError("Could not import DBSummaryClient. ")
        if self.db_name:
            client = DBSummaryClient(system_app=self.system_app)
            try:
                table_infos = await blocking_func_to_async(
                    self._executor,
                    client.get_db_summary,
                    self.db_name,
                    self.current_user_input,
                    self.top_k,
                )
            except Exception as e:
                logger.error("db summary find error!" + str(e))
                # table_infos = self.database.table_simple_info()
                table_infos = await blocking_func_to_async(
                    self._executor, self.database.table_simple_info
                )

        input_values = {
            "input": self.current_user_input,
            # "top_k": str(self.top_k),
            # "dialect": dialect,
            "table_info": table_infos,
        }
        return input_values
