# Define your Pydantic schemas here
from dbgpt._private.pydantic import BaseModel, Field
from dbgpt.core.awel.flow.flow_factory import FlowPanel

from ..config import SERVE_APP_NAME_HUMP

ServeRequest = FlowPanel


class ServerResponse(BaseModel):
    """Flow response model"""

    # TODO define your own fields here
    class Config:
        title = f"ServerResponse for {SERVE_APP_NAME_HUMP}"
