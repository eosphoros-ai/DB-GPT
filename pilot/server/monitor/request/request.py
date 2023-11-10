from pydantic import BaseModel


class LlmManageRequest(BaseModel):

    model_type: str = None

    sk: str = None

    desc: str = None

    user_id: str = None
