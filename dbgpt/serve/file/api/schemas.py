# Define your Pydantic schemas here
from typing import Any, Dict

from dbgpt._private.pydantic import BaseModel, ConfigDict, Field, model_to_dict

from ..config import SERVE_APP_NAME_HUMP


class ServeRequest(BaseModel):
    """File request model"""

    # TODO define your own fields here

    model_config = ConfigDict(title=f"ServeRequest for {SERVE_APP_NAME_HUMP}")

    def to_dict(self, **kwargs) -> Dict[str, Any]:
        """Convert the model to a dictionary"""
        return model_to_dict(self, **kwargs)


class ServerResponse(BaseModel):
    """File response model"""

    # TODO define your own fields here

    model_config = ConfigDict(title=f"ServerResponse for {SERVE_APP_NAME_HUMP}")

    def to_dict(self, **kwargs) -> Dict[str, Any]:
        """Convert the model to a dictionary"""
        return model_to_dict(self, **kwargs)


class UploadFileResponse(BaseModel):
    """Upload file response model"""

    file_name: str = Field(..., title="The name of the uploaded file")
    file_id: str = Field(..., title="The ID of the uploaded file")
    bucket: str = Field(..., title="The bucket of the uploaded file")
    uri: str = Field(..., title="The URI of the uploaded file")

    def to_dict(self, **kwargs) -> Dict[str, Any]:
        """Convert the model to a dictionary"""
        return model_to_dict(self, **kwargs)
