from typing import List, Optional, Union

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
    doc_file: Union[UploadFile, str] = File(None)
    """space id: space id"""
    space_id: Optional[str] = Field(None, description="space id")
    """space name: space name"""
    space_name: Optional[str] = Field(None, description="space name")
    """questions: questions"""
    questions: Optional[List[str]] = Field(None, description="questions")


class DocumentServeResponse(BaseModel):
    id: Optional[int] = Field(None, description="The doc id")
    doc_name: Optional[str] = Field(None, description="doc type")
    """vector_type: vector type"""
    doc_type: Optional[str] = Field(None, description="The doc content")
    """desc: description"""
    content: Optional[str] = Field(None, description="content")
    """vector ids"""
    vector_ids: Optional[str] = Field(None, description="vector ids")
    """space: space name"""
    space: Optional[str] = Field(None, description="space name")
    """status: status"""
    status: Optional[str] = Field(None, description="status")
    """last_sync: last sync time"""
    last_sync: Optional[str] = Field(None, description="last sync time")
    """result: result"""
    result: Optional[str] = Field(None, description="result")
    """summary: summary"""
    summary: Optional[str] = Field(None, description="summary")
    """gmt_created: created time"""
    gmt_created: Optional[str] = Field(None, description="created time")
    """gmt_modified: modified time"""
    gmt_modified: Optional[str] = Field(None, description="modified time")
    """chunk_size: chunk size"""
    chunk_size: Optional[int] = Field(None, description="chunk size")
    """questions: questions"""
    questions: Optional[str] = Field(None, description="questions")


class ChunkServeRequest(BaseModel):
    id: Optional[int] = Field(None, description="The primary id")
    document_id: Optional[int] = Field(None, description="document id")
    doc_name: Optional[str] = Field(None, description="document name")
    doc_type: Optional[str] = Field(None, description="document type")
    content: Optional[str] = Field(None, description="chunk content")
    meta_info: Optional[str] = Field(None, description="chunk meta info")
    questions: Optional[List[str]] = Field(None, description="chunk questions")
    gmt_created: Optional[str] = Field(None, description="chunk create time")
    gmt_modified: Optional[str] = Field(None, description="chunk modify time")


class ChunkServeResponse(BaseModel):
    id: Optional[int] = Field(None, description="The primary id")
    document_id: Optional[int] = Field(None, description="document id")
    doc_name: Optional[str] = Field(None, description="document name")
    doc_type: Optional[str] = Field(None, description="document type")
    content: Optional[str] = Field(None, description="chunk content")
    meta_info: Optional[str] = Field(None, description="chunk meta info")
    questions: Optional[str] = Field(None, description="chunk questions")


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


class KnowledgeRetrieveRequest(BaseModel):
    """Retrieve request"""

    """space id"""
    space_id: int = Field(None, description="space id")

    """query: query"""
    query: str = Field(None, description="query")

    """top_k: top k"""
    top_k: Optional[int] = Field(5, description="top k")

    """score_threshold: score threshold
    """
    score_threshold: Optional[float] = Field(0.0, description="score threshold")


# 复用这里代码


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
    """user_id: user_id"""
    user_id: Optional[str] = Field(None, description="user id")
    """user_id: user_ids"""
    user_ids: Optional[str] = Field(None, description="user ids")
    """sys code"""
    sys_code: Optional[str] = Field(None, description="The sys code")
    """domain type"""
    domain_type: Optional[str] = Field(None, description="domain_type")


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
