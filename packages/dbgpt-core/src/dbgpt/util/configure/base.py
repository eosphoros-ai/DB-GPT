"""Configuration base module."""

import logging
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Optional, Union

logger = logging.getLogger(__name__)


class _MISSING_TYPE:
    pass


_MISSING = _MISSING_TYPE()


class ConfigCategory(str, Enum):
    """The configuration category."""

    AGENT = "agent"


class ProviderType(str, Enum):
    """The provider type."""

    ENV = "env"
    PROMPT_MANAGER = "prompt_manager"


class ConfigProvider(ABC):
    """The configuration provider."""

    name: ProviderType

    @abstractmethod
    def query(self, key: str, **kwargs) -> Any:
        """Query the configuration value by key."""


class EnvironmentConfigProvider(ConfigProvider):
    """Environment configuration provider.

    Obtain the configuration value from the environment variable.
    """

    name: ProviderType = ProviderType.ENV

    def query(self, key: str, **kwargs) -> Any:
        import os

        return os.environ.get(key, None)


class PromptManagerConfigProvider(ConfigProvider):
    """Prompt manager configuration provider.

    Obtain the configuration value from the prompt manager.

    It is valid only when DB-GPT web server is running for now.
    """

    name: ProviderType = ProviderType.PROMPT_MANAGER

    def query(self, key: str, **kwargs) -> Any:
        from dbgpt._private.config import Config

        try:
            from dbgpt_serve.prompt.serve import Serve
        except ImportError:
            logger.debug("Prompt manager is not available.")
            return None

        cfg = Config()
        sys_app = cfg.SYSTEM_APP
        if not sys_app:
            return None
        prompt_serve = Serve.get_instance(sys_app)
        if not prompt_serve or not prompt_serve.prompt_manager:
            return None
        prompt_manager = prompt_serve.prompt_manager
        value = prompt_manager.prefer_query(key, **kwargs)
        if not value:
            return None
        # Just return the first value
        return value[0].to_prompt_template().template


class ConfigInfo:
    def __init__(
        self,
        default: Any,
        key: Optional[str] = None,
        provider: Optional[Union[str, ConfigProvider]] = None,
        is_list: bool = False,
        separator: str = "[LIST_SEP]",
        description: Optional[str] = None,
    ):
        self.default = default
        self.key = key
        self.provider = provider
        self.is_list = is_list
        self.separator = separator
        self.description = description

    def query(self, **kwargs) -> Any:
        if self.key is None:
            return self.default
        value: Any = None
        if isinstance(self.provider, ConfigProvider):
            value = self.provider.query(self.key, **kwargs)
        elif self.provider == ProviderType.ENV:
            value = EnvironmentConfigProvider().query(self.key, **kwargs)
        elif self.provider == ProviderType.PROMPT_MANAGER:
            value = PromptManagerConfigProvider().query(self.key, **kwargs)
        if value is None:
            value = self.default
        if value and self.is_list and isinstance(value, str):
            value = value.split(self.separator)
        return value


def DynConfig(
    default: Any = _MISSING,
    *,
    category: str | ConfigCategory | None = None,
    key: str | None = None,
    provider: str | ProviderType | ConfigProvider | None = None,
    is_list: bool = False,
    separator: str = "[LIST_SEP]",
    description: str | None = None,
) -> Any:
    """Dynamic configuration.

    It allows to query the configuration value dynamically.
    It can obtain the configuration value from the specified provider.

    **Note**: Now just support obtaining string value or string list value.

    Args:
        default (Any): The default value.
        category (str | ConfigCategory | None): The configuration category.
        key (str | None): The configuration key.
        provider (str | ProviderType | ConfigProvider | None): The configuration
            provider.
        is_list (bool): Whether the value is a list.
        separator (str): The separator to split the list value.
        description (str | None): The configuration description.
    """
    if provider is None and category == ConfigCategory.AGENT:
        provider = ProviderType.PROMPT_MANAGER
    if default == _MISSING and key is None:
        raise ValueError("Default value or key is required.")
    if default != _MISSING and isinstance(default, list):
        is_list = True
    return ConfigInfo(
        default=default,
        key=key,
        provider=provider,
        is_list=is_list,
        separator=separator,
        description=description,
    )
