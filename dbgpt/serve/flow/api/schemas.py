from typing import Any, Dict, List, Literal, Optional, Union

from dbgpt._private.pydantic import BaseModel, ConfigDict, Field
from dbgpt.core.awel import CommonLLMHttpRequestBody
from dbgpt.core.awel.flow.flow_factory import (
    FlowPanel,
    VariablesRequest,
    _VariablesRequestBase,
)
from dbgpt.core.awel.util.parameter_util import RefreshOptionRequest

from ..config import SERVE_APP_NAME_HUMP

ServeRequest = FlowPanel


class ServerResponse(FlowPanel):
    """Flow response model"""

    # TODO define your own fields here

    model_config = ConfigDict(title=f"ServerResponse for {SERVE_APP_NAME_HUMP}")


class FlowInfo(BaseModel):
    name: str
    definition_type: str
    description: Optional[str] = None
    label: Optional[str] = None
    package: Optional[str] = None
    package_type: Optional[str] = None
    root: Optional[str] = None
    path: Optional[str] = None
    version: Optional[str] = None


class VariablesResponse(VariablesRequest):
    """Variable response model."""

    id: int = Field(
        ...,
        description="The id of the variable",
        examples=[1],
    )


class VariablesKeyResponse(_VariablesRequestBase):
    """Variables Key response model.

    Just include the key, for select options in the frontend.
    """


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


class FlowDebugRequest(BaseModel):
    """Flow response model"""

    model_config = ConfigDict(title=f"FlowDebugRequest")
    flow: ServeRequest = Field(
        ...,
        title="The flow to debug",
        description="The flow to debug",
    )
    request: Union[CommonLLMHttpRequestBody, Dict[str, Any]] = Field(
        ...,
        title="The request to debug",
        description="The request to debug",
    )
    variables: Optional[Dict[str, Any]] = Field(
        None,
        title="The variables to debug",
        description="The variables to debug",
    )
    user_name: Optional[str] = Field(None, description="User name")
    sys_code: Optional[str] = Field(None, description="System code")
