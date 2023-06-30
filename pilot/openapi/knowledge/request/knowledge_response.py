from typing import List

from pydantic import BaseModel


class ChunkQueryResponse(BaseModel):
    """data: data"""

    data: List = None
    """total: total size"""
    total: int = None
    """page: current page"""
    page: int = None


class DocumentQueryResponse(BaseModel):
    """data: data"""

    data: List = None
    """total: total size"""
    total: int = None
    """page: current page"""
    page: int = None
