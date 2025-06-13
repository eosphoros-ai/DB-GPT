from typing import Any, List, Optional, Union

from dbgpt._private.pydantic import (
    BaseModel,
    Field,
    model_to_dict,
)

from ...resource.base import AgentResource


class TeamContext(BaseModel):
    can_ask_user: Optional[bool] = Field(
        True,
        description="Can ask user",
        examples=[
            True,
            False,
        ],
    )
    llm_strategy: Optional[str] = Field(
        None, description="The team leader's llm strategy"
    )
    llm_strategy_value: Union[Optional[str], Optional[List[Any]]] = Field(
        None, description="The team leader's llm config"
    )
    prompt_template: Optional[str] = Field(
        None, description="The team leader's prompt template!"
    )
    resources: Optional[list[AgentResource]] = Field(
        None, description="The team leader's prompt template!"
    )

    def to_dict(self):
        return model_to_dict(self)


class SingleAgentContext(TeamContext):
    agent_name: Optional[str] = Field(None, description="Current agent name")
    agent_role: Optional[str] = Field(None, description="Current agent role")
