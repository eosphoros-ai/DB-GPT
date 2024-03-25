"""this module contains the schemas for the dbgpt client."""
import json
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from fastapi import File, UploadFile

from dbgpt._private.pydantic import BaseModel, Field
from dbgpt.rag.chunk_manager import ChunkParameters


class ChatCompletionRequestBody(BaseModel):
    """ChatCompletion LLM http request body."""

    model: str = Field(
        ..., description="The model name", examples=["gpt-3.5-turbo", "proxyllm"]
    )
    messages: Union[str, List[str]] = Field(
        ..., description="User input messages", examples=["Hello", "How are you?"]
    )
    stream: bool = Field(default=True, description="Whether return stream")

    temperature: Optional[float] = Field(
        default=None,
        description="What sampling temperature to use, between 0 and 2. Higher values "
        "like 0.8 will make the output more random, "
        "while lower values like 0.2 will "
        "make it more focused and deterministic.",
    )
    max_new_tokens: Optional[int] = Field(
        default=None,
        description="The maximum number of tokens that can be generated in the chat "
        "completion.",
    )
    conv_uid: Optional[str] = Field(
        default=None, description="The conversation id of the model inference"
    )
    span_id: Optional[str] = Field(
        default=None, description="The span id of the model inference"
    )
    chat_mode: Optional[str] = Field(
        default="chat_normal",
        description="The chat mode",
        examples=["chat_awel_flow", "chat_normal"],
    )
    chat_param: Optional[str] = Field(
        default=None,
        description="The chat param of chat mode",
    )
    user_name: Optional[str] = Field(
        default=None, description="The user name of the model inference"
    )
    sys_code: Optional[str] = Field(
        default=None, description="The system code of the model inference"
    )
    incremental: bool = Field(
        default=True,
        description="Used to control whether the content is returned incrementally "
        "or in full each time. "
        "If this parameter is not provided, the default is full return.",
    )
    enable_vis: str = Field(
        default=True, description="response content whether to output vis label"
    )


class ChatMode(Enum):
    """Chat mode."""

    CHAT_NORMAL = "chat_normal"
    CHAT_APP = "chat_app"
    CHAT_AWEL_FLOW = "chat_flow"
    CHAT_KNOWLEDGE = "chat_knowledge"


class AwelTeamModel(BaseModel):
    """Awel team model."""

    dag_id: str = Field(
        ...,
        description="The unique id of dag",
        examples=["flow_dag_testflow_66d8e9d6-f32e-4540-a5bd-ea0648145d0e"],
    )
    uid: str = Field(
        default=None,
        description="The unique id of flow",
        examples=["66d8e9d6-f32e-4540-a5bd-ea0648145d0e"],
    )
    name: Optional[str] = Field(
        default=None,
        description="The name of dag",
    )
    label: Optional[str] = Field(
        default=None,
        description="The label of dag",
    )
    version: Optional[str] = Field(
        default=None,
        description="The version of dag",
    )
    description: Optional[str] = Field(
        default=None,
        description="The description of dag",
    )
    editable: bool = Field(
        default=False,
        description="is the dag is editable",
        examples=[True, False],
    )
    state: Optional[str] = Field(
        default=None,
        description="The state of dag",
    )
    user_name: Optional[str] = Field(
        default=None,
        description="The owner of current dag",
    )
    sys_code: Optional[str] = Field(
        default=None,
        description="The system code of current dag",
    )
    flow_category: Optional[str] = Field(
        default="common",
        description="The flow category of current dag",
    )


class AgentResourceType(Enum):
    """Agent resource type."""

    DB = "database"
    Knowledge = "knowledge"
    Internet = "internet"
    Plugin = "plugin"
    TextFile = "text_file"
    ExcelFile = "excel_file"
    ImageFile = "image_file"
    AwelFlow = "awel_flow"


