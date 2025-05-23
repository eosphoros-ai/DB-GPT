import json
import logging
import os
import uuid
from typing import Dict, List, Type

from dbgpt import SystemApp
from dbgpt.util.executor_utils import blocking_func_to_async
from dbgpt.util.tracer import trace
from dbgpt_app.scene import BaseChat, ChatScene
from dbgpt_app.scene.base_chat import ChatParam
from dbgpt_app.scene.chat_dashboard.config import ChatDashboardConfig
from dbgpt_app.scene.chat_dashboard.data_loader import DashboardDataLoader
from dbgpt_app.scene.chat_dashboard.data_preparation.report_schma import (
    ChartData,
    ReportData,
)
from dbgpt_serve.datasource.manages import ConnectorManager

logger = logging.getLogger(__name__)


class ChatDashboard(BaseChat):
    chat_scene: str = ChatScene.ChatDashboard.value()
    report_name: str
    """Chat Dashboard to generate dashboard chart"""

    @classmethod
    def param_class(cls) -> Type[ChatDashboardConfig]:
        return ChatDashboardConfig

    def __init__(self, chat_param: ChatParam, system_app: SystemApp):
        """Chat Dashboard Module Initialization
        Args:
           - chat_param: Dict
            - chat_session_id: (str) chat session_id
            - current_user_input: (str) current user input
            - model_name:(str) llm model name
            - select_param:(str) dbname
        """
        self.db_name = chat_param.select_param
        super().__init__(chat_param=chat_param, system_app=system_app)
        if not self.db_name:
            raise ValueError(f"{ChatScene.ChatDashboard.value} mode should choose db!")
        self.db_name = self.db_name
        self.report_name = "report"
        local_db_manager = ConnectorManager.get_instance(self.system_app)
        self.database = local_db_manager.get_connector(self.db_name)
        self.curr_config = chat_param.real_app_config(ChatDashboardConfig)

        self.dashboard_template = self.__load_dashboard_template(self.report_name)

    def __load_dashboard_template(self, template_name):
        current_dir = os.getcwd()
        print(current_dir)

        current_dir = os.path.dirname(os.path.abspath(__file__))
        with open(f"{current_dir}/template/{template_name}/dashboard.json", "r") as f:
            data = f.read()
        return json.loads(data)

    @trace()
    async def generate_input_values(self) -> Dict:
        try:
            from dbgpt_serve.datasource.service.db_summary_client import DBSummaryClient
        except ImportError:
            raise ValueError("Could not import DBSummaryClient. ")

        user_input = self.current_user_input.last_text
        client = DBSummaryClient(system_app=self.system_app)
        try:
            table_infos = await blocking_func_to_async(
                self._executor,
                client.get_db_summary,
                self.db_name,
                user_input,
                self.curr_config.schema_retrieve_top_k,
            )
            logger.info(f"Retrieved table info: {table_infos}")
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
            "dialect": self.database.dialect,
            "table_info": table_infos,
            "supported_chat_type": self.dashboard_template["supported_chart_type"],
        }

        # Mapping variable names: compatible with custom prompt template variable names
        # Get the input_variables of the current prompt
        input_variables = []
        if hasattr(self.prompt_template, "prompt") and hasattr(
            self.prompt_template.prompt, "input_variables"
        ):
            input_variables = self.prompt_template.prompt.input_variables
        # Compatible with question and user_input
        if "question" in input_variables:
            input_values["question"] = self.current_user_input
        if "user_input" in input_variables:
            input_values["user_input"] = self.current_user_input

        return input_values

    def do_action(self, prompt_response):
        # TODO: Record the overall information, and record the successful and
        #  unsuccessful processing separately
        chart_datas: List[ChartData] = []
        dashboard_data_loader = DashboardDataLoader()
        for chart_item in prompt_response:
            try:
                field_names, values = dashboard_data_loader.get_chart_values_by_conn(
                    self.database, chart_item.sql
                )
                chart_datas.append(
                    ChartData(
                        chart_uid=str(uuid.uuid1()),
                        chart_name=chart_item.title,
                        chart_type=chart_item.showcase,
                        chart_desc=chart_item.thoughts,
                        chart_sql=chart_item.sql,
                        column_name=field_names,
                        values=values,
                    )
                )
            except Exception as e:
                logger.warning(f"Failed to get chart data: {str(e)}")
        return ReportData(
            conv_uid=self.chat_session_id,
            template_name=self.report_name,
            template_introduce=None,
            charts=chart_datas,
        )
