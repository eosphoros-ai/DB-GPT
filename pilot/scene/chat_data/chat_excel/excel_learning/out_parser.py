import json
import re
from abc import ABC, abstractmethod
from typing import Dict, NamedTuple, List
import pandas as pd
from pilot.utils import build_logger
from pilot.out_parser.base import BaseOutputParser, T
from pilot.configs.model_config import LOGDIR
from pilot.configs.config import Config

CFG = Config()


class ExcelResponse(NamedTuple):
    desciption: str
    clounms: List
    plans: List


logger = build_logger("chat_excel", LOGDIR + "ChatExcel.log")


class LearningExcelOutputParser(BaseOutputParser):
    def __init__(self, sep: str, is_stream_out: bool):
        super().__init__(sep=sep, is_stream_out=is_stream_out)

    def parse_prompt_response(self, model_out_text):
        clean_str = super().parse_prompt_response(model_out_text)
        print("clean prompt response:", clean_str)
        response = json.loads(clean_str)
        for key in sorted(response):
            if key.strip() == "DataAnalysis":
                desciption = response[key]
            if key.strip() == "ColumnAnalysis":
                clounms = response[key]
            if key.strip() == "AnalysisProgram":
                plans = response[key]
        return ExcelResponse(desciption=desciption, clounms=clounms, plans=plans)

    def parse_view_response(self, speak, data) -> str:
        ### tool out data to table view
        html_title = f"### **数据简介:**\n{data.desciption} \n"
        html_colunms = f"### **数据结构:**\n"
        for item in data.clounms:
            keys = item.keys()
            for key in keys:
                html_colunms = html_colunms + f"-   **{key}**:{item[key]} \n"

        html_plans = f"\n ### **分析计划:** \n"
        for item in data.plans:
            html_plans = html_plans + f"-   {item} \n"
        html = f"""{html_title}{html_colunms}{html_plans}"""
        return html
