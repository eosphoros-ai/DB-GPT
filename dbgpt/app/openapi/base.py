from fastapi import Request
from fastapi.exceptions import RequestValidationError
from dbgpt.app.openapi.api_view_model import Result


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    message = ""
    for error in exc.errors():
        message += ".".join(error.get("loc")) + ":" + error.get("msg") + ";"
    return Result.failed(code="E0001", msg=message)
