from typing import List, Literal

from dbgpt._private.pydantic import BaseModel, ConfigDict, Field
from dbgpt.core.awel.flow.flow_factory import FlowPanel
from dbgpt.core.awel.util.parameter_util import RefreshOptionRequest

from ..config import SERVE_APP_NAME_HUMP

ServeRequest = FlowPanel


class ServerResponse(FlowPanel):
    """Flow response model"""

    # TODO define your own fields here

    model_config = ConfigDict(title=f"ServerResponse for {SERVE_APP_NAME_HUMP}")


class RefreshNodeRequest(BaseModel):
    """Flow response model"""

    model_config = ConfigDict(title=f"RefreshNodeRequest")
    id: str = Field(
        ...,
        title="The id of the node",
        description="The id of the node to refresh",
        examples=["operator_llm_operator___$$___llm___$$___v1"],
    )
    flow_type: Literal["operator", "resource"] = Field(
        "operator",
        title="The type of the node",
        description="The type of the node to refresh",
        examples=["operator", "resource"],
    )
    type_name: str = Field(
        ...,
        title="The type of the node",
        description="The type of the node to refresh",
        examples=["LLMOperator"],
    )
    type_cls: str = Field(
        ...,
        title="The class of the node",
        description="The class of the node to refresh",
        examples=["dbgpt.core.operator.llm.LLMOperator"],
    )
    refresh: List[RefreshOptionRequest] = Field(
        ...,
        title="The refresh options",
        description="The refresh options",
    )
