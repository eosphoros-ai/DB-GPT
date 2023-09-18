
from fastapi import APIRouter

from pilot.componet import ComponetType
from pilot.configs.config import Config
from pilot.model.base import ModelInstance, WorkerApplyType

from pilot.model.cluster import WorkerStartupRequest
from pilot.openapi.api_view_model import Result

from pilot.server.llm_manage.request.request import ModelResponse

CFG = Config()
router = APIRouter()


@router.post("/controller/list")
async def controller_list(request: ModelInstance):
    print(f"/controller/list params:")
    try:
        CFG.LLM_MODEL = request.model_name
        return Result.succ("success")

    except Exception as e:
        return Result.faild(code="E000X", msg=f"space list error {e}")


@router.get("/v1/worker/model/list")
async def model_list():
    print(f"/worker/model/list")
    try:
        from pilot.model.cluster.controller.controller import BaseModelController

        controller = CFG.SYSTEM_APP.get_componet(
            ComponetType.MODEL_CONTROLLER, BaseModelController
        )
        responses = []
        managers = await controller.get_all_instances(
            model_name="WorkerManager@service", healthy_only=True
        )
        manager_map = dict(map(lambda manager: (manager.host, manager), managers))
        models = await controller.get_all_instances()
        for model in models:
            worker_name, worker_type = model.model_name.split("@")
            if worker_type == "llm" or worker_type == "text2vec":
                response = ModelResponse(
                    model_name=worker_name,
                    model_type=worker_type,
                    host=model.host,
                    port=model.port,
                    healthy=model.healthy,
                    check_healthy=model.check_healthy,
                    last_heartbeat=model.last_heartbeat,
                    prompt_template=model.prompt_template,
                )
                response.manager_host = model.host if manager_map[model.host] else None
                response.manager_port = (
                    manager_map[model.host].port if manager_map[model.host] else None
                )
                responses.append(response)
        return Result.succ(responses)

    except Exception as e:
        return Result.faild(code="E000X", msg=f"space list error {e}")


@router.post("/v1/worker/model/stop")
async def model_start(request: WorkerStartupRequest):
    print(f"/v1/worker/model/stop:")
    try:
        from pilot.model.cluster.controller.controller import BaseModelController

        controller = CFG.SYSTEM_APP.get_componet(
            ComponetType.MODEL_CONTROLLER, BaseModelController
        )
        instances = await controller.get_all_instances(model_name="WorkerManager@service", healthy_only=True)
        worker_instance = None
        for instance in instances:
            if (
                instance.host == request.host
                and instance.port == request.port
            ):
                from pilot.model.cluster import ModelRegistryClient
                from pilot.model.cluster import RemoteWorkerManager

                registry = ModelRegistryClient(f"http://{request.host}:{request.port}")
                worker_manager = RemoteWorkerManager(registry)
                return Result.succ(await worker_manager.model_shutdown(request))
        if not worker_instance:
            return Result.faild(code="E000X", msg=f"can not find worker manager")
    except Exception as e:
        return Result.faild(code="E000X", msg=f"model stop failed {e}")


@router.post("/v1/worker/model/start")
async def model_start(request: WorkerStartupRequest):
    print(f"/v1/worker/model/start:")
    try:
        from pilot.model.cluster.controller.controller import BaseModelController

        controller = CFG.SYSTEM_APP.get_componet(
            ComponetType.MODEL_CONTROLLER, BaseModelController
        )
        instances = await controller.get_all_instances(model_name="WorkerManager@service", healthy_only=True)
        worker_instance = None
        for instance in instances:
            if (
                instance.host == request.host
                and instance.port == request.port
            ):
                from pilot.model.cluster import ModelRegistryClient
                from pilot.model.cluster import RemoteWorkerManager

                registry = ModelRegistryClient(f"http://{request.host}:{request.port}")
                worker_manager = RemoteWorkerManager(registry)
                return Result.succ(await worker_manager.model_startup(request))
        if not worker_instance:
            return Result.faild(code="E000X", msg=f"can not find worker manager")
    except Exception as e:
        return Result.faild(code="E000X", msg=f"model start failed {e}")
