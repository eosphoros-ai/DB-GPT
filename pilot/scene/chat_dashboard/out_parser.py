import json
import re
from dataclasses import dataclass, asdict
from abc import ABC, abstractmethod
from typing import Dict, NamedTuple, List
import pandas as pd
from pilot.utils import build_logger
from pilot.out_parser.base import BaseOutputParser, T
from pilot.configs.model_config import LOGDIR
from pilot.scene.base import ChatScene


class ChartItem(NamedTuple):
    sql: str
    title: str
    thoughts: str
    showcase: str


logger = build_logger("webserver", LOGDIR + "ChatDashboardOutputParser.log")


class ChatDashboardOutputParser(BaseOutputParser):
    def __init__(self, sep: str, is_stream_out: bool):
        super().__init__(sep=sep, is_stream_out=is_stream_out)

    def parse_prompt_response(self, model_out_text):
        clean_str = super().parse_prompt_response(model_out_text)
        print("clean prompt response:", clean_str)
        response = json.loads(clean_str)
        chart_items: List[ChartItem] = []
        for item in response:
            chart_items.append(
                ChartItem(
                    item["sql"], item["title"], item["thoughts"], item["showcase"]
                )
            )
        return chart_items

    def parse_view_response(self, speak, data) -> str:
        return json.dumps(data.prepare_dict())

    @property
    def _type(self) -> str:
        return ChatScene.ChatDashboard.value
