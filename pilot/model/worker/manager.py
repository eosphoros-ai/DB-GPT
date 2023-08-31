import asyncio
import httpx
import itertools
import json
import os
import random
import time
from abc import ABC, abstractmethod
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Awaitable, Callable, Dict, Iterator, List, Optional

import uvicorn
from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import StreamingResponse
from pilot.configs.model_config import LOGDIR
from pilot.model.base import (
    ModelInstance,
    ModelOutput,
    WorkerApplyType,
    WorkerApplyOutput,
)
from pilot.model.controller.registry import ModelRegistry
from pilot.model.parameter import (
    ModelParameters,
    ModelWorkerParameters,
    WorkerType,
)
from pilot.model.worker.base import ModelWorker
from pilot.scene.base_message import ModelMessage
from pilot.utils import build_logger
from pilot.utils.parameter_utils import EnvArgumentParser, ParameterDescription
from pydantic import BaseModel

logger = build_logger("model_worker", LOGDIR + "/model_worker.log")


class PromptRequest(BaseModel):
    messages: List[ModelMessage]
    model: str
    prompt: str = None
    temperature: float = None
    max_new_tokens: int = None
    stop: str = None
    echo: bool = True


class EmbeddingsRequest(BaseModel):
    model: str
    input: List[str]


class WorkerApplyRequest(BaseModel):
    model: str
    apply_type: WorkerApplyType
    worker_type: WorkerType = WorkerType.LLM
    params: Dict = None
    apply_user: str = None


class WorkerParameterRequest(BaseModel):
    model: str
    worker_type: WorkerType = WorkerType.LLM


@dataclass
class WorkerRunData:
    worker_key: str
    worker: ModelWorker
    worker_params: ModelWorkerParameters
    model_params: ModelParameters
    stop_event: asyncio.Event
    semaphore: asyncio.Semaphore = None
    command_args: List[str] = None
    _heartbeat_future: Optional[Future] = None
    _last_heartbeat: Optional[datetime] = None


RegisterFunc = Callable[[WorkerRunData], Awaitable[None]]
DeregisterFunc = Callable[[WorkerRunData], Awaitable[None]]
SendHeartbeatFunc = Callable[[WorkerRunData], Awaitable[None]]
ApplyFunction = Callable[[WorkerRunData], Awaitable[None]]


class WorkerManager(ABC):
    @abstractmethod
    async def get_model_instances(
        self, worker_type: str, model_name: str, healthy_only: bool = True
    ) -> List[WorkerRunData]:
        """Get model instances by worker type and model name"""

    @abstractmethod
    async def select_one_instanes(
        self, worker_type: str, model_name: str, healthy_only: bool = True
    ) -> WorkerRunData:
        """Select one instances"""

    @abstractmethod
    async def generate_stream(self, params: Dict, **kwargs) -> Iterator[ModelOutput]:
        """Generate stream result, chat scene"""

    @abstractmethod
    async def generate(self, params: Dict) -> ModelOutput:
        """Generate non stream result"""

    @abstractmethod
    async def embeddings(self, params: Dict) -> List[List[float]]:
        """Embed input"""

    @abstractmethod
    async def worker_apply(self, apply_req: WorkerApplyRequest) -> WorkerApplyOutput:
        """Worker apply"""

    @abstractmethod
    async def parameter_descriptions(
        self, worker_type: str, model_name: str
    ) -> List[ParameterDescription]:
        """Get parameter descriptions of model"""


async def _async_heartbeat_sender(
    worker_run_data: WorkerRunData, send_heartbeat_func: SendHeartbeatFunc
):
    while not worker_run_data.stop_event.is_set():
        try:
            await send_heartbeat_func(worker_run_data)
        except Exception as e:
            logger.warn(f"Send heartbeat func error: {str(e)}")
        finally:
            await asyncio.sleep(worker_run_data.worker_params.heartbeat_interval)


