from dataclasses import dataclass
from typing import Generic, List, Optional, TypeVar

from dbgpt._private.pydantic import BaseModel, ConfigDict, Field


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


class PluginHubVO(BaseModel):
    id: int = Field(..., description="Plugin id")
    name: str = Field(..., description="Plugin name")
    description: str = Field(..., description="Plugin description")
    author: Optional[str] = Field(None, description="Plugin author")
    email: Optional[str] = Field(None, description="Plugin email")
    type: Optional[str] = Field(None, description="Plugin type")
    version: Optional[str] = Field(None, description="Plugin version")
    storage_channel: Optional[str] = Field(None, description="Plugin storage channel")
    storage_url: Optional[str] = Field(None, description="Plugin storage url")
    download_param: Optional[str] = Field(None, description="Plugin download param")
    installed: Optional[int] = Field(None, description="Plugin installed")
    gmt_created: Optional[str] = Field(None, description="Plugin upload time")


class MyPluginVO(BaseModel):
    id: int = Field(..., description="My Plugin")
    tenant: Optional[str] = Field(None, description="My Plugin tenant")
    user_code: Optional[str] = Field(None, description="My Plugin user code")
    user_name: Optional[str] = Field(None, description="My Plugin user name")
    sys_code: Optional[str] = Field(None, description="My Plugin sys code")
    name: str = Field(..., description="My Plugin name")
    file_name: str = Field(..., description="My Plugin file name")
    type: Optional[str] = Field(None, description="My Plugin type")
    version: Optional[str] = Field(None, description="My Plugin version")
    use_count: Optional[int] = Field(None, description="My Plugin use count")
    succ_count: Optional[int] = Field(None, description="My Plugin succ count")
    gmt_created: Optional[str] = Field(None, description="My Plugin install time")
