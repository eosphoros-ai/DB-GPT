import json
from typing import Optional

import yaml

from ..base import Vis


def default_chart_type_promot() -> str:
    """this function is moved from excel_analyze/chat.py,and used by subclass.
    Returns:

    """
    antv_charts = [
        {"response_line_chart": "used to display comparative trend analysis data"},
        {
            "response_pie_chart": "suitable for scenarios such as proportion and distribution statistics"
        },
        {
            "response_table": "suitable for display with many display columns or non-numeric columns"
        },
        # {"response_data_text":" the default display method, suitable for single-line or simple content display"},
        {
            "response_scatter_plot": "Suitable for exploring relationships between variables, detecting outliers, etc."
        },
        {
            "response_bubble_chart": "Suitable for relationships between multiple variables, highlighting outliers or special situations, etc."
        },
        {
            "response_donut_chart": "Suitable for hierarchical structure representation, category proportion display and highlighting key categories, etc."
        },
        {
            "response_area_chart": "Suitable for visualization of time series data, comparison of multiple groups of data, analysis of data change trends, etc."
        },
        {
            "response_heatmap": "Suitable for visual analysis of time series data, large-scale data sets, distribution of classified data, etc."
        },
    ]
    return "\n".join(
        f"{key}:{value}"
        for dict_item in antv_charts
        for key, value in dict_item.items()
    )


class VisChart(Vis):
    def render_prompt(self):
        return default_chart_type_promot()

    async def generate_param(self, **kwargs) -> Optional[str]:
        chart = kwargs.get("chart", None)
        data_df = kwargs.get("data_df", None)

        if not chart:
            raise ValueError(
                f"Parameter information is missing and {self.vis_tag} protocol conversion cannot be performed."
            )

        sql = chart.get("sql", None)
        param = {}
        if not sql or len(sql) <= 0:
            return None

        param["sql"] = sql
        param["type"] = chart.get("display_type", "response_table")
        param["title"] = chart.get("title", "")
        param["describe"] = chart.get("thought", "")

        param["data"] = json.loads(
            data_df.to_json(orient="records", date_format="iso", date_unit="s")
        )
        return param

    @classmethod
    def vis_tag(cls):
        return "vis-chart"
