from dataclasses import dataclass
from typing import Any, Dict, Generic, List, Optional, TypedDict, TypeVar

from dbgpt._private.pydantic import BaseModel, Field

T = TypeVar("T")


class PagenationFilter(BaseModel, Generic[T]):
    page_index: int = 1
    page_size: int = 20
    filter: T = None


class PagenationResult(BaseModel, Generic[T]):
    page_index: int = 1
    page_size: int = 20
    total_page: int = 0
    total_row_count: int = 0
    datas: List[T] = []

    def to_dic(self):
        data_dicts = []
        for item in self.datas:
            data_dicts.append(item.__dict__)
        return {
            "page_index": self.page_index,
            "page_size": self.page_size,
            "total_page": self.total_page,
            "total_row_count": self.total_row_count,
            "datas": data_dicts,
        }


class AwelTeamContext(BaseModel):
    dag_id: str = Field(
        ...,
        description="The unique id of dag",
        examples=["flow_dag_testflow_66d8e9d6-f32e-4540-a5bd-ea0648145d0e"],
    )
    uid: str = Field(
        default=None,
        description="The unique id of flow",
        examples=["66d8e9d6-f32e-4540-a5bd-ea0648145d0e"],
    )
    name: Optional[str] = Field(
        default=None,
        description="The name of dag",
    )
    label: Optional[str] = Field(
        default=None,
        description="The label of dag",
    )
    version: Optional[str] = Field(
        default=None,
        description="The version of dag",
    )
    description: Optional[str] = Field(
        default=None,
        description="The description of dag",
    )
    editable: bool = Field(
        default=False,
        description="is the dag is editable",
        examples=[True, False],
    )
    state: Optional[str] = Field(
        default=None,
        description="The state of dag",
    )
    user_name: Optional[str] = Field(
        default=None,
        description="The owner of current dag",
    )
    sys_code: Optional[str] = Field(
        default=None,
        description="The system code of current dag",
    )
    flow_category: Optional[str] = Field(
        default="common",
        description="The flow category of current dag",
    )

    def to_dict(self):
        return self.dict()


@dataclass
class PluginHubFilter(BaseModel):
    name: str
    description: str
    author: str
    email: str
    type: str
    version: str
    storage_channel: str
    storage_url: str


@dataclass
class MyPluginFilter(BaseModel):
    tenant: str
    user_code: str
    user_name: str
    name: str
    file_name: str
    type: str
    version: str


class PluginHubParam(BaseModel):
    channel: Optional[str] = Field("git", description="Plugin storage channel")
    url: Optional[str] = Field(
        "https://github.com/eosphoros-ai/DB-GPT-Plugins.git",
        description="Plugin storage url",
    )
    branch: Optional[str] = Field(
        "main", description="github download branch", nullable=True
    )
    authorization: Optional[str] = Field(
        None, description="github download authorization", nullable=True
    )
