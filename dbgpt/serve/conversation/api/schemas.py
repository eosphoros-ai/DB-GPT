# Define your Pydantic schemas here
from typing import Any, Dict, Optional

from dbgpt._private.pydantic import BaseModel, ConfigDict, Field, model_to_dict

from ..config import SERVE_APP_NAME_HUMP


class ServeRequest(BaseModel):
    """Conversation request model"""

    model_config = ConfigDict(title=f"ServeRequest for {SERVE_APP_NAME_HUMP}")

    # Just for query
    chat_mode: str = Field(
        default=None,
        description="The chat mode.",
        examples=[
            "chat_normal",
        ],
    )
    conv_uid: Optional[str] = Field(
        default=None,
        description="The conversation uid.",
        examples=[
            "5e7100bc-9017-11ee-9876-8fe019728d79",
        ],
    )
    user_name: Optional[str] = Field(
        default=None,
        description="The user name.",
        examples=[
            "zhangsan",
        ],
    )
    sys_code: Optional[str] = Field(
        default=None,
        description="The system code.",
        examples=[
            "dbgpt",
        ],
    )

    def to_dict(self, **kwargs) -> Dict[str, Any]:
        """Convert the model to a dictionary"""
        return model_to_dict(self, **kwargs)


class ServerResponse(BaseModel):
    """Conversation response model"""

    model_config = ConfigDict(
        title=f"ServerResponse for {SERVE_APP_NAME_HUMP}", protected_namespaces=()
    )

    conv_uid: str = Field(
        ...,
        description="The conversation uid.",
        examples=[
            "5e7100bc-9017-11ee-9876-8fe019728d79",
        ],
    )
    user_input: str = Field(
        ...,
        description="The user input, we return it as the summary the conversation.",
        examples=[
            "Hello world",
        ],
    )
    chat_mode: str = Field(
        ...,
        description="The chat mode.",
        examples=[
            "chat_normal",
        ],
    )
    select_param: Optional[str] = Field(
        default=None,
        description="The select param.",
        examples=[
            "my_knowledge_space_name",
        ],
    )
    model_name: Optional[str] = Field(
        default=None,
        description="The model name.",
        examples=[
            "vicuna-13b-v1.5",
        ],
    )
    user_name: Optional[str] = Field(
        default=None,
        description="The user name.",
        examples=[
            "zhangsan",
        ],
    )
    sys_code: Optional[str] = Field(
        default=None,
        description="The system code.",
        examples=[
            "dbgpt",
        ],
    )

    def to_dict(self, **kwargs) -> Dict[str, Any]:
        """Convert the model to a dictionary"""
        return model_to_dict(self, **kwargs)


class MessageVo(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    role: str = Field(
        ...,
        description="The role that sends out the current message.",
        examples=["human", "ai", "view"],
    )
    context: str = Field(
        ...,
        description="The current message content.",
        examples=[
            "Hello",
            "Hi, how are you?",
        ],
    )

    order: int = Field(
        ...,
        description="The current message order.",
        examples=[
            1,
            2,
        ],
    )

    time_stamp: Optional[Any] = Field(
        default=None,
        description="The current message time stamp.",
        examples=[
            "2023-01-07 09:00:00",
        ],
    )

    model_name: Optional[str] = Field(
        default=None,
        description="The model name.",
        examples=[
            "vicuna-13b-v1.5",
        ],
    )

    def to_dict(self, **kwargs) -> Dict[str, Any]:
        """Convert the model to a dictionary"""
        return model_to_dict(self, **kwargs)
