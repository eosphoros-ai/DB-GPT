from typing import List, Optional

from fastapi import File, UploadFile

from dbgpt._private.pydantic import BaseModel, ConfigDict, Field
from dbgpt.rag.chunk_manager import ChunkParameters

from ..config import SERVE_APP_NAME_HUMP


class SpaceServeRequest(BaseModel):
    """name: knowledge space name"""

    """vector_type: vector type"""
    id: Optional[int] = Field(None, description="The space id")
    name: str = Field(None, description="The space name")
    """vector_type: vector type"""
    vector_type: str = Field(None, description="The vector type")
    """domain_type: domain type"""
    domain_type: str = Field(None, description="The domain type")
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
    id: Optional[int] = Field(None, description="The doc id")
    doc_name: Optional[str] = Field(None, description="doc name")
    """doc_type: document type"""
    doc_type: Optional[str] = Field(None, description="The doc type")
    """content: description"""
    content: Optional[str] = Field(None, description="content")
    """doc file"""
    doc_file: UploadFile = File(...)
    """doc_source: doc source"""
    doc_source: Optional[str] = Field(None, description="doc source")
    """doc_source: doc source"""
    space_id: Optional[str] = Field(None, description="space id")


class DocumentServeResponse(BaseModel):
    id: Optional[int] = Field(None, description="The doc id")
    doc_name: Optional[str] = Field(None, description="doc type")
    """vector_type: vector type"""
    doc_type: Optional[str] = Field(None, description="The doc content")
    """desc: description"""
    content: Optional[str] = Field(None, description="content")
    """vector ids"""
    vector_ids: Optional[str] = Field(None, description="vector ids")
    """doc_source: doc source"""
    doc_source: Optional[str] = Field(None, description="doc source")
    """doc_source: doc source"""
    space: Optional[str] = Field(None, description="space name")


class KnowledgeSyncRequest(BaseModel):
    """Sync request"""

    """doc_ids: doc ids"""
    doc_id: Optional[int] = Field(None, description="The doc id")

    """space id"""
    space_id: Optional[str] = Field(None, description="space id")

    """model_name: model name"""
    model_name: Optional[str] = Field(None, description="model name")

    """chunk_parameters: chunk parameters 
    """
    chunk_parameters: Optional[ChunkParameters] = Field(
        None, description="chunk parameters"
    )


class SpaceServeResponse(BaseModel):
    """Flow response model"""

    model_config = ConfigDict(title=f"ServeResponse for {SERVE_APP_NAME_HUMP}")

    """name: knowledge space name"""

    """vector_type: vector type"""
    id: Optional[int] = Field(None, description="The space id")
    name: Optional[str] = Field(None, description="The space name")
    """vector_type: vector type"""
    vector_type: Optional[str] = Field(None, description="The vector type")
    """desc: description"""
    desc: Optional[str] = Field(None, description="The description")
    """context: argument context"""
    context: Optional[str] = Field(None, description="The context")
    """owner: owner"""
    owner: Optional[str] = Field(None, description="The owner")
    """sys code"""
    sys_code: Optional[str] = Field(None, description="The sys code")
    """domain type"""
    domain_type: Optional[str] = Field(None, description="domain_type")

    # TODO define your own fields here


class DocumentChunkVO(BaseModel):
    id: int = Field(..., description="document chunk id")
    document_id: int = Field(..., description="document id")
    doc_name: str = Field(..., description="document name")
    doc_type: str = Field(..., description="document type")
    content: str = Field(..., description="document content")
    meta_info: str = Field(..., description="document meta info")
    gmt_created: str = Field(..., description="document create time")
    gmt_modified: str = Field(..., description="document modify time")


class DocumentVO(BaseModel):
    """Document Entity."""

    id: int = Field(..., description="document id")
    doc_name: str = Field(..., description="document name")
    doc_type: str = Field(..., description="document type")
    space: str = Field(..., description="document space name")
    chunk_size: int = Field(..., description="document chunk size")
    status: str = Field(..., description="document status")
    last_sync: str = Field(..., description="document last sync time")
    content: str = Field(..., description="document content")
    result: Optional[str] = Field(None, description="document result")
    vector_ids: Optional[str] = Field(None, description="document vector ids")
    summary: Optional[str] = Field(None, description="document summary")
    gmt_created: str = Field(..., description="document create time")
    gmt_modified: str = Field(..., description="document modify time")


class KnowledgeDomainType(BaseModel):
    """Knowledge domain type"""

    name: str = Field(..., description="The domain type name")
    desc: str = Field(..., description="The domain type description")


class KnowledgeStorageType(BaseModel):
    """Knowledge storage type"""

    name: str = Field(..., description="The storage type name")
    desc: str = Field(..., description="The storage type description")
    domain_types: List[KnowledgeDomainType] = Field(..., description="The domain types")


class KnowledgeConfigResponse(BaseModel):
    """Knowledge config response"""

    storage: List[KnowledgeStorageType] = Field(..., description="The storage types")
