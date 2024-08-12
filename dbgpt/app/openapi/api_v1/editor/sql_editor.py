from typing import List, Optional

from dbgpt._private.pydantic import BaseModel
from dbgpt.app.scene.chat_dashboard.data_preparation.report_schma import ValueItem


class DataNode(BaseModel):
    title: Optional[str]
    key: Optional[str]

    type: Optional[str] = ""
    default_value: Optional[str] = None
    can_null: Optional[str] = "YES"
    comment: Optional[str] = None
    children: Optional[List] = []


class SqlRunData(BaseModel):
    result_info: Optional[str]
    run_cost: float
    colunms: Optional[List[str]] = []
    values: Optional[List] = []


class ChartRunData(BaseModel):
    sql_data: SqlRunData
    chart_values: List[ValueItem]
    chart_type: Optional[str]
