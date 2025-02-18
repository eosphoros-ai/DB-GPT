# Define your Pydantic schemas here
from typing import Any, Dict, Optional

from dbgpt._private.pydantic import BaseModel, ConfigDict, Field, model_to_dict

from ..config import SERVE_APP_NAME_HUMP


class ServeRequest(BaseModel):
    """Model request model"""

    # TODO define your own fields here

    model_config = ConfigDict(title=f"ServeRequest for {SERVE_APP_NAME_HUMP}")

    def to_dict(self, **kwargs) -> Dict[str, Any]:
        """Convert the model to a dictionary"""
        return model_to_dict(self, **kwargs)


class ServerResponse(BaseModel):
    """Model response model"""

    # TODO define your own fields here

    model_config = ConfigDict(title=f"ServerResponse for {SERVE_APP_NAME_HUMP}")

    def to_dict(self, **kwargs) -> Dict[str, Any]:
        """Convert the model to a dictionary"""
        return model_to_dict(self, **kwargs)


class ModelResponse(BaseModel):
    """ModelRequest"""

    """model_name: model_name"""
    model_name: str = Field(description="Model name")
    """model_type: model_type"""
    # model_type: str = None
    worker_type: str = Field(description="Worker type")
    """host: host"""
    host: str = Field(description="Host of the model")
    """port: port"""
    port: int = Field(description="Port of the model")
    """manager_host: manager_host"""
    manager_host: str = Field(description="Model worker manager host")
    """manager_port: manager_port"""
    manager_port: int = Field(description="Model worker manager port")
    """healthy: healthy"""
    healthy: bool = Field(True, description="Model health status")

    """check_healthy: check_healthy"""
    check_healthy: bool = Field(True, description="Check model health status")
    prompt_template: Optional[str] = Field(None, description="Model prompt template")
    last_heartbeat: Optional[str] = Field(None, description="Model last heartbeat")
