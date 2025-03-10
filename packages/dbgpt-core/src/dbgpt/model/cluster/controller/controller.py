import logging
import os
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter

from dbgpt.component import BaseComponent, ComponentType, SystemApp
from dbgpt.configs.model_config import resolve_root_path
from dbgpt.model.base import ModelInstance
from dbgpt.model.cluster.registry import EmbeddedModelRegistry, ModelRegistry
from dbgpt.model.parameter import DBModelRegistryParameters, ModelControllerParameters
from dbgpt.util.api_utils import APIMixin
from dbgpt.util.api_utils import _api_remote as api_remote
from dbgpt.util.api_utils import _sync_api_remote as sync_api_remote
from dbgpt.util.fastapi import create_app
from dbgpt.util.tracer.tracer_impl import (
    TracerParameters,
    initialize_tracer,
    root_tracer,
)
from dbgpt.util.utils import (
    LoggingParameters,
    setup_http_service_logging,
    setup_logging,
)

logger = logging.getLogger(__name__)


class BaseModelController(BaseComponent, ABC):
    name = ComponentType.MODEL_CONTROLLER

    def init_app(self, system_app: SystemApp):
        pass

    @abstractmethod
    async def register_instance(self, instance: ModelInstance) -> bool:
        """Register a given model instance"""

    @abstractmethod
    async def deregister_instance(self, instance: ModelInstance) -> bool:
        """Deregister a given model instance."""

    @abstractmethod
    async def get_all_instances(
        self, model_name: str = None, healthy_only: bool = False
    ) -> List[ModelInstance]:
        """Fetch all instances of a given model.

        Optionally, fetch only the healthy instances.
        """

    @abstractmethod
    async def send_heartbeat(self, instance: ModelInstance) -> bool:
        """Send a heartbeat for a given model instance. This can be used to verify if
        the instance is still alive and functioning."""

    async def model_apply(self) -> bool:
        raise NotImplementedError


class LocalModelController(BaseModelController):
    def __init__(self, registry: ModelRegistry) -> None:
        self.registry = registry
        self.deployment = None

    async def register_instance(self, instance: ModelInstance) -> bool:
        return await self.registry.register_instance(instance)

    async def deregister_instance(self, instance: ModelInstance) -> bool:
        return await self.registry.deregister_instance(instance)

    async def get_all_instances(
        self, model_name: str = None, healthy_only: bool = False
    ) -> List[ModelInstance]:
        logger.info(
            f"Get all instances with {model_name}, healthy_only: {healthy_only}"
        )
        if not model_name:
            return await self.registry.get_all_model_instances(
                healthy_only=healthy_only
            )
        else:
            return await self.registry.get_all_instances(model_name, healthy_only)

    async def send_heartbeat(self, instance: ModelInstance) -> bool:
        return await self.registry.send_heartbeat(instance)


class _RemoteModelController(APIMixin, BaseModelController):
    def __init__(
        self,
        urls: str,
        health_check_interval_secs: int = 5,
        health_check_timeout_secs: int = 30,
        check_health: bool = True,
        choice_type: Literal["latest_first", "random"] = "latest_first",
    ) -> None:
        APIMixin.__init__(
            self,
            urls=urls,
            health_check_path="/api/health",
            health_check_interval_secs=health_check_interval_secs,
            health_check_timeout_secs=health_check_timeout_secs,
            check_health=check_health,
            choice_type=choice_type,
        )
        BaseModelController.__init__(self)

    @api_remote(path="/api/controller/models", method="POST")
    async def register_instance(self, instance: ModelInstance) -> bool:
        pass

    @api_remote(path="/api/controller/models", method="DELETE")
    async def deregister_instance(self, instance: ModelInstance) -> bool:
        pass

    @api_remote(path="/api/controller/models")
    async def get_all_instances(
        self, model_name: str = None, healthy_only: bool = False
    ) -> List[ModelInstance]:
        pass

    @api_remote(path="/api/controller/heartbeat", method="POST")
    async def send_heartbeat(self, instance: ModelInstance) -> bool:
        pass


