import json
import os
import uuid
from typing import Dict, List

from dbgpt import SystemApp
from dbgpt.util.executor_utils import blocking_func_to_async
from dbgpt.util.tracer import trace
from dbgpt_app.scene import BaseChat, ChatScene
from dbgpt_app.scene.chat_dashboard.data_loader import DashboardDataLoader
from dbgpt_app.scene.chat_dashboard.data_preparation.report_schma import (
    ChartData,
    ReportData,
)
from dbgpt_serve.datasource.manages import ConnectorManager


class ChatDashboard(BaseChat):
    chat_scene: str = ChatScene.ChatDashboard.value()
    report_name: str
    """Chat Dashboard to generate dashboard chart"""

    def __init__(self, chat_param: Dict, system_app: SystemApp = None):
        """Chat Dashboard Module Initialization
        Args:
           - chat_param: Dict
            - chat_session_id: (str) chat session_id
            - current_user_input: (str) current user input
            - model_name:(str) llm model name
            - select_param:(str) dbname
        """
        self.db_name = chat_param["select_param"]
        chat_param["chat_mode"] = ChatScene.ChatDashboard
        super().__init__(chat_param=chat_param, system_app=system_app)
        if not self.db_name:
            raise ValueError(f"{ChatScene.ChatDashboard.value} mode should choose db!")
        self.db_name = self.db_name
        self.report_name = chat_param.get("report_name", "report")
        local_db_manager = ConnectorManager.get_instance(self.system_app)
        self.database = local_db_manager.get_connector(self.db_name)

        self.top_k: int = 5
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

        client = DBSummaryClient(system_app=self.system_app)
        try:
            table_infos = await blocking_func_to_async(
                self._executor,
                client.get_db_summary,
                self.db_name,
                self.current_user_input,
                self.top_k,
            )
            print("dashboard vector find tables:{}", table_infos)
        except Exception as e:
            print("db summary find error!" + str(e))

        input_values = {
            "input": self.current_user_input,
            "dialect": self.database.dialect,
            "table_info": self.database.table_simple_info(),
            "supported_chat_type": self.dashboard_template["supported_chart_type"],
        }

        return input_values

    def do_action(self, prompt_response):
        ### TODO 记录整体信息，处理成功的，和未成功的分开记录处理
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
                # TODO 修复流程
                print(str(e))
        return ReportData(
            conv_uid=self.chat_session_id,
            template_name=self.report_name,
            template_introduce=None,
            charts=chart_datas,
        )
