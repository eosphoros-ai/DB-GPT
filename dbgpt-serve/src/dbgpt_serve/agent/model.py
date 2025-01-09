from dataclasses import dataclass
from typing import Any, Dict, Generic, List, Optional, TypedDict, TypeVar

from pydantic import field_validator, validator

from dbgpt._private.pydantic import BaseModel, ConfigDict, Field, model_to_dict

T = TypeVar("T")


class PagenationFilter(BaseModel, Generic[T]):
    page_index: int = 1
    page_size: int = 20
    filter: T = None


class PagenationResult(BaseModel, Generic[T]):
    model_config = ConfigDict(arbitrary_types_allowed=True)
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


class NativeTeamContext(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    chat_scene: Optional[str] = Field(
        ...,
        description="The chat scene of current app",
        examples=[
            "chat_knowledge",
            "chat_with_db_qa",
            "chat_with_db_execute",
            "chat_dba",
            "chat_dashboard",
            "chat_excel",
        ],
    )
    scene_name: Optional[str] = Field(
        ...,
        description="The name of scene",
        examples=[
            "Chat Knowledge",
            "Chat DB",
            "Chat Data",
            "Professional DBA",
            "Dashboard",
            "Chat Excel",
        ],
    )
    scene_describe: Optional[str] = Field(
        default="",
        description="The describe of scene",
    )
    param_title: Optional[str] = Field(
        default="",
        description="The param title of scene",
    )
    show_disable: Optional[bool] = Field(
        default=False,
        description="The description of dag",
    )

    @field_validator("show_disable", mode="before")
    def parse_show_disable(cls, value):
        if value in (None, ""):
            return False
        return value

    def to_dict(self):
        return model_to_dict(self)


@dataclass
class PluginHubFilter(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    author: Optional[str] = None
    email: Optional[str] = None
    type: Optional[str] = None
    version: Optional[str] = None
    storage_channel: Optional[str] = None
    storage_url: Optional[str] = None


@dataclass
class MyPluginFilter(BaseModel):
    tenant: Optional[str] = None
    user_code: Optional[str] = None
    user_name: Optional[str] = None
    name: Optional[str] = None
    file_name: Optional[str] = None
    type: Optional[str] = None
    version: Optional[str] = None


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
