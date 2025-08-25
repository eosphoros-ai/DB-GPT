from typing import Any, Dict, List, Optional

from dbgpt._private.pydantic import (
    BaseModel,
    Field,
    model_to_dict,
)


class VisBase(BaseModel):
    uid: str = Field(..., description="vis component uid")
    type: str = Field(..., description="vis data update type")
    message_id: Optional[str] = Field(None, description="vis component message id")

    def to_dict(self, **kwargs) -> Dict[str, Any]:
        """Convert the model to a dictionary"""
        return model_to_dict(self, **kwargs)


class VisTextContent(VisBase):
    markdown: str = Field(..., description="vis message content")


class VisMessageContent(VisBase):
    markdown: str = Field(..., description="vis msg content")
    role: Optional[str] = Field(
        default=None, description="vis message generate agent role"
    )
    name: Optional[str] = Field(
        default=None, description="vis message generate agent name"
    )
    avatar: Optional[str] = Field(
        default=None, description="vis message generate agent avatar"
    )
    model: Optional[str] = Field(
        default=None, description="vis message generate agent model"
    )


class VisTaskContent(BaseModel):
    task_id: str = Field(default=None, description="vis task id")
    task_uid: Optional[str] = Field(default=None, description="vis task uid")
    task_content: Optional[str] = Field(default=None, description="vis task content")
    task_link: Optional[str] = Field(default=None, description="vis task link")
    agent_id: Optional[str] = Field(default=None, description="vis task agent id")
    agent_name: Optional[str] = Field(default=None, description="vis task agent name")
    agent_link: Optional[str] = Field(default=None, description="vis task agent link")
    task_name: Optional[str] = Field(default=None, description="vis task  name")
    avatar: Optional[str] = Field(default=None, description="vis task avatar")

    def to_dict(self, **kwargs) -> Dict[str, Any]:
        """Convert the model to a dictionary"""
        return model_to_dict(self, **kwargs)


class VisPlansContent(VisBase):
    tasks: List[VisTaskContent] = Field(default=[], description="vis plan tasks")

    def to_dict(self, **kwargs) -> Dict[str, Any]:
        tasks_dict = []
        for step in self.tasks:
            tasks_dict.append(step.to_dict())
        dict_value = model_to_dict(self, exclude={"tasks"})
        dict_value["tasks"] = tasks_dict
        return dict_value


class VisStepContent(VisBase):
    avatar: Optional[str] = Field(default=None, description="vis task avatar")
    status: Optional[str] = Field(default=None, description="vis task status")
    tool_name: Optional[str] = Field(default=None, description="vis task tool name")
    tool_args: Optional[str] = Field(default=None, description="vis task tool args")
    tool_result: Optional[str] = Field(default=None, description="vis tool result")

    err_msg: Optional[str] = Field(
        default=None, description="vis task tool error message"
    )
    progress: Optional[int] = Field(
        default=None, description="vis task tool  exceute progress"
    )
    tool_execute_link: Optional[str] = Field(
        default=None, description="vis task tool exceute link"
    )


class StepInfo(BaseModel):
    avatar: Optional[str] = Field(default=None, description="vis task avatar")
    status: Optional[str] = Field(default=None, description="vis task status")
    tool_name: Optional[str] = Field(default=None, description="vis task tool name")
    tool_args: Optional[str] = Field(default=None, description="vis task tool args")
    tool_result: Optional[str] = Field(default=None, description="vis tool result")

    err_msg: Optional[str] = Field(
        default=None, description="vis task tool error message"
    )
    progress: Optional[int] = Field(
        default=None, description="vis task tool  exceute progress"
    )
    tool_execute_link: Optional[str] = Field(
        default=None, description="vis task tool exceute link"
    )


class VisStepsContent(VisBase):
    steps: Optional[List[StepInfo]] = Field(
        default=None, description="vis task tools exceute info"
    )


class VisThinkingContent(VisBase):
    markdown: str = Field(..., description="vis thinking content")
    think_link: str = Field(None, description="vis thinking link")


class VisNode(VisBase):
    id: str = Field(..., description="id of the node")
    markdown: str = Field(..., description="content of the node")
    node_type: str = Field(None, description="type of the node, user/bot")
    avatar: str = Field(None, description="avatar of the node")
    agent_name: str = Field(None, description="name of the agent")
    title: str = Field(None, description="title of the node")
    status: str = Field(None, description="status of the node")


class VisEdge(VisBase):
    source: str = Field(..., description="source of the edge")
    target: str = Field(..., description="target of the edge")


class VisGraph(VisBase):
    nodes: list[VisNode] = Field(..., description="nodes in the graph")
    edges: list[VisEdge] = Field(..., description="edges in the graph")


class VisSelectContent(VisBase):
    markdown: str = Field(..., description="content of the select option")
    confirm_message: Optional[str] = Field(
        None,
        description="When the user selects this option, a message is simulated to be sent by the user, and this field represents the content of the message.",
    )
    extra: Optional[dict] = Field(
        None,
        description="When the user selects this option, this extended information will be passed to the system.",
    )
