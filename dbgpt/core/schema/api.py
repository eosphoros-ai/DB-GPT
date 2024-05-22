"""API schema module."""

import time
import uuid
from enum import IntEnum
from typing import Any, Dict, Generic, List, Literal, Optional, TypeVar, Union

from dbgpt._private.pydantic import BaseModel, Field, model_to_dict

T = TypeVar("T")


class Result(BaseModel, Generic[T]):
    """Common result entity for API response."""

    success: bool = Field(
        ..., description="Whether it is successful, True: success, False: failure"
    )
    err_code: str | None = Field(None, description="Error code")
    err_msg: str | None = Field(None, description="Error message")
    data: T | None = Field(None, description="Return data")

    @staticmethod
    def succ(data: T) -> "Result[T]":
        """Build a successful result entity.

        Args:
            data (T): Return data

        Returns:
            Result[T]: Result entity
        """
        return Result(success=True, err_code=None, err_msg=None, data=data)

    @staticmethod
    def failed(msg: str, err_code: Optional[str] = "E000X") -> "Result[Any]":
        """Build a failed result entity.

        Args:
            msg (str): Error message
            err_code (Optional[str], optional): Error code. Defaults to "E000X".
        """
        return Result(success=False, err_code=err_code, err_msg=msg, data=None)

    def to_dict(self, **kwargs) -> Dict[str, Any]:
        """Convert to dict."""
        return model_to_dict(self, **kwargs)


class APIChatCompletionRequest(BaseModel):
    """Chat completion request entity."""

    model: str = Field(..., description="Model name")
    messages: Union[str, List[Dict[str, str]]] = Field(..., description="Messages")
    temperature: Optional[float] = Field(0.7, description="Temperature")
    top_p: Optional[float] = Field(1.0, description="Top p")
    top_k: Optional[int] = Field(-1, description="Top k")
    n: Optional[int] = Field(1, description="Number of completions")
    max_tokens: Optional[int] = Field(None, description="Max tokens")
    stop: Optional[Union[str, List[str]]] = Field(None, description="Stop")
    stream: Optional[bool] = Field(False, description="Stream")
    user: Optional[str] = Field(None, description="User")
    repetition_penalty: Optional[float] = Field(1.0, description="Repetition penalty")
    frequency_penalty: Optional[float] = Field(0.0, description="Frequency penalty")
    presence_penalty: Optional[float] = Field(0.0, description="Presence penalty")


class DeltaMessage(BaseModel):
    """Delta message entity for chat completion response."""

    role: Optional[str] = None
    content: Optional[str] = None


class ChatCompletionResponseStreamChoice(BaseModel):
    """Chat completion response choice entity."""

    index: int = Field(..., description="Choice index")
    delta: DeltaMessage = Field(..., description="Delta message")
    finish_reason: Optional[Literal["stop", "length"]] = Field(
        None, description="Finish reason"
    )


class ChatCompletionStreamResponse(BaseModel):
    """Chat completion response stream entity."""

    id: str = Field(
        default_factory=lambda: f"chatcmpl-{str(uuid.uuid1())}", description="Stream ID"
    )
    created: int = Field(
        default_factory=lambda: int(time.time()), description="Created time"
    )
    model: str = Field(..., description="Model name")
    choices: List[ChatCompletionResponseStreamChoice] = Field(
        ..., description="Chat completion response choices"
    )


class ChatMessage(BaseModel):
    """Chat message entity."""

    role: str = Field(..., description="Role of the message")
    content: str = Field(..., description="Content of the message")


class UsageInfo(BaseModel):
    """Usage info entity."""

    prompt_tokens: int = Field(0, description="Prompt tokens")
    total_tokens: int = Field(0, description="Total tokens")
    completion_tokens: Optional[int] = Field(0, description="Completion tokens")


class ChatCompletionResponseChoice(BaseModel):
    """Chat completion response choice entity."""

    index: int = Field(..., description="Choice index")
    message: ChatMessage = Field(..., description="Chat message")
    finish_reason: Optional[Literal["stop", "length"]] = Field(
        None, description="Finish reason"
    )


