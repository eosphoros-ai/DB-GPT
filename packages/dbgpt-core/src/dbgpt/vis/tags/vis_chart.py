"""Chart visualization protocol conversion class."""

import json
from typing import Any, Dict, Optional

from ..base import Vis


def default_chart_type_prompt() -> str:
    """Return prompt information for the default chart type.

    This function is moved from excel_analyze/chat.py,and used by subclass.

    Returns:
        str: prompt information for the default chart type.
    """
    antv_charts = [
        {"response_line_chart": "used to display comparative trend analysis data"},
        {
            "response_pie_chart": "suitable for scenarios such as proportion and "
            "distribution statistics"
        },
        {
            "response_table": "suitable for display with many display columns or "
            "non-numeric columns"
        },
        {
            "response_scatter_chart": "Suitable for exploring relationships between "
            "variables, detecting outliers, etc."
        },
        {
            "response_bubble_chart": "Suitable for relationships between multiple "
            "variables, highlighting outliers or special situations, etc."
        },
        {
            "response_donut_chart": "Suitable for hierarchical structure representation"
            ", category proportion display and highlighting key categories, etc."
        },
        {
            "response_area_chart": "Suitable for visualization of time series data, "
            "comparison of multiple groups of data, analysis of data change trends, "
            "etc."
        },
        {
            "response_heatmap": "Suitable for visual analysis of time series data, "
            "large-scale data sets, distribution of classified data, etc."
        },
    ]
    return "\n".join(
        f"{key}:{value}"
        for dict_item in antv_charts
        for key, value in dict_item.items()
    )


class VisChart(Vis):
    """Chart visualization protocol conversion class."""

    def render_prompt(self) -> Optional[str]:
        """Return the prompt for the vis protocol."""
        return default_chart_type_prompt()

    def sync_generate_param(self, **kwargs) -> Optional[Dict[str, Any]]:
        """Generate the parameters required by the vis protocol."""
        chart = kwargs.get("chart", None)
        data_df = kwargs.get("data_df", None)

        if not chart:
            raise ValueError(
                f"Parameter information is missing and {self.vis_tag} protocol "
                "conversion cannot be performed."
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
    def vis_tag(cls) -> str:
        """Return the tag name of the vis protocol."""
        return "vis-db-chart"
