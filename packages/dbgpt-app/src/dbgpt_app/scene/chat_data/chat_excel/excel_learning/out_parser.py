import json
import logging
from typing import Dict, List, NamedTuple

from dbgpt.core.interface.output_parser import BaseOutputParser
from dbgpt_app.scene.chat_data.chat_excel.excel_reader import TransformedExcelResponse


class ExcelResponse(NamedTuple):
    desciption: str
    clounms: List
    plans: List


logger = logging.getLogger(__name__)


class LearningExcelOutputParser(BaseOutputParser):
    def __init__(self, is_stream_out: bool = False, **kwargs):
        super().__init__(is_stream_out=is_stream_out, **kwargs)
        self.is_downgraded = False

    def parse_prompt_response(self, model_out_text):
        description = ""
        columns = []
        plans = []
        try:
            clean_str = super().parse_prompt_response(model_out_text)
            logger.info(f"parse_prompt_response:{model_out_text},{model_out_text}")
            response = json.loads(clean_str)
            for key in sorted(response):
                if key.strip() == "data_analysis":
                    description = response[key]
                if key.strip() == "column_analysis":
                    columns = response[key]
                if key.strip() == "analysis_program":
                    plans = response[key]
            return TransformedExcelResponse(
                description=description, columns=columns, plans=plans
            )
        except Exception as e:
            logger.error(f"parse_prompt_response failed: {e}")
            for name in self.data_schema:
                columns.append({name: "-"})
            return TransformedExcelResponse(
                description=model_out_text, columns=columns, plans=plans
            )

    def _build_columns_html(self, columns: List[Dict[str, str]]) -> str:
        html_columns = "### **Data Structure**\n"
        column_index = 0
        for item in columns:
            column_index += 1
            column_name = item.get("new_column_name", "")
            old_column_name = item.get("old_column_name", "")
            column_description = item.get("column_description", "")
            html_columns += (
                f"- **{column_index}. {column_name}({old_column_name})**: "
                f"_{column_description}_\n"
            )
        return html_columns

    def __build_plans_html(self, plans_data):
        html_plans = "### **Analysis plans**\n"
        index = 0
        if plans_data:
            for item in plans_data:
                index += 1
                html_plans = html_plans + f"{item} \n"
        return html_plans

    def parse_view_response(
        self, speak, data: TransformedExcelResponse, prompt_response
    ) -> str:
        if data and not isinstance(data, str):
            ### tool out data to table view
            html_title = f"### **Data Summary**\n{data.description} "
            html_columns = self._build_columns_html(data.columns)
            html_plans = self.__build_plans_html(data.plans)

            html = f"""{html_title}\n{html_columns}\n{html_plans}"""
            return html
        else:
            return speak
