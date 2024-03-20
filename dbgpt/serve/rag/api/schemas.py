from typing import Optional

from fastapi import File, UploadFile
from pydantic import BaseModel, Field

from dbgpt.rag.chunk_manager import ChunkParameters

from ..config import SERVE_APP_NAME_HUMP


class SpaceServeRequest(BaseModel):
    """name: knowledge space name"""

    """vector_type: vector type"""
    id: Optional[int] = Field(None, description="The space id")
    name: str = Field(None, description="The space name")
    """vector_type: vector type"""
    vector_type: str = Field("Chroma", description="The vector type")
    """desc: description"""
    desc: Optional[str] = Field(None, description="The description")
    """owner: owner"""
    owner: Optional[str] = Field(None, description="The owner")
    """context: argument context"""
    context: Optional[str] = Field(None, description="The context")
    """gmt_created: created time"""
    gmt_created: Optional[str] = Field(None, description="The created time")
    """gmt_modified: modified time"""
    gmt_modified: Optional[str] = Field(None, description="The modified time")


class DocumentServeRequest(BaseModel):
    id: int = Field(None, description="The doc id")
    doc_name: str = Field(None, description="doc name")
    """doc_type: document type"""
    doc_type: str = Field(None, description="The doc type")
    """content: description"""
    content: str = Field(None, description="content")
    """doc file"""
    doc_file: UploadFile = File(...)
    """doc_source: doc source"""
    doc_source: str = None
    """doc_source: doc source"""
    space_id: str = None


class DocumentServeResponse(BaseModel):
    id: int = Field(None, description="The doc id")
    doc_name: str = Field(None, description="doc type")
    """vector_type: vector type"""
    doc_type: str = Field(None, description="The doc content")
    """desc: description"""
    content: str = Field(None, description="content")
    """vector ids"""
    vector_ids: str = Field(None, description="vector ids")
    """doc_source: doc source"""
    doc_source: str = None
    """doc_source: doc source"""
    space: str = None


class KnowledgeSyncRequest(BaseModel):
    """Sync request"""

    """doc_ids: doc ids"""
    doc_id: int = Field(None, description="The doc id")

    """space id"""
    space_id: str = Field(None, description="space id")

    """model_name: model name"""
    model_name: Optional[str] = Field(None, description="model name")

    """chunk_parameters: chunk parameters 
    """
    chunk_parameters: ChunkParameters = Field(None, description="chunk parameters")


class SpaceServeResponse(BaseModel):
    """Flow response model"""

    """name: knowledge space name"""

    """vector_type: vector type"""
    id: int = Field(None, description="The space id")
    name: str = Field(None, description="The space name")
    """vector_type: vector type"""
    vector_type: str = Field(None, description="The vector type")
    """desc: description"""
    desc: str = Field(None, description="The description")
    """context: argument context"""
    context: str = Field(None, description="The context")
    """owner: owner"""
    owner: str = Field(None, description="The owner")
    """sys code"""
    sys_code: str = Field(None, description="The sys code")

    # TODO define your own fields here
    class Config:
        title = f"ServerResponse for {SERVE_APP_NAME_HUMP}"
