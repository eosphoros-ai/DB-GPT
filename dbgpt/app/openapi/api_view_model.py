from dbgpt._private.pydantic import BaseModel, Field
from typing import TypeVar, Generic, Any, Optional, Literal, List
import uuid
import time

T = TypeVar("T")


class Result(Generic[T], BaseModel):
    success: bool
    err_code: str = None
    err_msg: str = None
    data: T = None

    @classmethod
    def succ(cls, data: T):
        return Result(success=True, err_code=None, err_msg=None, data=data)

    @classmethod
    def failed(cls, msg):
        return Result(success=False, err_code="E000X", err_msg=msg, data=None)

    @classmethod
    def failed(cls, code, msg):
        return Result(success=False, err_code=code, err_msg=msg, data=None)


class ChatSceneVo(BaseModel):
    chat_scene: str = Field(..., description="chat_scene")
    scene_name: str = Field(..., description="chat_scene name show for user")
    scene_describe: str = Field("", description="chat_scene describe ")
    param_title: str = Field("", description="chat_scene required parameter title")
    show_disable: bool = Field(False, description="chat_scene show disable")


class ConversationVo(BaseModel):
    """
    dialogue_uid
    """

    conv_uid: str = ""
    """ 
    user input 
    """
    user_input: str = ""
    """
    user
    """
    user_name: str = None
    """ 
    the scene of chat 
    """
    chat_mode: str = ""

    """
    chat scene select param 
    """
    select_param: str = None
    """
    llm model name
    """
    model_name: str = None

    """Used to control whether the content is returned incrementally or in full each time. 
    If this parameter is not provided, the default is full return.
    """
    incremental: bool = False

    sys_code: Optional[str] = None


class MessageVo(BaseModel):
    """
    role that sends out the current message
    """

    role: str
    """
    current message 
    """
    context: str

    """ message postion order """
    order: int

    """
    time the current message was sent 
    """
    time_stamp: Any = None

    """
    model_name
    """
    model_name: str


class DeltaMessage(BaseModel):
    role: Optional[str] = None
    content: Optional[str] = None


class ChatCompletionResponseStreamChoice(BaseModel):
    index: int
    delta: DeltaMessage
    finish_reason: Optional[Literal["stop", "length"]] = None


class ChatCompletionStreamResponse(BaseModel):
    id: str = Field(default_factory=lambda: f"chatcmpl-{str(uuid.uuid1())}")
    created: int = Field(default_factory=lambda: int(time.time()))
    model: str
    choices: List[ChatCompletionResponseStreamChoice]
