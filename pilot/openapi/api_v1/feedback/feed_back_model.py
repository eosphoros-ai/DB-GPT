from pydantic.main import BaseModel


class FeedBackBody(BaseModel):
    """conv_uid: conversation id"""

    conv_uid: str

    """conv_index: conversation index"""
    conv_index: int

    """question: human question"""
    question: str

    """knowledge_space: knowledge space"""
    knowledge_space: str

    """score: rating of the llm's answer"""
    score: int

    """ques_type: question type"""
    ques_type: str

    """messages: rating detail"""
    messages: str
