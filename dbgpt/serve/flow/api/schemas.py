from dbgpt._private.pydantic import ConfigDict

# Define your Pydantic schemas here
from dbgpt.core.awel.flow.flow_factory import FlowPanel

from ..config import SERVE_APP_NAME_HUMP

ServeRequest = FlowPanel


class ServerResponse(FlowPanel):
    """Flow response model"""

    # TODO define your own fields here

    model_config = ConfigDict(title=f"ServerResponse for {SERVE_APP_NAME_HUMP}")
