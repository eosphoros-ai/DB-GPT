import json
import logging

from typing import NamedTuple, List
from dbgpt.core.interface.output_parser import BaseOutputParser
from dbgpt.app.scene import ChatScene


class ChartItem(NamedTuple):
    sql: str
    title: str
    thoughts: str
    showcase: str


logger = logging.getLogger(__name__)


class ChatDashboardOutputParser(BaseOutputParser):
    def __init__(self, is_stream_out: bool, **kwargs):
        super().__init__(is_stream_out=is_stream_out, **kwargs)

    def parse_prompt_response(self, model_out_text):
        clean_str = super().parse_prompt_response(model_out_text)
        print("clean prompt response:", clean_str)
        response = json.loads(clean_str)
        chart_items: List[ChartItem] = []
        if not isinstance(response, list):
            response = [response]
        for item in response:
            chart_items.append(
                ChartItem(
                    item["sql"].replace("\\", " "),
                    item["title"],
                    item["thoughts"],
                    item["showcase"],
                )
            )
        return chart_items

    def parse_view_response(self, speak, data, prompt_response) -> str:
        return json.dumps(data.prepare_dict())

    @property
    def _type(self) -> str:
        return ChatScene.ChatDashboard.value
