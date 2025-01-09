# Define your Pydantic schemas here
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from dbgpt._private.pydantic import BaseModel, ConfigDict, Field, model_to_dict


class ConvFeedbackReasonType(Enum):
    WRONG_ANSWER = "Wrong answer"
    WRONG_SOURCE = "Wrong source"
    OUTDATED_CONTENT = "Outdated content"
    UNREAL_CONTENT = "Data is inaccurate"
    ILLEGAL_CONTENT = "Harmful content"
    OTHERS = "Others"

    @classmethod
    def to_dict(cls, reason_type):
        return {
            "reason_type": reason_type.name,
            "reason": reason_type.value,
        }

    @classmethod
    def of_type(cls, type_name: str):
        for name, member in cls.__members__.items():
            if name == type_name:
                return member
        raise ValueError(f"{type_name} is not a valid ConvFeedbackReasonType")


class ServeRequest(BaseModel):
    """Feedback request model"""

    id: Optional[int] = Field(None, description="Primary Key")
    gmt_created: Optional[str] = Field(None, description="Creation time")
    gmt_modified: Optional[str] = Field(None, description="Modification time")
    user_code: Optional[str] = Field(None, description="User ID")
    user_name: Optional[str] = Field(None, description="User Name")
    conv_uid: Optional[str] = Field(None, description="Conversation ID")
    message_id: Optional[str] = Field(
        None, description="Message ID, round_index for table chat_history_message"
    )
    score: Optional[float] = Field(None, description="Rating of answers")
    question: Optional[str] = Field(None, description="User question")
    ques_type: Optional[str] = Field(None, description="User question type")
    knowledge_space: Optional[str] = Field(None, description="Use resource")
    feedback_type: Optional[str] = Field(
        None, description="Feedback type like or unlike"
    )
    reason_type: Optional[str] = Field(None, description="Feedback reason category")
    remark: Optional[str] = Field(None, description="Remarks")
    reason_types: Optional[List[str]] = Field(
        default=[], description="Feedback reason categories"
    )
    reason: Optional[List[Dict]] = Field(
        default=[], description="Feedback reason category"
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict."""
        return model_to_dict(self)


ServerResponse = ServeRequest
