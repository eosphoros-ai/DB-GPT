from typing import Dict, Type

from dbgpt.component import SystemApp, logger
from dbgpt.util.executor_utils import blocking_func_to_async
from dbgpt.util.tracer import trace
from dbgpt_app.scene import BaseChat, ChatScene
from dbgpt_app.scene.base_chat import ChatParam
from dbgpt_app.scene.chat_db.professional_qa.config import ChatWithDBQAConfig
from dbgpt_serve.datasource.manages import ConnectorManager


class ChatWithDbQA(BaseChat):
    """As a DBA, Chat DB Module, chat with combine DB meta schema"""

    chat_scene: str = ChatScene.ChatWithDbQA.value()

    @classmethod
    def param_class(cls) -> Type[ChatWithDBQAConfig]:
        return ChatWithDBQAConfig

    def __init__(self, chat_param: ChatParam, system_app: SystemApp):
        """Chat DB Module Initialization
        Args:
           - chat_param: Dict
            - chat_session_id: (str) chat session_id
            - current_user_input: (str) current user input
            - model_name:(str) llm model name
            - select_param:(str) dbname
        """
        self.db_name = chat_param.select_param
        self.database = None
        self.curr_config = chat_param.real_app_config(ChatWithDBQAConfig)
        super().__init__(chat_param=chat_param, system_app=system_app)

        if self.db_name is None:
            raise Exception(f"Database: {self.db_name} not found")
        if self.db_name:
            local_db_manager = ConnectorManager.get_instance(self.system_app)
            self.database = local_db_manager.get_connector(self.db_name)
            self.tables = self.database.get_table_names()
        if self.database is not None and self.database.is_graph_type():
            # When the current graph database retrieves source data from ChatDB, the
            # topk uses the sum of node table and edge table.
            self.top_k = len(list(self.tables))
        else:
            logger.info(
                "Dialect: "
                f"{self.database.db_type if self.database is not None else None}"
            )
            self.top_k = self.curr_config.schema_retrieve_top_k

    @trace()
    async def generate_input_values(self) -> Dict:
        try:
            from dbgpt_serve.datasource.service.db_summary_client import DBSummaryClient
        except ImportError:
            raise ValueError("Could not import DBSummaryClient. ")
        user_input = self.current_user_input.last_text
        table_infos = None
        if self.db_name:
            client = DBSummaryClient(system_app=self.system_app)
            try:
                table_infos = await blocking_func_to_async(
                    self._executor,
                    client.get_db_summary,
                    self.db_name,
                    user_input,
                    self.top_k,
                )
            except Exception as e:
                logger.error(f"Retrieved table info error: {str(e)}")
                table_infos = await blocking_func_to_async(
                    self._executor, self.database.table_simple_info
                )
                if len(table_infos) > self.curr_config.schema_max_tokens:
                    # Load all tables schema, must be less then schema_max_tokens
                    # Here we just truncate the table_infos
                    # TODO: Count the number of tokens by LLMClient
                    table_infos = table_infos[: self.curr_config.schema_max_tokens]

        input_values = {
            "input": user_input,
            "table_info": table_infos,
        }
        return input_values