class LocalWorkerManager(WorkerManager):
    def __init__(
        self,
        register_func: RegisterFunc = None,
        deregister_func: DeregisterFunc = None,
        send_heartbeat_func: SendHeartbeatFunc = None,
        model_registry: ModelRegistry = None,
    ) -> None:
        self.workers: Dict[str, List[WorkerRunData]] = dict()
        self.executor = ThreadPoolExecutor(max_workers=os.cpu_count() * 5)
        self.register_func = register_func
        self.deregister_func = deregister_func
        self.send_heartbeat_func = send_heartbeat_func
        self.model_registry = model_registry

    def _worker_key(self, worker_type: str, model_name: str) -> str:
        if isinstance(worker_type, WorkerType):
            worker_type = worker_type.value
        return f"{model_name}@{worker_type}"

    def add_worker(
        self,
        worker: ModelWorker,
        worker_params: ModelWorkerParameters,
        embedded_mod: bool = True,
        command_args: List[str] = None,
    ):
        if not command_args:
            import sys

            command_args = sys.argv[1:]
        worker.load_worker(**asdict(worker_params))

        if not worker_params.worker_type:
            worker_params.worker_type = worker.worker_type()

        if isinstance(worker_params.worker_type, WorkerType):
            worker_params.worker_type = worker_params.worker_type.value

        worker_key = self._worker_key(
            worker_params.worker_type, worker_params.model_name
        )
        host = worker_params.host
        port = worker_params.port

        instances = self.workers.get(worker_key)
        if not instances:
            instances = []
            self.workers[worker_key] = instances
            logger.info(f"Init empty instances list for {worker_key}")
        # Load model params from persist storage
        model_params = worker.parse_parameters(command_args=command_args)

        worker_run_data = WorkerRunData(
            worker_key=worker_key,
            worker=worker,
            worker_params=worker_params,
            model_params=model_params,
            stop_event=asyncio.Event(),
            semaphore=asyncio.Semaphore(worker_params.limit_model_concurrency),
            command_args=command_args,
        )
        if not embedded_mod:
            exist_instances = [
                (w, p) for w, p in instances if p.host == host and p.port == port
            ]
            if not exist_instances:
                instances.append(worker_run_data)
        else:
            instances.append(worker_run_data)

    async def get_model_instances(
        self, worker_type: str, model_name: str, healthy_only: bool = True
    ) -> List[WorkerRunData]:
        worker_key = self._worker_key(worker_type, model_name)
        return self.workers.get(worker_key)

    async def select_one_instanes(
        self, worker_type: str, model_name: str, healthy_only: bool = True
    ) -> WorkerRunData:
        worker_instances = await self.get_model_instances(
            worker_type, model_name, healthy_only
        )
        if not worker_instances:
            raise Exception(
                f"Cound not found worker instances for model name {model_name} and worker type {worker_type}"
            )
        worker_run_data = random.choice(worker_instances)
        return worker_run_data

    async def _get_model(self, params: Dict, worker_type: str = "llm") -> WorkerRunData:
        model = params.get("model")
        if not model:
            raise Exception("Model name count not be empty")
        return await self.select_one_instanes(worker_type, model, healthy_only=True)

    async def generate_stream(
        self, params: Dict, async_wrapper=None, **kwargs
    ) -> Iterator[ModelOutput]:
        """Generate stream result, chat scene"""
        worker_run_data = await self._get_model(params)
        async with worker_run_data.semaphore:
            if worker_run_data.worker.support_async():
                async for outout in worker_run_data.worker.async_generate_stream(
                    params
                ):
                    yield outout
            else:
                if not async_wrapper:
                    from starlette.concurrency import iterate_in_threadpool

                    async_wrapper = iterate_in_threadpool
                async for output in async_wrapper(
                    worker_run_data.worker.generate_stream(params)
                ):
                    yield output

    async def generate(self, params: Dict) -> ModelOutput:
        """Generate non stream result"""
        worker_run_data = await self._get_model(params)
        async with worker_run_data.semaphore:
            if worker_run_data.worker.support_async():
                return await worker_run_data.worker.async_generate(params)
            else:
                loop = asyncio.get_event_loop()
                return await loop.run_in_executor(
                    self.executor, worker_run_data.worker.generate, params
                )

    async def embeddings(self, params: Dict) -> List[List[float]]:
        """Embed input"""
        worker_run_data = await self._get_model(params, worker_type="text2vec")
        async with worker_run_data.semaphore:
            if worker_run_data.worker.support_async():
                return await worker_run_data.worker.async_embeddings(params)
            else:
                loop = asyncio.get_event_loop()
                return await loop.run_in_executor(
                    self.executor, worker_run_data.worker.embeddings, params
                )

    async def worker_apply(self, apply_req: WorkerApplyRequest) -> WorkerApplyOutput:
        apply_func: Callable[[WorkerApplyRequest], Awaitable[str]] = None
        if apply_req.apply_type == WorkerApplyType.START:
            apply_func = self._start_all_worker
        elif apply_req.apply_type == WorkerApplyType.STOP:
            apply_func = self._stop_all_worker
        elif apply_req.apply_type == WorkerApplyType.UPDATE_PARAMS:
            apply_func = self._update_all_worker_params
        else:
            raise ValueError(f"Unsupported apply type {apply_req.apply_type}")
        return await apply_func(apply_req)

    async def parameter_descriptions(
        self, worker_type: str, model_name: str
    ) -> List[ParameterDescription]:
        worker_instances = await self.get_model_instances(worker_type, model_name)
        if not worker_instances:
            raise Exception(
                f"Not worker instances for model name {model_name} worker type {worker_type}"
            )
        worker_run_data = worker_instances[0]
        return worker_run_data.worker.parameter_descriptions()

    async def _apply_worker(
        self, apply_req: WorkerApplyRequest, apply_func: ApplyFunction
    ) -> None:
        """Apply function to worker instances in parallel

        Args:
            apply_req (WorkerApplyRequest): Worker apply request
            apply_func (ApplyFunction): Function to apply to worker instances, now function is async function
        """
        if apply_req:
            worker_type = apply_req.worker_type.value
            model_name = apply_req.model
            worker_instances = await self.get_model_instances(worker_type, model_name)
            if not worker_instances:
                raise Exception(
                    f"No worker instance found for the model {model_name} worker type {worker_type}"
                )
        else:
            # Apply to all workers
            worker_instances = list(itertools.chain(*self.workers.values()))
            logger.info(f"Apply to all workers: {worker_instances}")
        return await asyncio.gather(
            *(apply_func(worker) for worker in worker_instances)
        )

    async def _start_all_worker(
        self, apply_req: WorkerApplyRequest
    ) -> WorkerApplyOutput:
        start_time = time.time()
        logger.info(f"Begin start all worker, apply_req: {apply_req}")

        async def _start_worker(worker_run_data: WorkerRunData):
            worker_run_data.worker.start(
                worker_run_data.model_params, worker_run_data.command_args
            )
            worker_run_data.stop_event.clear()
            if worker_run_data.worker_params.register and self.register_func:
                # Register worker to controller
                await self.register_func(worker_run_data)
                if (
                    worker_run_data.worker_params.send_heartbeat
                    and self.send_heartbeat_func
                ):
                    asyncio.create_task(
                        _async_heartbeat_sender(
                            worker_run_data, self.send_heartbeat_func
                        )
                    )

        await self._apply_worker(apply_req, _start_worker)
        timecost = time.time() - start_time
        return WorkerApplyOutput(
            message=f"Worker started successfully", timecost=timecost
        )

    async def _stop_all_worker(
        self, apply_req: WorkerApplyRequest
    ) -> WorkerApplyOutput:
        start_time = time.time()

        async def _stop_worker(worker_run_data: WorkerRunData):
            worker_run_data.worker.stop()
            # Set stop event
            worker_run_data.stop_event.set()
            if worker_run_data._heartbeat_future:
                # Wait thread finish
                worker_run_data._heartbeat_future.result()
                worker_run_data._heartbeat_future = None
            if (
                worker_run_data.worker_params.register
                and self.register_func
                and self.deregister_func
            ):
                await self.deregister_func(worker_run_data)

        await self._apply_worker(apply_req, _stop_worker)
        timecost = time.time() - start_time
        return WorkerApplyOutput(
            message=f"Worker stopped successfully", timecost=timecost
        )

    async def _update_all_worker_params(
        self, apply_req: WorkerApplyRequest
    ) -> WorkerApplyOutput:
        start_time = time.time()
        need_restart = False

        async def update_params(worker_run_data: WorkerRunData):
            nonlocal need_restart
            new_params = apply_req.params
            if not new_params:
                return
            if worker_run_data.model_params.update_from(new_params):
                need_restart = True

        await self._apply_worker(apply_req, update_params)
        message = f"Update worker params successfully"
        timecost = time.time() - start_time
        if need_restart:
            logger.info("Model params update successfully, begin restart worker")
            await self._stop_all_worker(apply_req)
            await self._start_all_worker(apply_req)
            timecost = time.time() - start_time
            message = f"Update worker params and restart successfully"
        return WorkerApplyOutput(message=message, timecost=timecost)


