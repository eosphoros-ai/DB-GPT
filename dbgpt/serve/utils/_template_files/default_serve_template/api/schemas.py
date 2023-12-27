# Define your Pydantic schemas here
from dbgpt._private.pydantic import BaseModel, Field

from ..config import SERVE_APP_NAME_HUMP


class ServeRequest(BaseModel):
    """{__template_app_name__hump__} request model"""

    # TODO define your own fields here

    class Config:
        title = f"ServeRequest for {SERVE_APP_NAME_HUMP}"


class ServerResponse(BaseModel):
    """{__template_app_name__hump__} response model"""

    # TODO define your own fields here
    class Config:
        title = f"ServerResponse for {SERVE_APP_NAME_HUMP}"
