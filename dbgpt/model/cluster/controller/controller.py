import logging
import os
from abc import ABC, abstractmethod
from typing import List, Literal, Optional

from fastapi import APIRouter

from dbgpt.component import BaseComponent, ComponentType, SystemApp
from dbgpt.model.base import ModelInstance
from dbgpt.model.cluster.registry import EmbeddedModelRegistry, ModelRegistry
from dbgpt.model.parameter import ModelControllerParameters
from dbgpt.util.api_utils import APIMixin
from dbgpt.util.api_utils import _api_remote as api_remote
from dbgpt.util.api_utils import _sync_api_remote as sync_api_remote
from dbgpt.util.fastapi import create_app
from dbgpt.util.parameter_utils import EnvArgumentParser
from dbgpt.util.tracer.tracer_impl import initialize_tracer, root_tracer
from dbgpt.util.utils import setup_http_service_logging, setup_logging

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
        """Fetch all instances of a given model. Optionally, fetch only the healthy instances."""

    @abstractmethod
    async def send_heartbeat(self, instance: ModelInstance) -> bool:
        """Send a heartbeat for a given model instance. This can be used to verify if the instance is still alive and functioning."""

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
    host: str = None,
    port: int = None,
    registry: Optional[ModelRegistry] = None,
    controller_params: Optional[ModelControllerParameters] = None,
    system_app: Optional[SystemApp] = None,
):

    global controller
    if remote_controller_addr:
        controller.backend = _RemoteModelController(remote_controller_addr)
    else:
        if not registry:
            registry = EmbeddedModelRegistry()
        controller.backend = LocalModelController(registry=registry)

    if app:
        app.include_router(router, prefix="/api", tags=["Model"])
    else:
        import uvicorn

        from dbgpt.configs.model_config import LOGDIR

        setup_http_service_logging()
        app = create_app()
        if not system_app:
            system_app = SystemApp(app)
        if not controller_params:
            raise ValueError("Controller parameters are required.")
        initialize_tracer(
            os.path.join(LOGDIR, controller_params.tracer_file),
            root_operation_name="DB-GPT-ModelController",
            system_app=system_app,
            tracer_storage_cls=controller_params.tracer_storage_cls,
            enable_open_telemetry=controller_params.tracer_to_open_telemetry,
            otlp_endpoint=controller_params.otel_exporter_otlp_traces_endpoint,
            otlp_insecure=controller_params.otel_exporter_otlp_traces_insecure,
            otlp_timeout=controller_params.otel_exporter_otlp_traces_timeout,
        )

        app.include_router(router, prefix="/api", tags=["Model"])
        uvicorn.run(app, host=host, port=port, log_level="info")


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
async def api_deregister_instance(model_name: str, host: str, port: int):
    instance = ModelInstance(model_name=model_name, host=host, port=port)
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
    registry_type = controller_params.registry_type.strip()
    if controller_params.registry_type == "embedded":
        return EmbeddedModelRegistry(
            heartbeat_interval_secs=controller_params.heartbeat_interval_secs,
            heartbeat_timeout_secs=controller_params.heartbeat_timeout_secs,
        )
    elif controller_params.registry_type == "database":
        from urllib.parse import quote
        from urllib.parse import quote_plus as urlquote

        from dbgpt.model.cluster.registry_impl.storage import StorageModelRegistry

        try_to_create_db = False

        if controller_params.registry_db_type == "mysql":
            db_name = controller_params.registry_db_name
            db_host = controller_params.registry_db_host
            db_port = controller_params.registry_db_port
            db_user = controller_params.registry_db_user
            db_password = controller_params.registry_db_password
            if not db_name:
                raise ValueError(
                    "Registry DB name is required when using MySQL registry."
                )
            if not db_host:
                raise ValueError(
                    "Registry DB host is required when using MySQL registry."
                )
            if not db_port:
                raise ValueError(
                    "Registry DB port is required when using MySQL registry."
                )
            if not db_user:
                raise ValueError(
                    "Registry DB user is required when using MySQL registry."
                )
            if not db_password:
                raise ValueError(
                    "Registry DB password is required when using MySQL registry."
                )
            db_url = (
                f"mysql+pymysql://{quote(db_user)}:"
                f"{urlquote(db_password)}@"
                f"{db_host}:"
                f"{str(db_port)}/"
                f"{db_name}?charset=utf8mb4"
            )
        elif controller_params.registry_db_type == "sqlite":
            db_name = controller_params.registry_db_name
            if not db_name:
                raise ValueError(
                    "Registry DB name is required when using SQLite registry."
                )
            db_url = f"sqlite:///{db_name}"
            try_to_create_db = True
        else:
            raise ValueError(
                f"Unsupported registry DB type: {controller_params.registry_db_type}"
            )

        registry = StorageModelRegistry.from_url(
            db_url,
            db_name,
            pool_size=controller_params.registry_db_pool_size,
            max_overflow=controller_params.registry_db_max_overflow,
            try_to_create_db=try_to_create_db,
            heartbeat_interval_secs=controller_params.heartbeat_interval_secs,
            heartbeat_timeout_secs=controller_params.heartbeat_timeout_secs,
        )
        return registry
    else:
        raise ValueError(f"Unsupported registry type: {registry_type}")


def run_model_controller():
    parser = EnvArgumentParser()
    env_prefix = "controller_"
    controller_params: ModelControllerParameters = parser.parse_args_into_dataclass(
        ModelControllerParameters,
        env_prefixes=[env_prefix],
    )

    setup_logging(
        "dbgpt",
        logging_level=controller_params.log_level,
        logger_filename=controller_params.log_file,
    )
    registry = _create_registry(controller_params)

    initialize_controller(
        host=controller_params.host,
        port=controller_params.port,
        registry=registry,
        controller_params=controller_params,
    )


if __name__ == "__main__":
    run_model_controller()