class RemoteWorkerManager(LocalWorkerManager):
    def __init__(self, model_registry: ModelRegistry = None) -> None:
        super().__init__(model_registry=model_registry)

    async def get_model_instances(
        self, worker_type: str, model_name: str, healthy_only: bool = True
    ) -> List[WorkerRunData]:
        from pilot.model.worker.remote_worker import RemoteModelWorker

        worker_key = self._worker_key(worker_type, model_name)
        instances: List[ModelInstance] = await self.model_registry.get_all_instances(
            worker_key, healthy_only
        )
        worker_instances = []
        for ins in instances:
            worker = RemoteModelWorker()
            worker.load_worker(model_name, model_name, host=ins.host, port=ins.port)
            wr = WorkerRunData(
                worker_key=ins.model_name,
                worker=worker,
                worker_params=None,
                model_params=None,
                stop_event=asyncio.Event(),
                semaphore=asyncio.Semaphore(100),  # Not limit in client
            )
            worker_instances.append(wr)
        return worker_instances

    async def worker_apply(self, apply_req: WorkerApplyRequest) -> WorkerApplyOutput:
        async def _remote_apply_func(worker_run_data: WorkerRunData):
            worker_addr = worker_run_data.worker.worker_addr
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    worker_addr + "/apply",
                    headers=worker_run_data.worker.headers,
                    json=apply_req.dict(),
                    timeout=worker_run_data.worker.timeout,
                )
                if response.status_code == 200:
                    output = WorkerApplyOutput(**response.json())
                    logger.info(f"worker_apply success: {output}")
                else:
                    output = WorkerApplyOutput(message=response.text)
                    logger.warn(f"worker_apply failed: {output}")
                return output

        results = await self._apply_worker(apply_req, _remote_apply_func)
        if results:
            return results[0]


