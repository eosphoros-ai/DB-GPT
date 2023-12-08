import json
import logging
from typing import NamedTuple
from dbgpt.core.interface.output_parser import BaseOutputParser
from dbgpt._private.config import Config

CFG = Config()


class ExcelAnalyzeResponse(NamedTuple):
    sql: str
    thoughts: str
    display: str


logger = logging.getLogger(__name__)


class ChatExcelOutputParser(BaseOutputParser):
    def __init__(self, is_stream_out: bool, **kwargs):
        super().__init__(is_stream_out=is_stream_out, **kwargs)

    def parse_prompt_response(self, model_out_text):
        clean_str = super().parse_prompt_response(model_out_text)
        print("clean prompt response:", clean_str)
        try:
            response = json.loads(clean_str)
            for key in sorted(response):
                if key.strip() == "sql":
                    sql = response[key].replace("\\", " ")
                if key.strip() == "thoughts":
                    thoughts = response[key]
                if key.strip() == "display":
                    display = response[key]
            return ExcelAnalyzeResponse(sql, thoughts, display)
        except Exception as e:
            raise ValueError(f"LLM Response Can't Parser! \n")

    def parse_view_response(self, speak, data, prompt_response) -> str:
        ### tool out data to table view
        return data
