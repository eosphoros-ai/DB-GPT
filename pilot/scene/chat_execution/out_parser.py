import json
import re
from abc import ABC, abstractmethod
from typing import Dict, NamedTuple
import pandas as pd
from pilot.utils import build_logger
from pilot.out_parser.base import BaseOutputParser, T
from pilot.configs.model_config import LOGDIR


logger = build_logger("webserver", LOGDIR + "DbChatOutputParser.log")


class PluginAction(NamedTuple):
    command: Dict
    speak: str
    reasoning:str
    thoughts: str


class PluginChatOutputParser(BaseOutputParser):
    def parse_prompt_response(self, model_out_text) -> T:
        response = json.loads(super().parse_prompt_response(model_out_text))
        command, thoughts, speak, reasoning = response["command"], response["thoughts"], response["speak"], response["reasoning"]
        return PluginAction(command, speak, reasoning, thoughts)

    def parse_view_response(self, speak, data) -> str:
        ### tool out data to table view
        print(f"parse_view_response:{speak},{str(data)}")
        view_text = f"##### {speak}" + "\n" + str(data)
        return view_text

    def get_format_instructions(self) -> str:
        pass
