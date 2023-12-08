import json
import logging
from typing import NamedTuple, List
from dbgpt.core.interface.output_parser import BaseOutputParser


class ExcelResponse(NamedTuple):
    desciption: str
    clounms: List
    plans: List


logger = logging.getLogger(__name__)


class LearningExcelOutputParser(BaseOutputParser):
    def __init__(self, is_stream_out: bool, **kwargs):
        super().__init__(is_stream_out=is_stream_out, **kwargs)
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
            clounms = []
            for name in self.data_schema:
                clounms.append({name: "-"})
            return ExcelResponse(desciption=model_out_text, clounms=clounms, plans=None)

    def __build_colunms_html(self, clounms_data):
        html_colunms = f"### **Data Structure**\n"
        column_index = 0
        for item in clounms_data:
            column_index += 1
            keys = item.keys()
            for key in keys:
                html_colunms = (
                    html_colunms + f"- **{column_index}.[{key}]**   _{item[key]}_\n"
                )
        return html_colunms

    def __build_plans_html(self, plans_data):
        html_plans = f"### **Analysis plans**\n"
        index = 0
        if plans_data:
            for item in plans_data:
                index += 1
                html_plans = html_plans + f"{item} \n"
        return html_plans

    def parse_view_response(self, speak, data, prompt_response) -> str:
        if data and not isinstance(data, str):
            ### tool out data to table view
            html_title = f"### **Data Summary**\n{data.desciption} "
            html_colunms = self.__build_colunms_html(data.clounms)
            html_plans = self.__build_plans_html(data.plans)

            html = f"""{html_title}\n{html_colunms}\n{html_plans}"""
            return html
        else:
            return speak
