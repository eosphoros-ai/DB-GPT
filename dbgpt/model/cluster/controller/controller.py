from abc import ABC, abstractmethod

import logging
from typing import List

from fastapi import APIRouter, FastAPI
from dbgpt.component import BaseComponent, ComponentType, SystemApp
from dbgpt.model.base import ModelInstance
from dbgpt.model.parameter import ModelControllerParameters
from dbgpt.model.cluster.registry import EmbeddedModelRegistry, ModelRegistry
from dbgpt.util.parameter_utils import EnvArgumentParser
from dbgpt.util.api_utils import (
    _api_remote as api_remote,
    _sync_api_remote as sync_api_remote,
)
from dbgpt.util.utils import setup_logging, setup_http_service_logging

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
    def __init__(self, registry: ModelRegistry = None) -> None:
        if not registry:
            registry = EmbeddedModelRegistry()
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


class _RemoteModelController(BaseModelController):
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url

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
    app=None, remote_controller_addr: str = None, host: str = None, port: int = None
):
    global controller
    if remote_controller_addr:
        controller.backend = _RemoteModelController(remote_controller_addr)
    else:
        controller.backend = LocalModelController()

    if app:
        app.include_router(router, prefix="/api", tags=["Model"])
    else:
        import uvicorn

        setup_http_service_logging()
        app = FastAPI()
        app.include_router(router, prefix="/api", tags=["Model"])
        uvicorn.run(app, host=host, port=port, log_level="info")


@router.post("/controller/models")
async def api_register_instance(request: ModelInstance):
    return await controller.register_instance(request)


@router.delete("/controller/models")
async def api_deregister_instance(model_name: str, host: str, port: int):
    instance = ModelInstance(model_name=model_name, host=host, port=port)
    return await controller.deregister_instance(instance)


@router.get("/controller/models")
async def api_get_all_instances(model_name: str = None, healthy_only: bool = False):
    return await controller.get_all_instances(model_name, healthy_only=healthy_only)


@router.post("/controller/heartbeat")
async def api_model_heartbeat(request: ModelInstance):
    return await controller.send_heartbeat(request)


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

    initialize_controller(host=controller_params.host, port=controller_params.port)


if __name__ == "__main__":
    run_model_controller()
