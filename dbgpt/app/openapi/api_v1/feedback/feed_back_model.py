from dbgpt._private.pydantic import BaseModel
from typing import Optional


class FeedBackBody(BaseModel):
    """conv_uid: conversation id"""

    conv_uid: str

    """conv_index: conversation index"""
    conv_index: int

    """question: human question"""
    question: str

    """score: rating of the llm's answer"""
    score: int

    """ques_type: question type"""
    ques_type: str

    user_name: Optional[str] = None

    """messages: rating detail"""
    messages: Optional[str] = None

    """knowledge_space: knowledge space"""
    knowledge_space: Optional[str] = None
