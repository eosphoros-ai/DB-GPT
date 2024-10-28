# Define your Pydantic schemas here
from typing import Any, Dict, List, Optional

from dbgpt._private.pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_to_dict,
    model_validator,
)

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


class _BucketFilePair(BaseModel):
    """Bucket file pair model"""

    bucket: str = Field(..., title="The bucket of the file")
    file_id: str = Field(..., title="The ID of the file")


class FileMetadataBatchRequest(BaseModel):
    """File metadata batch request model"""

    uris: Optional[List[str]] = Field(None, title="The URIs of the files")
    bucket_file_pairs: Optional[List[_BucketFilePair]] = Field(
        None, title="The bucket file pairs"
    )

    @model_validator(mode="after")
    def check_uris_or_bucket_file_pairs(self):
        # Check if either uris or bucket_file_pairs is provided
        if not (self.uris or self.bucket_file_pairs):
            raise ValueError("Either uris or bucket_file_pairs must be provided")
        # Check only one of uris or bucket_file_pairs is provided
        if self.uris and self.bucket_file_pairs:
            raise ValueError("Only one of uris or bucket_file_pairs can be provided")
        return self


class FileMetadataResponse(BaseModel):
    """File metadata model"""

    file_name: str = Field(..., title="The name of the file")
    file_id: str = Field(..., title="The ID of the file")
    bucket: str = Field(..., title="The bucket of the file")
    uri: str = Field(..., title="The URI of the file")
    file_size: int = Field(..., title="The size of the file")
    user_name: Optional[str] = Field(None, title="The user name")
    sys_code: Optional[str] = Field(None, title="The system code")
