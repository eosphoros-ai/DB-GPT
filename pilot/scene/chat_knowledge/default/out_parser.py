import json
import re
from abc import ABC, abstractmethod
from typing import Dict, NamedTuple
import pandas as pd
from pilot.utils import build_logger
from pilot.out_parser.base import BaseOutputParser, T
from pilot.configs.model_config import LOGDIR


logger = build_logger("webserver", LOGDIR + "DbChatOutputParser.log")


class NormalChatOutputParser(BaseOutputParser):
    def parse_prompt_response(self, model_out_text) -> T:
        return model_out_text

    def get_format_instructions(self) -> str:
        pass
