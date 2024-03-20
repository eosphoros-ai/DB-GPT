from typing import List, Optional

from fastapi import UploadFile

from dbgpt._private.pydantic import BaseModel
from dbgpt.rag.chunk_manager import ChunkParameters


class KnowledgeQueryRequest(BaseModel):
    """query: knowledge query"""

    query: str
    """top_k: return topK documents"""
    top_k: int


class KnowledgeSpaceRequest(BaseModel):
    """name: knowledge space name"""

    """vector_type: vector type"""
    id: int = None
    name: str = None
    """vector_type: vector type"""
    vector_type: str = None
    """desc: description"""
    desc: str = None
    """owner: owner"""
    owner: str = None


class KnowledgeDocumentRequest(BaseModel):
    """doc_name: doc path"""

    doc_name: str = None
    """doc_type: doc type"""
    doc_type: str = None
    """content: content"""
    content: str = None
    """content: content"""
    source: str = None


class DocumentQueryRequest(BaseModel):
    """doc_name: doc path"""

    doc_name: str = None
    """doc_ids: doc ids"""
    doc_ids: Optional[List] = None
    """doc_type: doc type"""
    doc_type: str = None
    """status: status"""
    status: str = None
    """page: page"""
    page: int = 1
    """page_size: page size"""
    page_size: int = 20


class DocumentSyncRequest(BaseModel):
    """Sync request"""

    """doc_ids: doc ids"""
    doc_ids: List

    model_name: Optional[str] = None

    """Preseparator, this separator is used for pre-splitting before the document is actually split by the text splitter.
    Preseparator are not included in the vectorized text. 
    """
    pre_separator: Optional[str] = None

    """Custom separators"""
    separators: Optional[List[str]] = None

    """Custom chunk size"""
    chunk_size: Optional[int] = None

    """Custom chunk overlap"""
    chunk_overlap: Optional[int] = None


class ChunkQueryRequest(BaseModel):
    """id: id"""

    id: int = None
    """document_id: doc id"""
    document_id: int = None
    """doc_name: doc path"""
    doc_name: str = None
    """doc_type: doc type"""
    doc_type: str = None
    """page: page"""
    page: int = 1
    """page_size: page size"""
    page_size: int = 20


class SpaceArgumentRequest(BaseModel):
    """argument: argument"""

    argument: str


class DocumentSummaryRequest(BaseModel):
    """Sync request"""

    """doc_ids: doc ids"""
    doc_id: int
    model_name: str
    conv_uid: str


class EntityExtractRequest(BaseModel):
    """argument: argument"""

    text: str
    model_name: str
