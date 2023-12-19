from dataclasses import dataclass
from dbgpt.component import AppConfig
from dbgpt.util import BaseParameters


@dataclass
class BaseServeConfig(BaseParameters):
    """Base configuration class for serve"""

    @classmethod
    def from_app_config(cls, config: AppConfig, config_prefix: str):
        """Create a configuration object from a dictionary

        Args:
            config (AppConfig): Application configuration
            config_prefix (str): Configuration prefix
        """
        config_dict = config.get_all_by_prefix(config_prefix)
        return cls(**config_dict)
