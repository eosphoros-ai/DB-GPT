import json
import os
import uuid
from typing import Dict, NamedTuple, List
from pilot.scene.base_message import (
    HumanMessage,
    ViewMessage,
)
from pilot.scene.base_chat import BaseChat
from pilot.scene.base import ChatScene
from pilot.common.sql_database import Database
from pilot.configs.config import Config
from pilot.common.markdown_text import (
    generate_htm_table,
)
from pilot.scene.chat_dashboard.prompt import prompt
from pilot.scene.chat_dashboard.data_preparation.report_schma import (
    ChartData,
    ReportData,
)

CFG = Config()


class ChatDashboard(BaseChat):
    chat_scene: str = ChatScene.ChatDashboard.value()
    report_name: str
    """Number of results to return from the query"""

    def __init__(self, chat_session_id, db_name, user_input, report_name):
        """ """
        super().__init__(
            chat_mode=ChatScene.ChatDashboard,
            chat_session_id=chat_session_id,
            current_user_input=user_input,
        )
        if not db_name:
            raise ValueError(f"{ChatScene.ChatDashboard.value} mode should chose db!")
        self.db_name = db_name
        self.report_name = report_name
        self.database = CFG.local_db
        # 准备DB信息(拿到指定库的链接)
        self.db_connect = self.database.get_session(self.db_name)
        self.top_k: int = 5
        self.dashboard_template = self.__load_dashboard_template(report_name)

    def __load_dashboard_template(self, template_name):
        current_dir = os.getcwd()
        print(current_dir)

        current_dir = os.path.dirname(os.path.abspath(__file__))
        with open(f"{current_dir}/template/{template_name}/dashboard.json", "r") as f:
            data = f.read()
        return json.loads(data)

    def generate_input_values(self):
        try:
            from pilot.summary.db_summary_client import DBSummaryClient
        except ImportError:
            raise ValueError("Could not import DBSummaryClient. ")
        client = DBSummaryClient()
        input_values = {
            "input": self.current_user_input,
            "dialect": self.database.dialect,
            "table_info": self.database.table_simple_info(self.db_connect),
            "supported_chat_type": self.dashboard_template["supported_chart_type"]
            # "table_info": client.get_similar_tables(dbname=self.db_name, query=self.current_user_input, topk=self.top_k)
        }

        return input_values

    def do_action(self, prompt_response):
        ### TODO 记录整体信息，处理成功的，和未成功的分开记录处理
        chart_datas: List[ChartData] = []
        for chart_item in prompt_response:
            try:
                datas = self.database.run(self.db_connect, chart_item.sql)
                chart_datas.append(
                    ChartData(
                        chart_uid=str(uuid.uuid1()),
                        chart_name=chart_item.title,
                        chart_type=chart_item.showcase,
                        chart_desc=chart_item.thoughts,
                        chart_sql=chart_item.sql,
                        column_name=datas[0],
                        values=datas,
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
