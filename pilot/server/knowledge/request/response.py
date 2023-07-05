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


class SpaceQueryResponse(BaseModel):
    """data: data"""

    name: str = None
    """vector_type: vector type"""
    vector_type: str = None
    """desc: description"""
    desc: str = None
    """owner: owner"""
    owner: str = None
    """doc_count: doc_count"""
    doc_count: int = None
