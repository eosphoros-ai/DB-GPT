import os
from functools import cache
from typing import Any, Dict, Optional, cast


class AppConfig:
    def __init__(self, configs: Optional[Dict[str, Any]] = None) -> None:
        self.configs = configs or {}

    def set(self, key: str, value: Any, overwrite: bool = False) -> None:
        """Set config value by key
        Args:
            key (str): The key of config
            value (Any): The value of config
            overwrite (bool, optional): Whether to overwrite the value if key exists. Defaults to False.
        """
        if key in self.configs and not overwrite:
            raise KeyError(f"Config key {key} already exists")
        self.configs[key] = value

    def get(self, key, default: Optional[Any] = None) -> Any:
        """Get config value by key

        Args:
            key (str): The key of config
            default (Optional[Any], optional): The default value if key not found. Defaults to None.
        """
        return self.configs.get(key, default)

    @cache
    def get_all_by_prefix(self, prefix) -> Dict[str, Any]:
        """Get all config values by prefix
        Args:
            prefix (str): The prefix of config
        """
        return {k: v for k, v in self.configs.items() if k.startswith(prefix)}

    def get_current_lang(self, default: Optional[str] = None) -> str:
        """Get current language

        Args:
            default (Optional[str], optional): The default language if not found. Defaults to None.

        Returns:
            str: The language of user running environment
        """
        env_lang = (
            "zh"
            if os.getenv("LANG") and cast(str, os.getenv("LANG")).startswith("zh")
            else default
        )
        return self.get("dbgpt.app.global.language", env_lang)
