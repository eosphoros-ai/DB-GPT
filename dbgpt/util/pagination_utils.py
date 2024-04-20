from typing import Generic, List, TypeVar

from dbgpt._private.pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class PaginationResult(BaseModel, Generic[T]):
    """Pagination result"""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    items: List[T] = Field(..., description="The items in the current page")
    total_count: int = Field(..., description="Total number of items")
    total_pages: int = Field(..., description="total number of pages")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Number of items per page")
