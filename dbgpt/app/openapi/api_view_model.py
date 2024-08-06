import socket
import time
import uuid
from enum import Enum
from typing import Any, Dict, Generic, List, Literal, Optional, TypeVar

from dbgpt._private.pydantic import BaseModel, ConfigDict, Field, model_to_dict
from dbgpt.core.awel import CommonLLMHttpResponseBody

T = TypeVar("T")


class Result(BaseModel, Generic[T]):
    success: Optional[bool]
    err_code: Optional[str] = None
    err_msg: Optional[str] = None
    data: Optional[T] = None
    host_name: Optional[str] = socket.gethostname()

    @classmethod
    def succ(cls, data: T = None):
        return Result(success=True, err_code=None, err_msg=None, data=data)

    @classmethod
    def failed(cls, code: str = "E000X", msg=None):
        return Result(success=False, err_code=code, err_msg=msg, data=None)

    def to_dict(self) -> Dict[str, Any]:
        return model_to_dict(self)


class ChatSceneVo(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    chat_scene: Optional[str] = Field(..., description="chat_scene")
    scene_name: Optional[str] = Field(..., description="chat_scene name show for user")
    scene_describe: Optional[str] = Field("", description="chat_scene describe ")
    param_title: Optional[str] = Field(
        "", description="chat_scene required parameter title"
    )
    show_disable: Optional[bool] = Field(False, description="chat_scene show disable")


class ConversationVo(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    """
    dialogue_uid
    """

    conv_uid: Optional[str] = ""
    """ 
    user input 
    """
    user_input: Optional[str] = ""
    """
    user
    """
    user_name: Optional[str] = None
    """ 
    the scene of chat 
    """
    chat_mode: Optional[str] = ""
    """
    the app of  chat
    """
    app_code: Optional[str] = ""

    temperature: Optional[float] = 0.5
    """
    chat scene select param 
    """
    select_param: Optional[Any] = None
    """
    llm model name
    """
    model_name: Optional[str] = None

    """Used to control whether the content is returned incrementally or in full each time. 
    If this parameter is not provided, the default is full return.
    """
    incremental: Optional[bool] = False

    sys_code: Optional[str] = None

    ext_info: Optional[dict] = {}


class MessageVo(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    """
    role that sends out the current message
    """

    role: Optional[str]
    """
    current message 
    """
    context: Optional[str]

    """ message postion order """
    order: Optional[int]

    """
    time the current message was sent 
    """
    time_stamp: Optional[Any] = None

    """
    model_name
    """
    model_name: Optional[str]


class DeltaMessage(BaseModel):
    role: Optional[str] = None
    content: Optional[str] = None


class ChatCompletionResponseStreamChoice(BaseModel):
    index: Optional[int]
    delta: Optional[DeltaMessage]
    finish_reason: Optional[Literal["stop", "length"]] = None


class ChatCompletionStreamResponse(BaseModel):
    id: Optional[str] = Field(default_factory=lambda: f"chatcmpl-{str(uuid.uuid1())}")
    created: Optional[int] = Field(default_factory=lambda: int(time.time()))
    model: Optional[str] = None
    choices: Optional[List[ChatCompletionResponseStreamChoice]]


class ChatContext(BaseModel):
    model: Optional[str] = Field(
        ..., description="The model name", examples=["gpt-3.5-turbo", "proxyllm"]
    )


class ChatAppContext(ChatContext):
    app_code: Optional[str]


class ChatKnowledgeContext(ChatContext):
    space: Optional[str]


class ChatFlowContext(ChatContext):
    flow_id: Optional[str]


class OpenAPIChatCompletionRequest(BaseModel):
    conv_uid: Optional[str] = Field(None, description="conversation uid")
    user_input: Optional[str] = Field(
        None, description="User input messages", examples=["Hello", "How are you?"]
    )
    chat_type: Optional[str] = Field(
        "normal",
        description="chat type",
        examples=["normal", "app", "flow", "knowledge"],
    )
    stream: Optional[bool] = Field(default=True, description="Whether return stream")
    context: Optional[Dict[str, Any]] = Field(
        None,
        description="The context of the model inference",
    )


class LinksFilters(BaseModel):
    chatRoomId: Optional[str] = Field(None, description="chat room id")
    chatRoomIds: Optional[str] = Field(None, description="chat room ids")


class LinksChatCompletionRequest(BaseModel):
    conversation_id: Optional[str] = Field(None, description="conversation uid")
    message_id: Optional[str] = Field(None, description="小蜜这边用户输入的消息Id")
    filters: Optional[LinksFilters] = Field(
        None,
        description="小蜜 filters",
        examples=None,
    )
    query: Optional[str] = Field(default=None, description="query")


class ScriptLink(BaseModel):
    sequence: Optional[str] = Field(None, description="sequence")
    title: Optional[str] = Field(None, description="title")
    url: Optional[str] = Field(None, description="url")


class LinksChatExtraResponse(BaseModel):
    gptModel: Optional[str] = Field(None, description="gpt model")
    scriptLinks: Optional[List[ScriptLink]] = Field(None, description="scriptLinks")


class ChatType(Enum):
    NORMAL = "normal"
    APP = "app"
    FLOW = "flow"
    KNOWLEDGE = "knowledge"


class APIToken(BaseModel):
    api_key: Optional[str] = Field(..., description="ant app name")
    api_token: Optional[str] = Field(..., description="api token")
    user_id: Optional[str] = Field(..., description="user id")