class ModelRegistryClient(_RemoteModelController, ModelRegistry):
    async def get_all_model_instances(
        self, healthy_only: bool = False
    ) -> List[ModelInstance]:
        return await self.get_all_instances(healthy_only=healthy_only)

    @sync_api_remote(path="/api/controller/models")
    def sync_get_all_instances(
        self, model_name: str = None, healthy_only: bool = False
    ) -> List[ModelInstance]:
        pass


class ModelControllerAdapter(BaseModelController):
    def __init__(self, backend: BaseModelController = None) -> None:
        self.backend = backend

    async def register_instance(self, instance: ModelInstance) -> bool:
        return await self.backend.register_instance(instance)

    async def deregister_instance(self, instance: ModelInstance) -> bool:
        return await self.backend.deregister_instance(instance)

    async def get_all_instances(
        self, model_name: str = None, healthy_only: bool = False
    ) -> List[ModelInstance]:
        return await self.backend.get_all_instances(model_name, healthy_only)

    async def send_heartbeat(self, instance: ModelInstance) -> bool:
        return await self.backend.send_heartbeat(instance)

    async def model_apply(self) -> bool:
        return await self.backend.model_apply()


router = APIRouter()

controller = ModelControllerAdapter()


def initialize_controller(
    app=None,
    remote_controller_addr: str = None,
    registry: Optional[ModelRegistry] = None,
    controller_params: Optional[ModelControllerParameters] = None,
    system_app: Optional[SystemApp] = None,
    trace_config: Optional[TracerParameters] = None,
):
    global controller
    if remote_controller_addr:
        controller.backend = _RemoteModelController(remote_controller_addr)
    else:
        if not registry:
            registry = EmbeddedModelRegistry()
        controller.backend = LocalModelController(registry=registry)

    if app:
        # Register the controller API to the FastAPI app.
        app.include_router(router, prefix="/api", tags=["Model Controller"])
    else:
        import uvicorn

        setup_http_service_logging()
        app = create_app()
        if not system_app:
            system_app = SystemApp(app)
        if not controller_params:
            raise ValueError("Controller parameters are required.")
        trace_config = trace_config or TracerParameters()
        trace_file = trace_config.file or os.path.join(
            "logs", "dbgpt_model_controller_tracer.jsonl"
        )
        initialize_tracer(
            trace_file,
            system_app=system_app,
            root_operation_name=trace_config.root_operation_name
            or "DB-GPT-ModelController",
            tracer_parameters=trace_config,
        )

        app.include_router(router, prefix="/api", tags=["Model Controller"])
        uvicorn.run(
            app,
            host=controller_params.host,
            port=controller_params.port,
            log_level="info",
        )


@router.get("/health")
async def api_health_check():
    """Health check API."""
    return {"status": "ok"}


@router.post("/controller/models")
async def api_register_instance(request: ModelInstance):
    with root_tracer.start_span(
        "dbgpt.model.controller.register_instance", metadata=request.to_dict()
    ):
        return await controller.register_instance(request)


@router.delete("/controller/models")
async def api_deregister_instance(
    model_name: str, host: str, port: int, remove_from_registry: bool = False
):
    instance = ModelInstance(
        model_name=model_name,
        host=host,
        port=port,
        remove_from_registry=remove_from_registry,
    )
    with root_tracer.start_span(
        "dbgpt.model.controller.deregister_instance", metadata=instance.to_dict()
    ):
        return await controller.deregister_instance(instance)


@router.get("/controller/models")
async def api_get_all_instances(model_name: str = None, healthy_only: bool = False):
    return await controller.get_all_instances(model_name, healthy_only=healthy_only)


@router.post("/controller/heartbeat")
async def api_model_heartbeat(request: ModelInstance):
    return await controller.send_heartbeat(request)


