# Define your Pydantic schemas here
from dbgpt._private.pydantic import BaseModel, Field


class ServeRequest(BaseModel):
    """{__template_app_name__hump__} request model"""

    # TODO define your own fields here


class ServerResponse(BaseModel):
    """{__template_app_name__hump__} response model"""

    # TODO define your own fields here
