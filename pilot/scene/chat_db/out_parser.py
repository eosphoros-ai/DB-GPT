import json
from abc import ABC, abstractmethod
from typing import (
    Any,
    Dict,
    Generic,
    List,
    NamedTuple,
    Optional,
    Sequence,
    TypeVar,
    Union,
)
import pandas as pd

from pilot.out_parser.base import BaseOutputParser, T


class SqlAction(NamedTuple):
    sql: str
    thoughts: Dict


class DbChatOutputParser(BaseOutputParser):

    def __init__(self, sep:str, is_stream_out: bool):
        super().__init__(sep=sep, is_stream_out=is_stream_out )


    def parse_model_server_out(self, response) -> str:
        return super().parse_model_server_out(response)

    def parse_prompt_response(self, model_out_text):
        cleaned_output = model_out_text.rstrip()
        if "```json" in cleaned_output:
            _, cleaned_output = cleaned_output.split("```json")
        if "```" in cleaned_output:
            cleaned_output, _ = cleaned_output.split("```")
        if cleaned_output.startswith("```json"):
            cleaned_output = cleaned_output[len("```json"):]
        if cleaned_output.startswith("```"):
            cleaned_output = cleaned_output[len("```"):]
        if cleaned_output.endswith("```"):
            cleaned_output = cleaned_output[: -len("```")]
        cleaned_output = cleaned_output.strip()
        response = json.loads(cleaned_output)
        sql, thoughts = response["sql"], response["thoughts"]

        return SqlAction(sql, thoughts)

    def parse_view_response(self, speak, data) -> str:
        ### tool out data to table view
        df = pd.DataFrame(data[1:], columns=data[0])
        table_style = """<style> 
            table{border-collapse:collapse;width:100%;height:80%;margin:0 auto;float:center;border: 1px solid #007bff; background-color:#333; color:#fff}th,td{border:1px solid #ddd;padding:3px;text-align:center}th{background-color:#C9C3C7;color: #fff;font-weight: bold;}tr:nth-child(even){background-color:#444}tr:hover{background-color:#444}
         </style>"""
        html_table = df.to_html(index=False, escape=False)
        html = f"<html><head>{table_style}</head><body>{html_table}</body></html>"
        view_text = f"##### {str(speak)}" + "\n" + html.replace("\n", " ")
        return view_text

    @property
    def _type(self) -> str:
        return "sql_chat"
