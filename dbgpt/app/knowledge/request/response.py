from typing import List

from dbgpt._private.pydantic import BaseModel


class ChunkQueryResponse(BaseModel):
    """data: data"""

    data: List = None
    """summary: document summary"""
    summary: str = None
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

    id: int = None
    name: str = None
    """vector_type: vector type"""
    vector_type: str = None
    """desc: description"""
    desc: str = None
    """context: context"""
    context: str = None
    """owner: owner"""
    owner: str = None
    gmt_created: str = None
    gmt_modified: str = None
    """doc_count: doc_count"""
    docs: int = None