class AgentResourceModel(BaseModel):
    """Agent resource model."""

    type: AgentResourceType
    name: str
    value: str
    is_dynamic: bool = (
        False  # Is the current resource predefined or dynamically passed in?
    )

    @staticmethod
    def from_dict(d: Dict[str, Any]):
        """From dict."""
        if d is None:
            return None
        return AgentResourceModel(
            type=AgentResourceType(d.get("type")),
            name=d.get("name"),
            introduce=d.get("introduce"),
            value=d.get("value", None),
            is_dynamic=d.get("is_dynamic", False),
        )

    @staticmethod
    def from_json_list_str(d: Optional[str]):
        """From json list str."""
        if d is None:
            return None
        try:
            json_array = json.loads(d)
        except Exception as e:
            raise ValueError(f"Illegal AgentResource json string！{d},{e}")
        return [AgentResourceModel.from_dict(item) for item in json_array]

    def to_dict(self) -> Dict[str, Any]:
        """To dict."""
        temp = self.dict()
        for field, value in temp.items():
            if isinstance(value, Enum):
                temp[field] = value.value
        return temp


class AppDetailModel(BaseModel):
    """App detail model."""

    app_code: Optional[str] = Field(None, description="app code")
    app_name: Optional[str] = Field(None, description="app name")
    agent_name: Optional[str] = Field(None, description="agent name")
    node_id: Optional[str] = Field(None, description="node id")
    resources: Optional[list[AgentResourceModel]] = Field(None, description="resources")
    prompt_template: Optional[str] = Field(None, description="prompt template")
    llm_strategy: Optional[str] = Field(None, description="llm strategy")
    llm_strategy_value: Optional[str] = Field(None, description="llm strategy value")
    created_at: datetime = datetime.now()
    updated_at: datetime = datetime.now()


class AppModel(BaseModel):
    """App model."""

    app_code: Optional[str] = Field(None, title="app code")
    app_name: Optional[str] = Field(None, title="app name")
    app_describe: Optional[str] = Field(None, title="app describe")
    team_mode: Optional[str] = Field(None, title="team mode")
    language: Optional[str] = Field("en", title="language")
    team_context: Optional[Union[str, AwelTeamModel]] = Field(
        None, title="team context"
    )
    user_code: Optional[str] = Field(None, title="user code")
    sys_code: Optional[str] = Field(None, title="sys code")
    is_collected: Optional[str] = Field(None, title="is collected")
    icon: Optional[str] = Field(None, title="icon")
    created_at: datetime = datetime.now()
    updated_at: datetime = datetime.now()
    details: List[AppDetailModel] = Field([], title="app details")


class SpaceModel(BaseModel):
    """Space model."""

    id: str = Field(
        default=None,
        description="space id",
    )
    name: str = Field(
        default=None,
        description="knowledge space name",
    )
    vector_type: str = Field(
        default=None,
        description="vector type",
    )
    desc: str = Field(
        default=None,
        description="space description",
    )
    owner: str = Field(
        default=None,
        description="space owner",
    )
    context: Optional[str] = Field(
        default=None,
        description="space argument context",
    )


class DocumentModel(BaseModel):
    """Document model."""

    id: int = Field(None, description="The doc id")
    doc_name: str = Field(None, description="doc name")
    """doc_type: document type"""
    doc_type: str = Field(None, description="The doc type")
    """content: description"""
    content: str = Field(None, description="content")
    """doc file"""
    doc_file: UploadFile = Field(File(None), description="doc file")
    """doc_source: doc source"""
    doc_source: str = Field(None, description="doc source")
    """doc_source: doc source"""
    space_id: str = Field(None, description="space_id")


class SyncModel(BaseModel):
    """Sync model."""

    """doc_id: doc id"""
    doc_id: str = Field(None, description="The doc id")

    """space id"""
    space_id: str = Field(None, description="The space id")

    """model_name: model name"""
    model_name: Optional[str] = Field(None, description="model name")

    """chunk_parameters: chunk parameters
    """
    chunk_parameters: ChunkParameters = Field(None, description="chunk parameters")