class WorkerManagerAdapter(WorkerManager):
    def __init__(self, worker_manager: WorkerManager = None) -> None:
        self.worker_manager = worker_manager

    async def get_model_instances(
        self, worker_type: str, model_name: str, healthy_only: bool = True
    ) -> List[WorkerRunData]:
        return await self.worker_manager.get_model_instances(
            worker_type, model_name, healthy_only
        )

    async def select_one_instanes(
        self, worker_type: str, model_name: str, healthy_only: bool = True
    ) -> WorkerRunData:
        return await self.worker_manager.select_one_instanes(
            worker_type, model_name, healthy_only
        )

    async def generate_stream(self, params: Dict, **kwargs) -> Iterator[ModelOutput]:
        async for output in self.worker_manager.generate_stream(params, **kwargs):
            yield output

    async def generate(self, params: Dict) -> ModelOutput:
        return await self.worker_manager.generate(params)

    async def embeddings(self, params: Dict) -> List[List[float]]:
        return await self.worker_manager.embeddings(params)

    async def worker_apply(self, apply_req: WorkerApplyRequest) -> WorkerApplyOutput:
        return await self.worker_manager.worker_apply(apply_req)

    async def parameter_descriptions(
        self, worker_type: str, model_name: str
    ) -> List[ParameterDescription]:
        return await self.worker_manager.parameter_descriptions(worker_type, model_name)


worker_manager = WorkerManagerAdapter()
router = APIRouter()


async def generate_json_stream(params):
    from starlette.concurrency import iterate_in_threadpool

    async for output in worker_manager.generate_stream(
        params, async_wrapper=iterate_in_threadpool
    ):
        yield json.dumps(asdict(output), ensure_ascii=False).encode() + b"\0"


@router.post("/worker/generate_stream")
async def api_generate_stream(request: Request):
    params = await request.json()
    generator = generate_json_stream(params)
    return StreamingResponse(generator)


@router.post("/worker/generate")
async def api_generate(request: PromptRequest):
    params = request.dict(exclude_none=True)
    output = await worker_manager.generate(params)
    return output


@router.post("/worker/embeddings")
async def api_embeddings(request: EmbeddingsRequest):
    params = request.dict(exclude_none=True)
    output = await worker_manager.embeddings(params)
    return output


@router.post("/worker/apply")
async def api_worker_apply(request: WorkerApplyRequest):
    output = await worker_manager.worker_apply(request)
    return output


@router.get("/worker/parameter/descriptions")
async def api_worker_parameter_descs(
    model: str, worker_type: str = WorkerType.LLM.value
):
    output = await worker_manager.parameter_descriptions(worker_type, model)
    return output


def _setup_fastapi(worker_params: ModelWorkerParameters):
    app = FastAPI()
    if worker_params.standalone:
        from pilot.model.controller.controller import router as controller_router

        if not worker_params.controller_addr:
            worker_params.controller_addr = f"http://127.0.0.1:{worker_params.port}"
        app.include_router(controller_router, prefix="/api")

    @app.on_event("startup")
    async def startup_event():
        asyncio.create_task(
            worker_manager.worker_manager._start_all_worker(apply_req=None)
        )

    return app


