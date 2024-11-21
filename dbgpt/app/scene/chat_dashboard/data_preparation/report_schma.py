from typing import Any, List, Optional

from dbgpt._private.pydantic import BaseModel


class ValueItem(BaseModel):
    name: str
    type: Optional[str] = None
    value: float

    def dict(self, *args, **kwargs):
        return {"name": self.name, "type": self.type, "value": self.value}


class ChartData(BaseModel):
    chart_uid: str
    chart_name: str
    chart_type: str
    chart_desc: str
    chart_sql: str
    column_name: List
    values: List[ValueItem]
    style: Any = None

    def dict(self, *args, **kwargs):
        return {
            "chart_uid": self.chart_uid,
            "chart_name": self.chart_name,
            "chart_type": self.chart_type,
            "chart_desc": self.chart_desc,
            "chart_sql": self.chart_sql,
            "column_name": [str(item) for item in self.column_name],
            "values": [value.dict() for value in self.values],
            "style": self.style,
        }


class ReportData(BaseModel):
    conv_uid: str
    template_name: str
    template_introduce: Optional[str] = None
    charts: List[ChartData]

    def prepare_dict(self):
        return {
            "conv_uid": self.conv_uid,
            "template_name": self.template_name,
            "template_introduce": self.template_introduce,
            "charts": [chart.dict() for chart in self.charts],
        }
