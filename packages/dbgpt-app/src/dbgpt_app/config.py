from dataclasses import dataclass, field
from typing import List, Optional

from dbgpt.datasource.parameter import BaseDatasourceParameters
from dbgpt.util.configure import HookConfig
from dbgpt.util.i18n_utils import _
from dbgpt.util.parameter_utils import BaseParameters, BaseServerParameters


@dataclass
class SystemParameters:
    """System parameters."""

    language: str = field(
        default="en",
        metadata={
            "help": _("Language setting"),
            "valid_values": ["en", "zh", "fr", "ja", "ko", "ru"],
        },
    )
    log_level: str = field(
        default="INFO",
        metadata={
            "help": _("Logging level"),
            "valid_values": ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        },
    )
    api_keys: List[str] = field(
        default_factory=list,
        metadata={
            "help": _("API keys"),
        },
    )


@dataclass
class ServiceWebParameters(BaseParameters):
    host: str = field(default="0.0.0.0", metadata={"help": _("Webserver deploy host")})
    port: int = field(
        default=5670, metadata={"help": _("Webserver deploy port, default is 5670")}
    )
    # daemon: Optional[bool] = field(
    #     default=False, metadata={"help": "Run Webserver in background"}
    # )
    controller_addr: Optional[str] = field(
        default=None,
        metadata={
            "help": _(
                "The Model controller address to connect. If None, read model "
                "controller address from environment key `MODEL_SERVER`."
            )
        },
    )
    database: BaseDatasourceParameters = field(
        default_factory=BaseDatasourceParameters,
        metadata={
            "help": _(
                "Database connection parameters, now support SQLite, OceanBase "
                "and MySQL"
            )
        },
    )


@dataclass
class ModelServiceConfig(BaseParameters):
    """Model service configuration."""

    controller: BaseServerParameters = field(metadata={"help": _("Model controller")})
    worker: BaseServerParameters = field(metadata={"help": _("Model worker")})
    api: BaseServerParameters = field(metadata={"help": _("Model API")})


@dataclass
class ServiceConfig(BaseParameters):
    web: ServiceWebParameters
    model: ModelServiceConfig


@dataclass
class ApplicationConfig:
    """Application configuration."""

    hooks: List[HookConfig] = field(
        default_factory=list,
        metadata={
            "help": _(
                "Configuration hooks, which will be executed before the configuration "
                "loading"
            ),
        },
    )

    system: SystemParameters = field(
        default_factory=SystemParameters,
        metadata={
            "help": _("System parameters"),
        },
    )
    service: ServiceConfig = field(default_factory=ServiceConfig)


if __name__ == "__main__":
    import os

    from dbgpt.configs.model_config import ROOT_PATH
    from dbgpt.util.configure import ConfigurationManager
    from dbgpt_serve.datasource.manages.connector_manager import ConnectorManager

    cm = ConnectorManager(None)
    cm.on_init()
    cfg = ConfigurationManager.from_file(
        os.path.join(ROOT_PATH, "configs", "dbgpt-default.toml")
    )
    app_config = cfg.parse_config(ApplicationConfig, hook_section="hooks")
    print(app_config)
