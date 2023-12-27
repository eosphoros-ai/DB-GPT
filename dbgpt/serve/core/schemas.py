from typing import Any, Generic, Optional, TypeVar

from dbgpt._private.pydantic import BaseModel, Field

T = TypeVar("T")


class Result(BaseModel, Generic[T]):
    """Common result entity class"""

    success: bool = Field(
        ..., description="Whether it is successful, True: success, False: failure"
    )
    err_code: str | None = Field(None, description="Error code")
    err_msg: str | None = Field(None, description="Error message")
    data: T | None = Field(None, description="Return data")

    @staticmethod
    def succ(data: T) -> "Result[T]":
        """Build a successful result entity

        Args:
            data (T): Return data

        Returns:
            Result[T]: Result entity
        """
        return Result(success=True, err_code=None, err_msg=None, data=data)

    @staticmethod
    def failed(msg: str, err_code: Optional[str] = "E000X") -> "Result[Any]":
        """Build a failed result entity

        Args:
            msg (str): Error message
            err_code (Optional[str], optional): Error code. Defaults to "E000X".
        """
        return Result(success=False, err_code=err_code, err_msg=msg, data=None)
