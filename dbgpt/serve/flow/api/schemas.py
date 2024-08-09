from typing import Any, List, Literal, Optional

from dbgpt._private.pydantic import BaseModel, ConfigDict, Field
from dbgpt.core.awel.flow.flow_factory import FlowPanel
from dbgpt.core.awel.util.parameter_util import RefreshOptionRequest

from ..config import SERVE_APP_NAME_HUMP

ServeRequest = FlowPanel


class ServerResponse(FlowPanel):
    """Flow response model"""

    # TODO define your own fields here

    model_config = ConfigDict(title=f"ServerResponse for {SERVE_APP_NAME_HUMP}")


class VariablesRequest(BaseModel):
    """Variable request model.

    For creating a new variable in the DB-GPT.
    """

    key: str = Field(
        ...,
        description="The key of the variable to create",
        examples=["dbgpt.model.openai.api_key"],
    )
    name: str = Field(
        ...,
        description="The name of the variable to create",
        examples=["my_first_openai_key"],
    )
    label: str = Field(
        ...,
        description="The label of the variable to create",
        examples=["My First OpenAI Key"],
    )
    value: Any = Field(
        ..., description="The value of the variable to create", examples=["1234567890"]
    )
    value_type: Literal["str", "int", "float", "bool"] = Field(
        "str",
        description="The type of the value of the variable to create",
        examples=["str", "int", "float", "bool"],
    )
    category: Literal["common", "secret"] = Field(
        ...,
        description="The category of the variable to create",
        examples=["common"],
    )
    scope: str = Field(
        ...,
        description="The scope of the variable to create",
        examples=["global"],
    )
    scope_key: Optional[str] = Field(
        ...,
        description="The scope key of the variable to create",
        examples=["dbgpt"],
    )
    enabled: Optional[bool] = Field(
        True,
        description="Whether the variable is enabled",
        examples=[True],
    )
    user_name: Optional[str] = Field(None, description="User name")
    sys_code: Optional[str] = Field(None, description="System code")


class VariablesResponse(VariablesRequest):
    """Variable response model."""

    id: int = Field(
        ...,
        description="The id of the variable",
        examples=[1],
    )


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
