from dbgpt._private.pydantic import BaseModel, Field
from typing import List, Any


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


class ChartList(BaseModel):
    round: int
    db_name: str
    charts: List


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
    chart_title: str
    db_name: str
    old_sql: str

    new_chart_type: str
    new_sql: str
    new_comment: str
    gmt_create: int


class ChatSqlEditContext(BaseModel):
    conv_uid: str
    db_name: str
    conv_round: int

    old_sql: str
    old_speak: str
    gmt_create: int = 0

    new_sql: str
    new_speak: str = ""
