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

    @classmethod
    def build_from_all(
        cls, all_items: List[T], page: int, page_size: int
    ) -> "PaginationResult[T]":
        """Build a pagination result from all items"""
        if page < 1:
            page = 1
        if page_size < 1:
            page_size = 1
        total_count = len(all_items)
        total_pages = (
            (total_count + page_size - 1) // page_size if total_count > 0 else 0
        )
        page = max(1, min(page, total_pages)) if total_pages > 0 else 0
        start_index = (page - 1) * page_size if page > 0 else 0
        end_index = min(start_index + page_size, total_count)
        items = all_items[start_index:end_index]

        return cls(
            items=items,
            total_count=total_count,
            total_pages=total_pages,
            page=page,
            page_size=page_size,
        )
