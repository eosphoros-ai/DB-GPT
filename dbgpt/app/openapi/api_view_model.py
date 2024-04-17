from typing import Any, Dict, Generic, Optional, TypeVar

from dbgpt._private.pydantic import BaseModel, ConfigDict, Field, model_to_dict

T = TypeVar("T")


class Result(BaseModel, Generic[T]):
    success: bool
    err_code: Optional[str] = None
    err_msg: Optional[str] = None
    data: Optional[T] = None

    @classmethod
    def succ(cls, data: T):
        return Result(success=True, err_code=None, err_msg=None, data=data)

    @classmethod
    def failed(cls, code: str = "E000X", msg=None):
        return Result(success=False, err_code=code, err_msg=msg, data=None)

    def to_dict(self) -> Dict[str, Any]:
        return model_to_dict(self)


class ChatSceneVo(BaseModel):
    chat_scene: str = Field(..., description="chat_scene")
    scene_name: str = Field(..., description="chat_scene name show for user")
    scene_describe: str = Field("", description="chat_scene describe ")
    param_title: str = Field("", description="chat_scene required parameter title")
    show_disable: bool = Field(False, description="chat_scene show disable")


class ConversationVo(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

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
    user_name: Optional[str] = Field(None, description="user name")
    """ 
    the scene of chat 
    """
    chat_mode: str = ""

    """
    chat scene select param 
    """
    select_param: Optional[str] = Field(None, description="chat scene select param")
    """
    llm model name
    """
    model_name: Optional[str] = Field(None, description="llm model name")

    """Used to control whether the content is returned incrementally or in full each time. 
    If this parameter is not provided, the default is full return.
    """
    incremental: bool = False

    sys_code: Optional[str] = Field(None, description="System code")


class MessageVo(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

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
    time_stamp: Optional[Any] = Field(
        None, description="time the current message was sent"
    )

    """
    model_name
    """
    model_name: str
