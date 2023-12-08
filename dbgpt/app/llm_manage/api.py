from fastapi import APIRouter

from dbgpt.component import ComponentType
from dbgpt._private.config import Config

from dbgpt.model.cluster import WorkerStartupRequest, WorkerManagerFactory
from dbgpt.app.openapi.api_view_model import Result

from dbgpt.app.llm_manage.request.request import ModelResponse

CFG = Config()
router = APIRouter()


@router.get("/v1/worker/model/params")
async def model_params():
    print(f"/worker/model/params")
    try:
        from dbgpt.model.cluster import WorkerManagerFactory

        worker_manager = CFG.SYSTEM_APP.get_component(
            ComponentType.WORKER_MANAGER_FACTORY, WorkerManagerFactory
        ).create()
        params = []
        workers = await worker_manager.supported_models()
        for worker in workers:
            for model in worker.models:
                model_dict = model.__dict__
                model_dict["host"] = worker.host
                model_dict["port"] = worker.port
                params.append(model_dict)
        return Result.succ(params)
        if not worker_instance:
            return Result.failed(code="E000X", msg=f"can not find worker manager")
    except Exception as e:
        return Result.failed(code="E000X", msg=f"model stop failed {e}")


@router.get("/v1/worker/model/list")
async def model_list():
    print(f"/worker/model/list")
    try:
        from dbgpt.model.cluster.controller.controller import BaseModelController

        controller = CFG.SYSTEM_APP.get_component(
            ComponentType.MODEL_CONTROLLER, BaseModelController
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
                response.manager_host = (
                    model.host if manager_map.get(model.host) else None
                )
                response.manager_port = (
                    manager_map[model.host].port
                    if manager_map.get(model.host)
                    else None
                )
                responses.append(response)
        return Result.succ(responses)

    except Exception as e:
        return Result.failed(code="E000X", msg=f"model list error {e}")


@router.post("/v1/worker/model/stop")
async def model_stop(request: WorkerStartupRequest):
    print(f"/v1/worker/model/stop:")
    try:
        from dbgpt.model.cluster.controller.controller import BaseModelController

        worker_manager = CFG.SYSTEM_APP.get_component(
            ComponentType.WORKER_MANAGER_FACTORY, WorkerManagerFactory
        ).create()
        if not worker_manager:
            return Result.failed(code="E000X", msg=f"can not find worker manager")
        request.params = {}
        return Result.succ(await worker_manager.model_shutdown(request))
    except Exception as e:
        return Result.failed(code="E000X", msg=f"model stop failed {e}")


@router.post("/v1/worker/model/start")
async def model_start(request: WorkerStartupRequest):
    print(f"/v1/worker/model/start:")
    try:
        worker_manager = CFG.SYSTEM_APP.get_component(
            ComponentType.WORKER_MANAGER_FACTORY, WorkerManagerFactory
        ).create()
        if not worker_manager:
            return Result.failed(code="E000X", msg=f"can not find worker manager")
        return Result.succ(await worker_manager.model_startup(request))
    except Exception as e:
        return Result.failed(code="E000X", msg=f"model start failed {e}")
