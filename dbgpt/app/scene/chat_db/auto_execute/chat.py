from typing import Dict

from dbgpt.agent.commands.command_mange import ApiCall
from dbgpt.app.scene import BaseChat, ChatScene
from dbgpt._private.config import Config
from dbgpt.util.executor_utils import blocking_func_to_async
from dbgpt.util.tracer import root_tracer, trace

CFG = Config()


class ChatWithDbAutoExecute(BaseChat):
    chat_scene: str = ChatScene.ChatWithDbExecute.value()

    """Number of results to return from the query"""

    def __init__(self, chat_param: Dict):
        """Chat Data Module Initialization
        Args:
           - chat_param: Dict
            - chat_session_id: (str) chat session_id
            - current_user_input: (str) current user input
            - model_name:(str) llm model name
            - select_param:(str) dbname
        """
        chat_mode = ChatScene.ChatWithDbExecute
        self.db_name = chat_param["select_param"]
        chat_param["chat_mode"] = chat_mode
        """ """
        super().__init__(
            chat_param=chat_param,
        )
        if not self.db_name:
            raise ValueError(
                f"{ChatScene.ChatWithDbExecute.value} mode should chose db!"
            )
        with root_tracer.start_span(
            "ChatWithDbAutoExecute.get_connect", metadata={"db_name": self.db_name}
        ):
            self.database = CFG.LOCAL_DB_MANAGE.get_connect(self.db_name)

        self.top_k: int = 50
        self.api_call = ApiCall(display_registry=CFG.command_disply)

    @trace()
    async def generate_input_values(self) -> Dict:
        """
        generate input values
        """
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
                    self.db_name,
                    self.current_user_input,
                    CFG.KNOWLEDGE_SEARCH_TOP_SIZE,
                )
        except Exception as e:
            print("db summary find error!" + str(e))
        if not table_infos:
            table_infos = await blocking_func_to_async(
                self._executor, self.database.table_simple_info
            )

        input_values = {
            "db_name": self.db_name,
            "user_input": self.current_user_input,
            "top_k": str(self.top_k),
            "dialect": self.database.dialect,
            "table_info": table_infos,
            "display_type": self._generate_numbered_list(),
        }
        return input_values

    def stream_plugin_call(self, text):
        text = text.replace("\n", " ")
        print(f"stream_plugin_call:{text}")
        return self.api_call.display_sql_llmvis(text, self.database.run_to_df)

    def do_action(self, prompt_response):
        print(f"do_action:{prompt_response}")
        return self.database.run_to_df
