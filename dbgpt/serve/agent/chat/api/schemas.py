# Define your Pydantic schemas here
from dbgpt._private.pydantic import BaseModel, ConfigDict, Field

from ..config import SERVE_APP_NAME_HUMP


class ServeRequest(BaseModel):
    """Agent/chat request model"""

    model_config = ConfigDict(title=f"ServeRequest for {SERVE_APP_NAME_HUMP}")

    # TODO define your own fields here


class ServerResponse(BaseModel):
    """Agent/chat response model"""

    model_config = ConfigDict(title=f"ServerResponse for {SERVE_APP_NAME_HUMP}")

    # TODO define your own fields here
