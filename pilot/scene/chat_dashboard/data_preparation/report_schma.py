from pydantic import BaseModel, Field
from typing import TypeVar, Union, List, Generic, Any


class ChartData(BaseModel):
    chart_uid: str
    chart_type: str
    chart_sql: str
    column_name: List
    values: List
    style: Any


class ReportData(BaseModel):
    conv_uid:str
    template_name:str
    template_introduce:str
    charts: List[ChartData]




