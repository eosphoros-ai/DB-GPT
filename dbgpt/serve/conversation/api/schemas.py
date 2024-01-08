# Define your Pydantic schemas here
from dbgpt._private.pydantic import BaseModel, Field

from ..config import SERVE_APP_NAME_HUMP


class ServeRequest(BaseModel):
    """Conversation request model"""

    # TODO define your own fields here

    class Config:
        title = f"ServeRequest for {SERVE_APP_NAME_HUMP}"


class ServerResponse(BaseModel):
    """Conversation response model"""

    # TODO define your own fields here
    class Config:
        title = f"ServerResponse for {SERVE_APP_NAME_HUMP}"
