from typing import List, Optional

from dbgpt._private.pydantic import BaseModel
from fastapi import UploadFile


class KnowledgeQueryRequest(BaseModel):
    """query: knowledge query"""

    query: str
    """top_k: return topK documents"""
    top_k: int


class KnowledgeSpaceRequest(BaseModel):
    """name: knowledge space name"""

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

    """text_chunk_size: text_chunk_size"""
    # text_chunk_size: int


class DocumentQueryRequest(BaseModel):
    """doc_name: doc path"""

    doc_name: str = None
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


class KnowledgeQueryResponse:
    """source: knowledge reference source"""

    source: str
    """score: knowledge vector query similarity score"""
    score: float = 0.0
    """text: raw text info"""
    text: str


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
