import logging
from typing import List

from fastapi import APIRouter, FastAPI
from pilot.model.base import ModelInstance
from pilot.model.parameter import ModelControllerParameters
from pilot.model.controller.registry import EmbeddedModelRegistry, ModelRegistry
from pilot.utils.parameter_utils import EnvArgumentParser


class ModelController:
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
        self, model_name: str, healthy_only: bool = False
    ) -> List[ModelInstance]:
        logging.info(
            f"Get all instances with {model_name}, healthy_only: {healthy_only}"
        )
        return await self.registry.get_all_instances(model_name, healthy_only)

    async def get_all_model_instances(self) -> List[ModelInstance]:
        return await self.registry.get_all_model_instances()

    async def send_heartbeat(self, instance: ModelInstance) -> bool:
        return await self.registry.send_heartbeat(instance)

    async def model_apply(self) -> bool:
        # TODO
        raise NotImplementedError


router = APIRouter()

controller = ModelController()


@router.post("/controller/models")
async def api_register_instance(request: ModelInstance):
    return await controller.register_instance(request)


@router.delete("/controller/models")
async def api_deregister_instance(request: ModelInstance):
    return await controller.deregister_instance(request)


@router.get("/controller/models")
async def api_get_all_instances(model_name: str = None, healthy_only: bool = False):
    if not model_name:
        return await controller.get_all_model_instances()
    return await controller.get_all_instances(model_name, healthy_only=healthy_only)


@router.post("/controller/heartbeat")
async def api_model_heartbeat(request: ModelInstance):
    return await controller.send_heartbeat(request)


def run_model_controller():
    import uvicorn

    parser = EnvArgumentParser()
    env_prefix = "controller_"
    controller_params: ModelControllerParameters = parser.parse_args_into_dataclass(
        ModelControllerParameters, env_prefix=env_prefix
    )
    app = FastAPI()
    app.include_router(router, prefix="/api")
    uvicorn.run(
        app, host=controller_params.host, port=controller_params.port, log_level="info"
    )


if __name__ == "__main__":
    run_model_controller()
