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
    thoughts: Dict


class PluginChatOutputParser(BaseOutputParser):
    def parse_prompt_response(self, model_out_text) -> T:
        response = json.loads(super().parse_prompt_response(model_out_text))
        command, thoughts = response["command"], response["thoughts"]
        return PluginAction(command, thoughts)

    def parse_view_response(self, speak, data) -> str:
        ### tool out data to table view
        print(f"parse_view_response:{speak},{str(data)}")
        view_text = f"##### {speak}" + "\n" + str(data)
        return view_text

    def get_format_instructions(self) -> str:
        pass
