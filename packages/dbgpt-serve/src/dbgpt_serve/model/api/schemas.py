# Define your Pydantic schemas here
from typing import Any, Dict, List, Optional

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


class ProviderConfigRequest(BaseModel):
    """Request body for saving a provider-level configuration."""

    provider: str = Field(description="The provider id, e.g. proxy/openai")
    api_key: Optional[str] = Field(None, description="The API key of the provider")
    api_base: Optional[str] = Field(
        None, description="The API base url of the provider"
    )


class ProviderModelsRequest(BaseModel):
    """Request body for saving the enabled models of a provider."""

    provider: str = Field(description="The provider id, e.g. proxy/openai")
    enabled_models: List[str] = Field(
        default_factory=list, description="The enabled model names under the provider"
    )


class ProviderModelRequest(BaseModel):
    """Request body for enabling/disabling a single model under a provider."""

    provider: str = Field(description="The provider id, e.g. proxy/openai")
    model: str = Field(description="The model name to enable or disable")


class ProviderRequest(BaseModel):
    """Request body carrying only a provider id."""

    provider: str = Field(description="The provider id, e.g. proxy/openai")


class ProviderCustomRequest(BaseModel):
    """Request body for creating a custom (OpenAI-compatible) provider."""

    label: str = Field(description="The display name of the custom provider")
    api_base: str = Field(description="The OpenAI-compatible API base url")
    api_key: str = Field(description="The API key of the custom provider")
    models: List[str] = Field(
        default_factory=list, description="The model names exposed by the provider"
    )
