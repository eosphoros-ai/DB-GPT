from pydantic import BaseModel, Field
from typing import TypeVar, Union, List, Generic

T = TypeVar('T')


class Result(Generic[T], BaseModel):
    success: bool
    err_code: str = None
    err_msg: str = None
    data: List[T] = None

    @classmethod
    def succ(cls, data: List[T]):
        return Result(success=True, err_code=None, err_msg=None, data=data)

    @classmethod
    def faild(cls, msg):
        return Result(success=False, err_code="E000X", err_msg=msg, data=None)

    @classmethod
    def faild(cls, code, msg):
        return Result(success=False, err_code=code, err_msg=msg, data=None)


class ConversationVo(BaseModel):
    """
    dialogue_uid
    """
    conv_uid: str = Field(...,  description="dialogue uid")
    """ 
    user input 
    """
    user_input: str
    """ 
    the scene of chat 
    """
    chat_mode: str  = Field(..., description="the scene of chat ")
    """
    chat scene select param 
    """
    select_param: str


class MessageVo(BaseModel):
    """
    role that sends out the current message 
    """
    role: str
    """
    current message 
    """
    context: str
    """
    time the current message was sent 
    """
    time_stamp: float
