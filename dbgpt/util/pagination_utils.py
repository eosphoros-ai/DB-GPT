from typing import TypeVar, Generic, List
from dbgpt._private.pydantic import BaseModel, Field

T = TypeVar("T")


class PaginationResult(BaseModel, Generic[T]):
    """Pagination result"""

    items: List[T] = Field(..., description="The items in the current page")
    total_count: int = Field(..., description="Total number of items")
    total_pages: int = Field(..., description="total number of pages")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Number of items per page")
