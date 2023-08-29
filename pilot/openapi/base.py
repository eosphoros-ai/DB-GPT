from fastapi import (
    APIRouter,
    Request,
    Body,
    status,
    HTTPException,
    Response,
    BackgroundTasks,
)

from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError

from pilot.openapi.api_view_model import (
    Result,
    ConversationVo,
    MessageVo,
    ChatSceneVo,
)


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    message = ""
    for error in exc.errors():
        message += ".".join(error.get("loc")) + ":" + error.get("msg") + ";"
    return Result.faild(code="E0001", msg=message)
