import logging
import sys
from typing import TYPE_CHECKING

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from dbgpt.core.schema.api import Result

if sys.version_info < (3, 11):
    try:
        from exceptiongroup import ExceptionGroup
    except ImportError:
        ExceptionGroup = None

if TYPE_CHECKING:
    from fastapi import FastAPI

logger = logging.getLogger(__name__)


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
