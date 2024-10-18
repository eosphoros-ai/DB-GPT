from typing import Any, Dict, List, Optional, Union

from dbgpt._private.pydantic import BaseModel
from dbgpt.core.interface.message import ModelMessage
from dbgpt.model.base import WorkerApplyType
from dbgpt.model.parameter import WorkerType

WORKER_MANAGER_SERVICE_TYPE = "service"
WORKER_MANAGER_SERVICE_NAME = "WorkerManager"


class PromptRequest(BaseModel):
    messages: List[ModelMessage]
    model: str
    prompt: str = None
    temperature: float = None
    max_new_tokens: int = None
    stop: Optional[Union[str, List[str]]] = None
    stop_token_ids: List[int] = []
    context_len: int = None
    echo: bool = True
    span_id: str = None
    metrics: bool = False
    """Whether to return metrics of inference"""
    version: str = "v2"
    """Message version, default to v2"""
    context: Dict[str, Any] = None
    """Context information for the model"""


class EmbeddingsRequest(BaseModel):
    model: str
    input: List[str]
    span_id: Optional[str] = None
    query: Optional[str] = None
    """For rerank model, query is required"""


class CountTokenRequest(BaseModel):
    model: str
    prompt: str


class ModelMetadataRequest(BaseModel):
    model: str


class WorkerApplyRequest(BaseModel):
    model: str
    apply_type: WorkerApplyType
    worker_type: WorkerType = WorkerType.LLM
    params: Dict = None
    apply_user: str = None


class WorkerParameterRequest(BaseModel):
    model: str
    worker_type: WorkerType = WorkerType.LLM


class WorkerStartupRequest(BaseModel):
    host: str
    port: int
    model: str
    worker_type: WorkerType
    params: Dict
