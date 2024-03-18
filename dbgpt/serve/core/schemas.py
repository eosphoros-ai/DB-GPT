import logging
import sys
from typing import TYPE_CHECKING, Any, Generic, Optional, TypeVar

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from dbgpt._private.pydantic import BaseModel, Field

if sys.version_info < (3, 11):
    try:
        from exceptiongroup import ExceptionGroup
    except ImportError:
        ExceptionGroup = None

if TYPE_CHECKING:
    from fastapi import FastAPI

logger = logging.getLogger(__name__)
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


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Validation exception handler"""
    message = ""
    for error in exc.errors():
        loc = ".".join(list(map(str, error.get("loc"))))
        message += loc + ":" + error.get("msg") + ";"
    res = Result.failed(msg=message, err_code="E0001")
    logger.error(f"validation_exception_handler catch RequestValidationError: {res}")
    return JSONResponse(status_code=400, content=res.dict())


async def http_exception_handler(request: Request, exc: HTTPException):
    res = Result.failed(
        msg=str(exc.detail),
        err_code=str(exc.status_code),
    )
    logger.error(f"http_exception_handler catch HTTPException: {res}")
    return JSONResponse(status_code=exc.status_code, content=res.dict())


async def common_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Common exception handler"""

    if ExceptionGroup and isinstance(exc, ExceptionGroup):
        err_strs = []
        for e in exc.exceptions:
            err_strs.append(str(e))
        err_msg = ";".join(err_strs)
    else:
        err_msg = str(exc)
    res = Result.failed(
        msg=err_msg,
        err_code="E0003",
    )
    logger.error(f"common_exception_handler catch Exception: {res}")
    return JSONResponse(status_code=400, content=res.dict())


def add_exception_handler(app: "FastAPI"):
    """Add exception handler"""
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(Exception, common_exception_handler)
