from pydantic import BaseModel, Field
from typing import TypeVar, Union, List, Generic, Any


class ChatDbRounds(BaseModel):
    round: int
    db_name: str
    round_name: str


class ChartDetail(BaseModel):
    chart_uid: str
    chart_type: str
    db_name: str
    chart_name: str
    chart_value: str
    chat_round: int  # defualt last round


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
