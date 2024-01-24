from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from dbgpt.app.openapi.api_view_model import Result


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    message = ""
    for error in exc.errors():
        loc = ".".join(list(map(str, error.get("loc"))))
        message += loc + ":" + error.get("msg") + ";"
    res = Result.failed(code="E0001", msg=message)
    return JSONResponse(status_code=400, content=res.dict())
