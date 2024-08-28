# Define your Pydantic schemas here
from typing import Any, Dict, Optional

from dbgpt._private.pydantic import BaseModel, ConfigDict, Field, model_to_dict

from ..config import SERVE_APP_NAME_HUMP


class ServeRequest(BaseModel):
    """DbgptsHub request model"""

    id: Optional[int] = Field(None, description="id")
    name: Optional[str] = Field(None, description="Dbgpts name")
    type: Optional[str] = Field(None, description="Dbgpts type")
    version: Optional[str] = Field(None, description="Dbgpts version")
    description: Optional[str] = Field(None, description="Dbgpts description")
    author: Optional[str] = Field(None, description="Dbgpts author")
    email: Optional[str] = Field(None, description="Dbgpts email")
    storage_channel: Optional[str] = Field(None, description="Dbgpts storage channel")
    storage_url: Optional[str] = Field(None, description="Dbgpts storage url")
    download_param: Optional[str] = Field(None, description="Dbgpts download param")
    installed: Optional[int] = Field(None, description="Dbgpts installed")

    model_config = ConfigDict(title=f"ServeRequest for {SERVE_APP_NAME_HUMP}")

    def to_dict(self, **kwargs) -> Dict[str, Any]:
        """Convert the model to a dictionary"""
        return model_to_dict(self, **kwargs)


class ServerResponse(ServeRequest):
    gmt_created: Optional[str] = Field(None, description="Dbgpts create time")
    gmt_modified: Optional[str] = Field(None, description="Dbgpts upload time")