def _create_registry(controller_params: ModelControllerParameters) -> ModelRegistry:
    """Create a model registry based on the controller parameters.

    Registry will store the metadata of all model instances, it will be a high
    availability service for model instances if you use a database registry now. Also,
    we can implement more registry types in the future.
    """
    if not controller_params.registry:
        return EmbeddedModelRegistry(
            heartbeat_interval_secs=controller_params.heartbeat_interval_secs,
            heartbeat_timeout_secs=controller_params.heartbeat_timeout_secs,
        )
    elif isinstance(controller_params.registry, DBModelRegistryParameters):
        from dbgpt.datasource.rdbms.base import (
            RDBMSConnector,
            RDBMSDatasourceParameters,
        )
        from dbgpt.model.cluster.registry_impl.storage import StorageModelRegistry
        from dbgpt_ext.datasource.rdbms.conn_sqlite import SQLiteConnectorParameters

        # controller_params.registry.
        db_config = controller_params.registry.database

        if isinstance(db_config, SQLiteConnectorParameters):
            db_config.path = resolve_root_path(db_config.path)
            db_dir = os.path.dirname(db_config.path)
            os.makedirs(db_dir, exist_ok=True)
            # Parse the db name from the db path
            db_name = os.path.basename(db_config.path).split(".")[0]
        elif isinstance(db_config, RDBMSDatasourceParameters):
            db_name = db_config.database
        else:
            raise ValueError(
                "DB-GPT only support SQLite, MySQL and OceanBase database as metadata "
                "storage database"
            )
        connector = db_config.create_connector()
        if not isinstance(connector, RDBMSConnector):
            raise ValueError("Only support RDBMSConnector")
        db_url = db_config.db_url()
        db_engine_args: Optional[Dict[str, Any]] = db_config.engine_args()

        try_to_create_db = False

        registry = StorageModelRegistry.from_url(
            db_url,
            db_name,
            engine_args=db_engine_args,
            try_to_create_db=try_to_create_db,
            heartbeat_interval_secs=controller_params.heartbeat_interval_secs,
            heartbeat_timeout_secs=controller_params.heartbeat_timeout_secs,
        )
        return registry
    else:
        raise ValueError(f"Unsupported registry type: {controller_params.registry}")


def parse_args():
    import argparse

    parser = argparse.ArgumentParser(description="DB-GPT API Server")
    parser.add_argument(
        "-c",
        "--config",
        type=str,
        required=True,
        help="Path to the configuration file.",
    )
    return parser.parse_args()


def run_model_controller(config_file: str):
    from dbgpt.configs.model_config import LOGDIR, ROOT_PATH
    from dbgpt.util.configure import ConfigurationManager
    from dbgpt_serve.datasource.manages.connector_manager import ConnectorManager

    cm = ConnectorManager(None)  # noqa: F841
    # pre import all datasource
    cm.on_init()

    if not os.path.isabs(config_file) and not os.path.exists(config_file):
        config_file = os.path.join(ROOT_PATH, config_file)

    cfg = ConfigurationManager.from_file(config_file)
    controller_params = cfg.parse_config(
        ModelControllerParameters,
        prefix="service.model.controller",
        hook_section="hooks",
    )

    sys_trace: Optional[TracerParameters] = None
    sys_log: Optional[LoggingParameters] = None

    if cfg.exists("trace"):
        sys_trace = cfg.parse_config(TracerParameters, prefix="trace")
    if cfg.exists("log"):
        sys_log = cfg.parse_config(LoggingParameters, prefix="log")

    log_config = controller_params.log or sys_log or LoggingParameters()
    trace_config = controller_params.trace or sys_trace or TracerParameters()

    setup_logging(
        "dbgpt",
        log_config=log_config,
        default_logger_filename=os.path.join(LOGDIR, "dbgpt_model_controller.log"),
    )

    registry = _create_registry(controller_params)

    initialize_controller(
        registry=registry,
        controller_params=controller_params,
        trace_config=trace_config,
    )


if __name__ == "__main__":
    _args = parse_args()
    _config_file = _args.config

    run_model_controller(_config_file)
