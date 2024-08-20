from enum import Enum
from typing import List, Optional, Union

from dbgpt._private.pydantic import BaseModel, ConfigDict
from dbgpt.rag import ChunkParameters


class KnowledgeQueryRequest(BaseModel):
    """query: knowledge query"""

    query: str
    """space: space name"""
    space: str
    """top_k: return topK documents"""
    top_k: int


class KnowledgeSpaceRequest(BaseModel):
    """name: knowledge space name"""

    """vector_type: vector type"""
    id: Optional[int] = None
    name: Optional[str] = None
    """vector_type: vector type"""
    vector_type: Optional[str] = None
    """vector_type: vector type"""
    domain_type: str = "Normal"
    """desc: description"""
    desc: str = None
    """owner: owner"""
    owner: Optional[str] = None

    space_id: Optional[Union[int, str]] = None


class BusinessFieldType(Enum):
    """BusinessFieldType"""

    NORMAL = "Normal"


class KnowledgeDocumentRequest(BaseModel):
    """doc_name: doc path"""

    doc_name: Optional[str] = None
    """doc_id: doc id"""
    doc_id: Optional[int] = None
    """doc_type: doc type"""
    doc_type: Optional[str] = None
    """doc_token: doc token"""
    doc_token: Optional[str] = None
    """content: content"""
    content: Optional[str] = None
    """content: content"""
    source: Optional[str] = None

    labels: Optional[str] = None

    questions: Optional[List[str]] = None


class DocumentRecallTestRequest(BaseModel):
    question: Optional[str] = None
    recall_top_k: Optional[int] = 1
    recall_retrievers: Optional[List[str]] = None
    recall_score_threshold: Optional[float] = -100


class DocumentQueryRequest(BaseModel):
    """doc_name: doc path"""

    doc_name: Optional[str] = None
    """doc_ids: doc ids"""
    doc_ids: Optional[List] = None
    """doc_type: doc type"""
    doc_type: Optional[str] = None
    """status: status"""
    status: Optional[str] = None
    """page: page"""
    page: int = 1
    """page_size: page size"""
    page_size: int = 20


class GraphVisRequest(BaseModel):
    limit: int = 100


class DocumentSyncRequest(BaseModel):
    """Sync request"""

    model_config = ConfigDict(protected_namespaces=())

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


class KnowledgeSyncRequest(BaseModel):
    """Sync request"""

    """doc_ids: doc ids"""
    doc_id: int

    """model_name: model name"""
    model_name: Optional[str] = None

    """chunk_parameters: chunk parameters 
    """
    chunk_parameters: ChunkParameters

    def to_dict(self):
        return {k: self._serialize(v) for k, v in self.__dict__.items()}

    def _serialize(self, value):
        if isinstance(value, BaseModel):
            return value.to_dict()
        elif isinstance(value, list):
            return [self._serialize(item) for item in value]
        elif isinstance(value, dict):
            return {k: self._serialize(v) for k, v in value.items()}
        else:
            return value


class ChunkQueryRequest(BaseModel):
    """id: id"""

    id: Optional[int] = None
    """document_id: doc id"""
    document_id: Optional[int] = None
    """doc_name: doc path"""
    doc_name: Optional[str] = None
    """doc_type: doc type"""
    doc_type: Optional[str] = None
    """chunk content: content"""
    content: Optional[str] = None
    """page: page"""
    page: int = 1
    """page_size: page size"""
    page_size: int = 20


class ChunkEditRequest(BaseModel):
    """id: id"""

    """chunk_id: chunk_id"""
    chunk_id: Optional[int] = None
    """chunk content: content"""
    content: Optional[str] = None
    """label: label"""
    label: Optional[str] = None
    """questions: questions"""
    questions: Optional[List[str]] = None


class KnowledgeQueryResponse:
    """source: knowledge reference source"""

    source: Optional[str]
    """score: knowledge vector query similarity score"""
    score: float = 0.0
    """text: raw text info"""
    text: Optional[str]


class SpaceArgumentRequest(BaseModel):
    """argument: argument"""

    argument: str


class DocumentSummaryRequest(BaseModel):
    """Sync request"""

    model_config = ConfigDict(protected_namespaces=())

    """doc_ids: doc ids"""
    doc_id: int
    model_name: str
    conv_uid: str


class DocumentDynamicText(BaseModel):
    space_id: int
    doc_id: int
    text_snippets: List[str]


class EntityExtractRequest(BaseModel):
    """argument: argument"""

    model_config = ConfigDict(protected_namespaces=())

    text: str
    model_name: str


class SpaceEvaluationRequest(BaseModel):
    """RAG Evaluation Reques.t"""

    datasets: List[dict]
    """space: space name"""
    space_id: Optional[int] = None
    """top_k: return topK documents"""
    top_k: int
    """type: evaluation type"""
    type: Optional[str] = "recall"
    """model_name: evaluation model_name"""
    model_name: Optional[str] = None
    """app_id: app_id"""
    app_id: Optional[str] = None
    """evaluate prompt id: prompt_id"""
    prompt_code: Optional[str] = None
