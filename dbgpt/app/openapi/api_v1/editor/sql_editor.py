from typing import Any, List, Optional

from dbgpt._private.pydantic import BaseModel
from dbgpt.app.scene.chat_dashboard.data_preparation.report_schma import ValueItem


class DataNode(BaseModel):
    title: str
    key: str

    type: str = ""
    default_value: Optional[Any] = None
    can_null: str = "YES"
    comment: Optional[str] = None
    children: List = []


class SqlRunData(BaseModel):
    result_info: str
    run_cost: int
    colunms: List[str]
    values: List


class ChartRunData(BaseModel):
    sql_data: SqlRunData
    chart_values: List[ValueItem]
    chart_type: str
