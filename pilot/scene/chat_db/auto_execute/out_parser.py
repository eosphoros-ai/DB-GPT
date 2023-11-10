import json
from typing import Dict, NamedTuple
import logging
import xml.etree.ElementTree as ET
from pilot.common.json_utils import serialize
from pilot.out_parser.base import BaseOutputParser, T
from pilot.configs.config import Config
from pilot.scene.chat_db.data_loader import DbDataLoader

CFG = Config()


class SqlAction(NamedTuple):
    sql: str
    thoughts: Dict


logger = logging.getLogger(__name__)


class DbChatOutputParser(BaseOutputParser):
    def __init__(self, sep: str, is_stream_out: bool):
        super().__init__(sep=sep, is_stream_out=is_stream_out)

    def parse_prompt_response(self, model_out_text):
        clean_str = super().parse_prompt_response(model_out_text)
        print("clean prompt response:", clean_str)
        response = json.loads(clean_str)
        for key in sorted(response):
            if key.strip() == "sql":
                sql = response[key]
            if key.strip() == "thoughts":
                thoughts = response[key]
        return SqlAction(sql, thoughts)

    def parse_view_response(self, speak, data, prompt_response) -> str:

        param = {}
        api_call_element = ET.Element("chart-view")
        try:
            df = data(prompt_response.sql)
            param["type"] = "response_table"
            param["sql"] = prompt_response.sql
            param["data"] = json.loads(df.to_json(orient='records', date_format='iso', date_unit='s'))
            view_json_str = json.dumps(param, default=serialize)
        except Exception as e:
            err_param ={}
            param["sql"] = prompt_response.sql
            err_param["type"] = "response_table"
            err_param["err_msg"] = str(e)
            view_json_str = json.dumps(err_param, default=serialize)

        api_call_element.text = view_json_str
        result = ET.tostring(api_call_element, encoding="utf-8")

        return speak + "\n" + result.decode("utf-8")




