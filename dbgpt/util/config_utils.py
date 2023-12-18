from functools import cache
from typing import Any, Dict, Optional


class AppConfig:
    def __init__(self):
        self.configs = {}

    def set(self, key: str, value: Any) -> None:
        """Set config value by key
        Args:
            key (str): The key of config
            value (Any): The value of config
        """
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
