from pydantic import BaseModel, Field
from typing import TypeVar, Union, List, Generic, Any


class DbField(BaseModel):
    colunm_name: str
    type: str
    colunm_len: str
    can_null: bool = True
    default_value: str = ""
    comment: str = ""

class DbTable(BaseModel):
    table_name: str
    comment: str
    colunm: List[DbField]

class ChatDbRounds(BaseModel):
    round: int
    db_name: str
    round_name: str


class ChartDetail(BaseModel):
    chart_uid: str
    chart_type: str
    chart_desc: str
    chart_sql: str
    db_name: str
    chart_name: str
    chart_value: Any
    table_value: Any


class ChatChartEditContext(BaseModel):
    conv_uid: str
    conv_round: int
    chart_uid: str

    old_sql: str
    new_sql: str
    comment: str
    gmt_create: int

    new_view_info: str


class ChatSqlEditContext(BaseModel):
    conv_uid: str
    conv_round: int

    old_sql: str
    new_sql: str
    comment: str
    gmt_create: int

    new_view_info: str
