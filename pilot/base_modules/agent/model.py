from typing import TypedDict, Optional, Dict, List
from dataclasses import dataclass
from pydantic import BaseModel, Field
from typing import TypeVar, Generic, Any

T = TypeVar('T')

class PagenationFilter(Generic[T]):
    page_index: int = 1
    page_size: int  = 20
    filter: T = None

class PagenationResult(Generic[T]):
    page_index: int = 1
    page_size: int  = 20
    total_page: int = 0
    total_row_count: int = 0
    datas: List[T] = []



@dataclass
class PluginHubParam:
    channel: str  = Field(..., description="Plugin storage channel")
    url: str  = Field(..., description="Plugin storage url")

    branch: str  = Field(..., description="When the storage channel is github, use to specify the branch", nullable=True)
    authorization: str  = Field(..., description="github download authorization", nullable=True)


