from typing import Optional

from dbgpt._private.pydantic import BaseModel


class FeedBackBody(BaseModel):
    """conv_uid: conversation id"""

    conv_uid: Optional[str]

    """conv_index: conversation index"""
    conv_index: Optional[int]

    """question: human question"""
    question: Optional[str]

    """score: rating of the llm's answer"""
    score: Optional[int]

    """ques_type: question type"""
    ques_type: Optional[str]

    user_name: Optional[str] = None

    """messages: rating detail"""
    messages: Optional[str] = None

    """knowledge_space: knowledge space"""
    knowledge_space: Optional[str] = None
