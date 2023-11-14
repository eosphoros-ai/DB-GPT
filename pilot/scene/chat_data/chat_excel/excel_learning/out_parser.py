import json
import logging
from typing import Dict, NamedTuple, List
from pilot.out_parser.base import BaseOutputParser, T
from pilot.configs.config import Config

CFG = Config()


class ExcelResponse(NamedTuple):
    desciption: str
    clounms: List
    plans: List


logger = logging.getLogger(__name__)


class LearningExcelOutputParser(BaseOutputParser):
    def __init__(self, sep: str, is_stream_out: bool):
        super().__init__(sep=sep, is_stream_out=is_stream_out)
        self.is_downgraded = False

    def parse_prompt_response(self, model_out_text):
        try:
            clean_str = super().parse_prompt_response(model_out_text)
            logger.info(f"parse_prompt_response:{model_out_text},{model_out_text}")
            response = json.loads(clean_str)
            for key in sorted(response):
                if key.strip() == "DataAnalysis":
                    desciption = response[key]
                if key.strip() == "ColumnAnalysis":
                    clounms = response[key]
                if key.strip() == "AnalysisProgram":
                    plans = response[key]
            return ExcelResponse(desciption=desciption, clounms=clounms, plans=plans)
        except Exception as e:
            logger.error(f"parse_prompt_response Faild!{str(e)}")
            self.is_downgraded = True
            return ExcelResponse(
                desciption=model_out_text, clounms=self.data_schema, plans=None
            )

    def parse_view_response(self, speak, data, prompt_response) -> str:
        if data and not isinstance(data, str):
            ### tool out data to table view
            html_title = f"### **Data Summary**\n{data.desciption} "
            html_colunms = f"### **Data Structure**\n"
            if self.is_downgraded:
                column_index = 0
                for item in data.clounms:
                    column_index += 1
                    html_colunms = (
                        html_colunms + f"- **{column_index}.[{item}]**   _未知_\n"
                    )
            else:
                column_index = 0
                for item in data.clounms:
                    column_index += 1
                    keys = item.keys()
                    for key in keys:
                        html_colunms = (
                            html_colunms
                            + f"- **{column_index}.[{key}]**   _{item[key]}_\n"
                        )

            html_plans = f"### **Recommended analysis plan**\n"
            index = 0
            if data.plans:
                for item in data.plans:
                    index += 1
                    html_plans = html_plans + f"{item} \n"
            html = f"""{html_title}\n{html_colunms}\n{html_plans}"""
            return html
        else:
            return speak