def _parse_worker_params(
    model_name: str = None, model_path: str = None, **kwargs
) -> ModelWorkerParameters:
    worker_args = EnvArgumentParser()
    worker_params: ModelWorkerParameters = worker_args.parse_args_into_dataclass(
        ModelWorkerParameters, model_name=model_name, model_path=model_path, **kwargs
    )
    env_prefix = EnvArgumentParser.get_env_prefix(worker_params.model_name)
    # Read parameters agein with prefix of model name.
    new_worker_params = worker_args.parse_args_into_dataclass(
        ModelWorkerParameters,
        env_prefix=env_prefix,
        model_name=worker_params.model_name,
        model_path=worker_params.model_path,
        **kwargs,
    )
    worker_params.update_from(new_worker_params)

    logger.info(f"Worker params: {worker_params}")
    return worker_params


def _create_local_model_manager(
    worker_params: ModelWorkerParameters,
) -> LocalWorkerManager:
    if not worker_params.register or not worker_params.controller_addr:
        logger.info(
            f"Not register current to controller, register: {worker_params.register}, controller_addr: {worker_params.controller_addr}"
        )
        return LocalWorkerManager()
    else:
        from pilot.model.controller.registry import ModelRegistryClient
        from pilot.utils.net_utils import _get_ip_address

        client = ModelRegistryClient(worker_params.controller_addr)
        host = _get_ip_address()
        port = worker_params.port

        async def register_func(worker_run_data: WorkerRunData):
            instance = ModelInstance(
                model_name=worker_run_data.worker_key, host=host, port=port
            )
            return await client.register_instance(instance)

        async def send_heartbeat_func(worker_run_data: WorkerRunData):
            instance = ModelInstance(
                model_name=worker_run_data.worker_key, host=host, port=port
            )
            return await client.send_heartbeat(instance)

        return LocalWorkerManager(
            register_func=register_func, send_heartbeat_func=send_heartbeat_func
        )


def _start_local_worker(
    worker_manager: WorkerManagerAdapter,
    worker_params: ModelWorkerParameters,
    embedded_mod=True,
):
    from pilot.utils.module_utils import import_from_checked_string

    if worker_params.worker_class:
        worker_cls = import_from_checked_string(worker_params.worker_class, ModelWorker)
        logger.info(
            f"Import worker class from {worker_params.worker_class} successfully"
        )
        worker: ModelWorker = worker_cls()
    else:
        from pilot.model.worker.default_worker import DefaultModelWorker

        worker = DefaultModelWorker()

    worker_manager.worker_manager = _create_local_model_manager(worker_params)
    worker_manager.worker_manager.add_worker(
        worker, worker_params, embedded_mod=embedded_mod
    )


def initialize_worker_manager_in_client(
    app=None,
    include_router: bool = True,
    model_name: str = None,
    model_path: str = None,
    run_locally: bool = True,
    controller_addr: str = None,
):
    global worker_manager

    worker_params: ModelWorkerParameters = _parse_worker_params(
        model_name=model_name, model_path=model_path, controller_addr=controller_addr
    )

    logger.info(f"Worker params: {worker_params}")
    if run_locally:
        worker_params.register = False
        _start_local_worker(worker_manager, worker_params, True)
        loop = asyncio.get_event_loop()
        loop.run_until_complete(
            worker_manager.worker_manager._start_all_worker(apply_req=None)
        )
    else:
        from pilot.model.controller.registry import ModelRegistryClient

        if not worker_params.controller_addr:
            raise ValueError("Controller can`t be None")
        client = ModelRegistryClient(worker_params.controller_addr)
        worker_manager.worker_manager = RemoteWorkerManager(client)

    if include_router and app:
        app.include_router(router, prefix="/api")


def run_worker_manager(
    app=None,
    include_router: bool = True,
    model_name: str = None,
    model_path: str = None,
    standalone: bool = False,
    port: int = None,
):
    global worker_manager

    worker_params: ModelWorkerParameters = _parse_worker_params(
        model_name=model_name, model_path=model_path, standalone=standalone, port=port
    )

    embedded_mod = True
    if not app:
        # Run worker manager independently
        embedded_mod = False
        app = _setup_fastapi(worker_params)
        _start_local_worker(worker_manager, worker_params, embedded_mod=False)
    else:
        _start_local_worker(worker_manager, worker_params, embedded_mod=False)
        loop = asyncio.get_event_loop()
        loop.run_until_complete(
            worker_manager.worker_manager._start_all_worker(apply_req=None)
        )

    if include_router:
        app.include_router(router, prefix="/api")

    if not embedded_mod:
        uvicorn.run(
            app, host=worker_params.host, port=worker_params.port, log_level="info"
        )


if __name__ == "__main__":
    run_worker_manager()
