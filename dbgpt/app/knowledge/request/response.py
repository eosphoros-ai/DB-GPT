from typing import List, Optional

from dbgpt._private.pydantic import BaseModel, Field
from dbgpt.serve.rag.api.schemas import DocumentChunkVO, DocumentVO


class ChunkQueryResponse(BaseModel):
    """data: data"""

    data: List[DocumentChunkVO] = Field(..., description="document chunk list")
    """summary: document summary"""
    summary: Optional[str] = Field(None, description="document summary")
    """total: total size"""
    total: Optional[int] = Field(None, description="total size")
    """page: current page"""
    page: Optional[int] = Field(None, description="current page")


class DocumentQueryResponse(BaseModel):
    """data: data"""

    data: List[DocumentVO] = Field(..., description="document list")
    """total: total size"""
    total: Optional[int] = Field(None, description="total size")
    """page: current page"""
    page: Optional[int] = Field(None, description="current page")


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


class KnowledgeQueryResponse(BaseModel):
    """source: knowledge reference source"""

    source: str
    """score: knowledge vector query similarity score"""
    score: float = 0.0
    """text: raw text info"""
    text: str
