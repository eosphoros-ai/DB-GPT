# Define your Pydantic schemas here
from typing import Any, Dict, Optional

from dbgpt._private.pydantic import BaseModel, ConfigDict, Field, model_to_dict

from ..config import SERVE_APP_NAME_HUMP


class ServeRequest(BaseModel):
    """DbgptsMy request model"""

    id: Optional[int] = Field(None, description="id")
    user_code: Optional[str] = Field(None, description="My gpts user code")
    user_name: Optional[str] = Field(None, description="My gpts user name")
    sys_code: Optional[str] = Field(None, description="My gpts sys code")
    name: str = Field(..., description="My gpts name")
    file_name: str = Field(..., description="My gpts file name")
    type: Optional[str] = Field(None, description="My gpts type")
    version: Optional[str] = Field(None, description="My gpts version")
    use_count: Optional[int] = Field(None, description="My gpts use count")
    succ_count: Optional[int] = Field(None, description="My gpts succ count")
    gmt_created: Optional[str] = Field(None, description="My gpts install time")

    model_config = ConfigDict(title=f"ServeRequest for {SERVE_APP_NAME_HUMP}")

    def to_dict(self, **kwargs) -> Dict[str, Any]:
        """Convert the model to a dictionary"""
        return model_to_dict(self, **kwargs)


ServerResponse = ServeRequest
