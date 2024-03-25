"""API schema module."""

import time
import uuid
from typing import Any, Generic, List, Literal, Optional, TypeVar

from dbgpt._private.pydantic import BaseModel, Field

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