class ChatCompletionResponse(BaseModel):
    """Chat completion response entity."""

    id: str = Field(
        default_factory=lambda: f"chatcmpl-{str(uuid.uuid1())}", description="Stream ID"
    )
    object: str = "chat.completion"
    created: int = Field(
        default_factory=lambda: int(time.time()), description="Created time"
    )
    model: str = Field(..., description="Model name")
    choices: List[ChatCompletionResponseChoice] = Field(
        ..., description="Chat completion response choices"
    )
    usage: UsageInfo = Field(..., description="Usage info")


class ErrorResponse(BaseModel):
    """Error response entity."""

    object: str = Field("error", description="Object type")
    message: str = Field(..., description="Error message")
    code: int = Field(..., description="Error code")


class EmbeddingsRequest(BaseModel):
    """Embeddings request entity."""

    model: Optional[str] = Field(None, description="Model name")
    engine: Optional[str] = Field(None, description="Engine name")
    input: Union[str, List[Any]] = Field(..., description="Input data")
    user: Optional[str] = Field(None, description="User name")
    encoding_format: Optional[str] = Field(None, description="Encoding format")


class EmbeddingsResponse(BaseModel):
    """Embeddings response entity."""

    object: str = Field("list", description="Object type")
    data: List[Dict[str, Any]] = Field(..., description="Data list")
    model: str = Field(..., description="Model name")
    usage: UsageInfo = Field(..., description="Usage info")


class RelevanceRequest(BaseModel):
    """Relevance request entity."""

    model: str = Field(..., description="Rerank model name")
    query: str = Field(..., description="Query text")
    documents: List[str] = Field(..., description="Document texts")


class RelevanceResponse(BaseModel):
    """Relevance response entity."""

    object: str = Field("list", description="Object type")
    model: str = Field(..., description="Rerank model name")
    data: List[float] = Field(..., description="Data list, relevance scores")
    usage: UsageInfo = Field(..., description="Usage info")


class ModelPermission(BaseModel):
    """Model permission entity."""

    id: str = Field(
        default_factory=lambda: f"modelperm-{str(uuid.uuid1())}",
        description="Permission ID",
    )
    object: str = Field("model_permission", description="Object type")
    created: int = Field(
        default_factory=lambda: int(time.time()), description="Created time"
    )
    allow_create_engine: bool = Field(False, description="Allow create engine")
    allow_sampling: bool = Field(True, description="Allow sampling")
    allow_logprobs: bool = Field(True, description="Allow logprobs")
    allow_search_indices: bool = Field(True, description="Allow search indices")
    allow_view: bool = Field(True, description="Allow view")
    allow_fine_tuning: bool = Field(False, description="Allow fine tuning")
    organization: str = Field("*", description="Organization")
    group: Optional[str] = Field(None, description="Group")
    is_blocking: bool = Field(False, description="Is blocking")


class ModelCard(BaseModel):
    """Model card entity."""

    id: str = Field(..., description="Model ID")
    object: str = Field("model", description="Object type")
    created: int = Field(
        default_factory=lambda: int(time.time()), description="Created time"
    )
    owned_by: str = Field("DB-GPT", description="Owned by")
    root: Optional[str] = Field(None, description="Root")
    parent: Optional[str] = Field(None, description="Parent")
    permission: List[ModelPermission] = Field(
        default_factory=list, description="Permission"
    )


class ModelList(BaseModel):
    """Model list entity."""

    object: str = Field("list", description="Object type")
    data: List[ModelCard] = Field(default_factory=list, description="Model list data")


class ErrorCode(IntEnum):
    """Error code enumeration.

    https://platform.openai.com/docs/guides/error-codes/api-errors.

    Adapted from fastchat.constants.
    """

    VALIDATION_TYPE_ERROR = 40001

    INVALID_AUTH_KEY = 40101
    INCORRECT_AUTH_KEY = 40102
    NO_PERMISSION = 40103

    INVALID_MODEL = 40301
    PARAM_OUT_OF_RANGE = 40302
    CONTEXT_OVERFLOW = 40303

    RATE_LIMIT = 42901
    QUOTA_EXCEEDED = 42902
    ENGINE_OVERLOADED = 42903

    INTERNAL_ERROR = 50001
    CUDA_OUT_OF_MEMORY = 50002
    GRADIO_REQUEST_ERROR = 50003
    GRADIO_STREAM_UNKNOWN_ERROR = 50004
    CONTROLLER_NO_WORKER = 50005
    CONTROLLER_WORKER_TIMEOUT = 50006
