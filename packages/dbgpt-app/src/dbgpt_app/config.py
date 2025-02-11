from dataclasses import dataclass, field
from typing import List, Optional

from dbgpt.datasource.parameter import BaseDatasourceParameters
from dbgpt.model.parameter import (
    ModelsDeployParameters,
    ModelServiceConfig,
    ModelWorkerParameters,
)
from dbgpt.util.configure import HookConfig
from dbgpt.util.i18n_utils import _
from dbgpt.util.parameter_utils import BaseParameters
from dbgpt.util.tracer import TracerParameters
from dbgpt.util.utils import LoggingParameters


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
    light: Optional[bool] = field(
        default=False, metadata={"help": _("Run Webserver in light mode")}
    )
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
                "Database connection config, now support SQLite, OceanBase and MySQL"
            )
        },
    )
    trace: Optional[TracerParameters] = field(
        default=None,
        metadata={
            "help": _("Tracer config for web server, if None, use global tracer config")
        },
    )
    log: Optional[LoggingParameters] = field(
        default=None,
        metadata={
            "help": _(
                "Logging configuration for web server, if None, use global config"
            )
        },
    )
    disable_alembic_upgrade: Optional[bool] = field(
        default=False,
        metadata={
            "help": _(
                "Whether to disable alembic to initialize and upgrade database metadata"
            )
        },
    )
    db_ssl_verify: Optional[bool] = field(
        default=False,
        metadata={"help": _("Whether to verify the SSL certificate of the database")},
    )
    default_thread_pool_size: Optional[int] = field(
        default=None,
        metadata={
            "help": _(
                "The default thread pool size, If None, use default config of python "
                "thread pool"
            )
        },
    )
    remote_embedding: Optional[bool] = field(
        default=False,
        metadata={
            "help": _(
                "Whether to enable remote embedding models. If it is True, you need"
                " to start a embedding model through `dbgpt start worker --worker_type "
                "text2vec --model_name xxx --model_path xxx`"
            )
        },
    )
    remote_rerank: Optional[bool] = field(
        default=False,
        metadata={
            "help": _(
                "Whether to enable remote rerank models. If it is True, you need"
                " to start a rerank model through `dbgpt start worker --worker_type "
                "text2vec --rerank --model_name xxx --model_path xxx`"
            )
        },
    )
    awel_dirs: Optional[str] = field(
        default=None,
        metadata={"help": _("The directories to search awel files, split by `,`")},
    )
    new_web_ui: bool = field(
        default=True,
        metadata={"help": _("Whether to use the new web UI, default is True")},
    )


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
            "help": _("System configuration"),
        },
    )
    service: ServiceConfig = field(default_factory=ServiceConfig)
    models: ModelsDeployParameters = field(
        default_factory=ModelsDeployParameters,
        metadata={
            "help": _("Model deployment configuration"),
        },
    )
    trace: TracerParameters = field(
        default_factory=TracerParameters,
        metadata={
            "help": _("Global tracer configuration"),
        },
    )
    log: LoggingParameters = field(
        default_factory=LoggingParameters,
        metadata={
            "help": _("Logging configuration"),
        },
    )

    def generate_temp_model_worker_params(self) -> ModelWorkerParameters:
        model_name = self.models.default_llm
        model_path = self.models.default_llm
        return ModelWorkerParameters(
            model_name=model_name,
            model_path=model_path,
            host=self.service.model.worker.host,
            port=self.service.model.worker.port,
        )
