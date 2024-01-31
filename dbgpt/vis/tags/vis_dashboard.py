import json
from typing import Optional

from ..base import Vis


class VisDashboard(Vis):
    async def generate_content(self, **kwargs) -> Optional[str]:
        charts = kwargs.get("charts", None)
        title = kwargs.get("title", None)
        if not charts:
            raise ValueError(
                f"Parameter information is missing and {self.vis_tag} protocol conversion cannot be performed."
            )

        chart_items = []
        for chart in charts:
            param = {}
            sql = chart.get("sql", "")
            param["sql"] = sql
            param["type"] = chart.get("display_type", "response_table")
            param["title"] = chart.get("title", "")
            param["describe"] = chart.get("thought", "")
            try:
                df = chart.get("data", None)
                err_msg = chart.get("err_msg", None)
                if not df:
                    param["err_msg"] = err_msg
                else:
                    param["data"] = json.loads(
                        df.to_json(orient="records", date_format="iso", date_unit="s")
                    )

            except Exception as e:
                param["data"] = []
                param["err_msg"] = str(e)
            chart_items.append(param)

        dashboard_param = {
            "data": chart_items,
            "chart_count": len(chart_items),
            "title": title,
            "display_strategy": "default",
            "style": "default",
        }

        return dashboard_param

    @classmethod
    def vis_tag(cls):
        return "vis-dashboard"
