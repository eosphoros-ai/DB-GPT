from datetime import datetime
from typing import Dict, List, Optional, Union

from fastapi import File, UploadFile
from pydantic import BaseModel, Field

from dbgpt.agent.resource.resource_api import AgentResource
from dbgpt.rag.chunk_manager import ChunkParameters


class ChatCompletionRequestBody(BaseModel):
    """ChatCompletion LLM http request body."""

    model: str = Field(
        ..., description="The model name", examples=["gpt-3.5-turbo", "proxyllm"]
    )
    messages: Union[str, List[str]] = Field(
        ..., description="User input messages", examples=["Hello", "How are you?"]
    )
    stream: bool = Field(default=False, description="Whether return stream")

    temperature: Optional[float] = Field(
        default=None,
        description="What sampling temperature to use, between 0 and 2. Higher values "
        "like 0.8 will make the output more random, while lower values like 0.2 will "
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
        description="Used to control whether the content is returned incrementally or in full each time. If this parameter is not provided, the default is full return.",
    )
    enable_vis: str = Field(
        default=True, description="response content whether to output vis label"
    )


class SpaceModel(BaseModel):
    """name: knowledge space name"""

    """vector_type: vector type"""
    id: int = Field(None, description="The space id")
    name: str = Field(None, description="The space name")
    """vector_type: vector type"""
    vector_type: str = Field(None, description="The vector type")
    """desc: description"""
    desc: str = Field(None, description="The description")
    """owner: owner"""
    owner: str = Field(None, description="The owner")


class AppDetailModel(BaseModel):
    app_code: Optional[str] = Field(None, title="app code")
    app_name: Optional[str] = Field(None, title="app name")
    agent_name: Optional[str] = Field(None, title="agent name")
    node_id: Optional[str] = Field(None, title="node id")
    resources: Optional[list[AgentResource]] = Field(None, title="resources")
    prompt_template: Optional[str] = Field(None, title="prompt template")
    llm_strategy: Optional[str] = Field(None, title="llm strategy")
    llm_strategy_value: Optional[str] = Field(None, title="llm strategy value")
    created_at: datetime = datetime.now()
    updated_at: datetime = datetime.now()


class AwelTeamModel(BaseModel):
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


class AppModel(BaseModel):
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


class DocumentModel(BaseModel):
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
    """Sync model"""

    """doc_id: doc id"""
    doc_id: str = Field(None, description="The doc id")

    """space id"""
    space_id: str = Field(None, description="The space id")

    """model_name: model name"""
    model_name: Optional[str] = Field(None, description="model name")

    """chunk_parameters: chunk parameters 
    """
    chunk_parameters: ChunkParameters = Field(None, description="chunk parameters")
