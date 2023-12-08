import asyncio
import itertools
import json
import logging
import os
import random
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from typing import Awaitable, Callable, Dict, Iterator, List

from fastapi import APIRouter, FastAPI
from fastapi.responses import StreamingResponse

from dbgpt.component import SystemApp
from dbgpt.configs.model_config import LOGDIR
from dbgpt.core import ModelOutput
from dbgpt.model.base import (
    ModelInstance,
    WorkerApplyOutput,
    WorkerApplyType,
    WorkerSupportedModel,
)
from dbgpt.model.cluster.base import *
from dbgpt.model.cluster.manager_base import (
    WorkerManager,
    WorkerManagerFactory,
    WorkerRunData,
)
from dbgpt.model.cluster.registry import ModelRegistry
from dbgpt.model.cluster.worker_base import ModelWorker
from dbgpt.model.llm_utils import list_supported_models
from dbgpt.model.parameter import ModelParameters, ModelWorkerParameters, WorkerType
from dbgpt.util.parameter_utils import (
    EnvArgumentParser,
    ParameterDescription,
    _dict_to_command_args,
    _get_dict_from_obj,
)
from dbgpt.util.utils import setup_logging, setup_http_service_logging
from dbgpt.util.tracer import initialize_tracer, root_tracer, SpanType, SpanTypeRunName
from dbgpt.util.system_utils import get_system_info

logger = logging.getLogger(__name__)

RegisterFunc = Callable[[WorkerRunData], Awaitable[None]]
DeregisterFunc = Callable[[WorkerRunData], Awaitable[None]]
SendHeartbeatFunc = Callable[[WorkerRunData], Awaitable[None]]
ApplyFunction = Callable[[WorkerRunData], Awaitable[None]]


async def _async_heartbeat_sender(
    worker_run_data: WorkerRunData,
    heartbeat_interval,
    send_heartbeat_func: SendHeartbeatFunc,
):
    while not worker_run_data.stop_event.is_set():
        try:
            await send_heartbeat_func(worker_run_data)
        except Exception as e:
            logger.warn(f"Send heartbeat func error: {str(e)}")
        finally:
            await asyncio.sleep(heartbeat_interval)


class LocalWorkerManager(WorkerManager):
    def __init__(
        self,
        register_func: RegisterFunc = None,
        deregister_func: DeregisterFunc = None,
        send_heartbeat_func: SendHeartbeatFunc = None,
        model_registry: ModelRegistry = None,
        host: str = None,
        port: int = None,
    ) -> None:
        self.workers: Dict[str, List[WorkerRunData]] = dict()
        self.executor = ThreadPoolExecutor(max_workers=os.cpu_count() * 5)
        self.register_func = register_func
        self.deregister_func = deregister_func
        self.send_heartbeat_func = send_heartbeat_func
        self.model_registry = model_registry
        self.host = host
        self.port = port
        self.start_listeners = []

        self.run_data = WorkerRunData(
            host=self.host,
            port=self.port,
            worker_key=self._worker_key(
                WORKER_MANAGER_SERVICE_TYPE, WORKER_MANAGER_SERVICE_NAME
            ),
            worker=None,
            worker_params=None,
            model_params=None,
            stop_event=asyncio.Event(),
            semaphore=None,
            command_args=None,
        )

    def _worker_key(self, worker_type: str, model_name: str) -> str:
        return WorkerType.to_worker_key(model_name, worker_type)

    async def run_blocking_func(self, func, *args):
        if asyncio.iscoroutinefunction(func):
            raise ValueError(f"The function {func} is not blocking function")
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self.executor, func, *args)

    async def start(self):
        if len(self.workers) > 0:
            out = await self._start_all_worker(apply_req=None)
            if not out.success:
                raise Exception(out.message)
        if self.register_func:
            await self.register_func(self.run_data)
        if self.send_heartbeat_func:
            asyncio.create_task(
                _async_heartbeat_sender(self.run_data, 20, self.send_heartbeat_func)
            )
        for listener in self.start_listeners:
            if asyncio.iscoroutinefunction(listener):
                await listener(self)
            else:
                listener(self)

    async def stop(self, ignore_exception: bool = False):
        if not self.run_data.stop_event.is_set():
            logger.info("Stop all workers")
            self.run_data.stop_event.clear()
            stop_tasks = []
            stop_tasks.append(
                self._stop_all_worker(apply_req=None, ignore_exception=ignore_exception)
            )
            if self.deregister_func:
                # If ignore_exception is True, use exception handling to ignore any exceptions raised from self.deregister_func
                if ignore_exception:

                    async def safe_deregister_func(run_data):
                        try:
                            await self.deregister_func(run_data)
                        except Exception as e:
                            logger.warning(
                                f"Stop worker, ignored exception from deregister_func: {e}"
                            )

                    stop_tasks.append(safe_deregister_func(self.run_data))
                else:
                    stop_tasks.append(self.deregister_func(self.run_data))

            results = await asyncio.gather(*stop_tasks)
            if not results[0].success and not ignore_exception:
                raise Exception(results[0].message)

    def after_start(self, listener: Callable[["WorkerManager"], None]):
        self.start_listeners.append(listener)

    def add_worker(
        self,
        worker: ModelWorker,
        worker_params: ModelWorkerParameters,
        command_args: List[str] = None,
    ) -> bool:
        if not command_args:
            command_args = sys.argv[1:]
        worker.load_worker(**asdict(worker_params))

        if not worker_params.worker_type:
            worker_params.worker_type = worker.worker_type()

        if isinstance(worker_params.worker_type, WorkerType):
            worker_params.worker_type = worker_params.worker_type.value

        worker_key = self._worker_key(
            worker_params.worker_type, worker_params.model_name
        )

        # Load model params from persist storage
        model_params = worker.parse_parameters(command_args=command_args)

        worker_run_data = WorkerRunData(
            host=self.host,
            port=self.port,
            worker_key=worker_key,
            worker=worker,
            worker_params=worker_params,
            model_params=model_params,
            stop_event=asyncio.Event(),
            semaphore=asyncio.Semaphore(worker_params.limit_model_concurrency),
            command_args=command_args,
        )
        instances = self.workers.get(worker_key)
        if not instances:
            instances = [worker_run_data]
            self.workers[worker_key] = instances
            logger.info(f"Init empty instances list for {worker_key}")
            return True
        else:
            # TODO Update worker
            logger.warn(f"Instance {worker_key} exist")
            return False

    def _remove_worker(self, worker_params: ModelWorkerParameters) -> None:
        worker_key = self._worker_key(
            worker_params.worker_type, worker_params.model_name
        )
        instances = self.workers.get(worker_key)
        if instances:
            del self.workers[worker_key]

    async def model_startup(self, startup_req: WorkerStartupRequest):
        """Start model"""
        model_name = startup_req.model
        worker_type = startup_req.worker_type
        params = startup_req.params
        logger.debug(
            f"start model, model name {model_name}, worker type {worker_type},  params: {params}"
        )
        worker_params: ModelWorkerParameters = ModelWorkerParameters.from_dict(
            params, ignore_extra_fields=True
        )
        if not worker_params.model_name:
            worker_params.model_name = model_name
        assert model_name == worker_params.model_name
        worker = _build_worker(worker_params)
        command_args = _dict_to_command_args(params)
        success = await self.run_blocking_func(
            self.add_worker, worker, worker_params, command_args
        )
        if not success:
            msg = f"Add worker {model_name}@{worker_type}, worker instances is exist"
            logger.warn(f"{msg}, worker_params: {worker_params}")
            self._remove_worker(worker_params)
            raise Exception(msg)
        supported_types = WorkerType.values()
        if worker_type not in supported_types:
            self._remove_worker(worker_params)
            raise ValueError(
                f"Unsupported worker type: {worker_type}, now supported worker type: {supported_types}"
            )
        start_apply_req = WorkerApplyRequest(
            model=model_name, apply_type=WorkerApplyType.START, worker_type=worker_type
        )
        out: WorkerApplyOutput = None
        try:
            out = await self.worker_apply(start_apply_req)
        except Exception as e:
            self._remove_worker(worker_params)
            raise e
        if not out.success:
            self._remove_worker(worker_params)
            raise Exception(out.message)

    async def model_shutdown(self, shutdown_req: WorkerStartupRequest):
        logger.info(f"Begin shutdown model, shutdown_req: {shutdown_req}")
        apply_req = WorkerApplyRequest(
            model=shutdown_req.model,
            apply_type=WorkerApplyType.STOP,
            worker_type=shutdown_req.worker_type,
        )
        out = await self._stop_all_worker(apply_req)
        if not out.success:
            raise Exception(out.message)

    async def supported_models(self) -> List[WorkerSupportedModel]:
        models = await self.run_blocking_func(list_supported_models)
        return [WorkerSupportedModel(host=self.host, port=self.port, models=models)]

    async def get_model_instances(
        self, worker_type: str, model_name: str, healthy_only: bool = True
    ) -> List[WorkerRunData]:
        return self.sync_get_model_instances(worker_type, model_name, healthy_only)

    def sync_get_model_instances(
        self, worker_type: str, model_name: str, healthy_only: bool = True
    ) -> List[WorkerRunData]:
        worker_key = self._worker_key(worker_type, model_name)
        return self.workers.get(worker_key, [])

    def _simple_select(
        self, worker_type: str, model_name: str, worker_instances: List[WorkerRunData]
    ) -> WorkerRunData:
        if not worker_instances:
            raise Exception(
                f"Cound not found worker instances for model name {model_name} and worker type {worker_type}"
            )
        worker_run_data = random.choice(worker_instances)
        return worker_run_data

    async def select_one_instance(
        self, worker_type: str, model_name: str, healthy_only: bool = True
    ) -> WorkerRunData:
        worker_instances = await self.get_model_instances(
            worker_type, model_name, healthy_only
        )
        return self._simple_select(worker_type, model_name, worker_instances)

    def sync_select_one_instance(
        self, worker_type: str, model_name: str, healthy_only: bool = True
    ) -> WorkerRunData:
        worker_instances = self.sync_get_model_instances(
            worker_type, model_name, healthy_only
        )
        return self._simple_select(worker_type, model_name, worker_instances)

    async def _get_model(self, params: Dict, worker_type: str = "llm") -> WorkerRunData:
        model = params.get("model")
        if not model:
            raise Exception("Model name count not be empty")
        return await self.select_one_instance(worker_type, model, healthy_only=True)

    def _sync_get_model(self, params: Dict, worker_type: str = "llm") -> WorkerRunData:
        model = params.get("model")
        if not model:
            raise Exception("Model name count not be empty")
        return self.sync_select_one_instance(worker_type, model, healthy_only=True)

    async def generate_stream(
        self, params: Dict, async_wrapper=None, **kwargs
    ) -> Iterator[ModelOutput]:
        """Generate stream result, chat scene"""
        with root_tracer.start_span(
            "WorkerManager.generate_stream", params.get("span_id")
        ) as span:
            params["span_id"] = span.span_id
            try:
                worker_run_data = await self._get_model(params)
            except Exception as e:
                yield ModelOutput(
                    text=f"**LLMServer Generate Error, Please CheckErrorInfo.**: {e}",
                    error_code=1,
                )
                return
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
        with root_tracer.start_span(
            "WorkerManager.generate", params.get("span_id")
        ) as span:
            params["span_id"] = span.span_id
            try:
                worker_run_data = await self._get_model(params)
            except Exception as e:
                return ModelOutput(
                    text=f"**LLMServer Generate Error, Please CheckErrorInfo.**: {e}",
                    error_code=1,
                )
            async with worker_run_data.semaphore:
                if worker_run_data.worker.support_async():
                    return await worker_run_data.worker.async_generate(params)
                else:
                    return await self.run_blocking_func(
                        worker_run_data.worker.generate, params
                    )

    async def embeddings(self, params: Dict) -> List[List[float]]:
        """Embed input"""
        with root_tracer.start_span(
            "WorkerManager.embeddings", params.get("span_id")
        ) as span:
            params["span_id"] = span.span_id
            try:
                worker_run_data = await self._get_model(params, worker_type="text2vec")
            except Exception as e:
                raise e
            async with worker_run_data.semaphore:
                if worker_run_data.worker.support_async():
                    return await worker_run_data.worker.async_embeddings(params)
                else:
                    return await self.run_blocking_func(
                        worker_run_data.worker.embeddings, params
                    )

    def sync_embeddings(self, params: Dict) -> List[List[float]]:
        worker_run_data = self._sync_get_model(params, worker_type="text2vec")
        return worker_run_data.worker.embeddings(params)

    async def worker_apply(self, apply_req: WorkerApplyRequest) -> WorkerApplyOutput:
        apply_func: Callable[[WorkerApplyRequest], Awaitable[str]] = None
        if apply_req.apply_type == WorkerApplyType.START:
            apply_func = self._start_all_worker
        elif apply_req.apply_type == WorkerApplyType.STOP:
            apply_func = self._stop_all_worker
        elif apply_req.apply_type == WorkerApplyType.RESTART:
            apply_func = self._restart_all_worker
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
        logger.info(f"Apply req: {apply_req}, apply_func: {apply_func}")
        if apply_req:
            worker_type = apply_req.worker_type.value
            model_name = apply_req.model
            worker_instances = await self.get_model_instances(
                worker_type, model_name, healthy_only=False
            )
            if not worker_instances:
                raise Exception(
                    f"No worker instance found for the model {model_name} worker type {worker_type}"
                )
        else:
            # Apply to all workers
            worker_instances = list(itertools.chain(*self.workers.values()))
            logger.info(f"Apply to all workers")
        return await asyncio.gather(
            *(apply_func(worker) for worker in worker_instances)
        )

    async def _start_all_worker(
        self, apply_req: WorkerApplyRequest
    ) -> WorkerApplyOutput:
        # TODO avoid start twice
        start_time = time.time()
        logger.info(f"Begin start all worker, apply_req: {apply_req}")

        async def _start_worker(worker_run_data: WorkerRunData):
            _start_time = time.time()
            info = worker_run_data._to_print_key()
            out = WorkerApplyOutput("")
            try:
                await self.run_blocking_func(
                    worker_run_data.worker.start,
                    worker_run_data.model_params,
                    worker_run_data.command_args,
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
                                worker_run_data,
                                worker_run_data.worker_params.heartbeat_interval,
                                self.send_heartbeat_func,
                            )
                        )
                out.message = f"{info} start successfully"
            except Exception as e:
                out.success = False
                out.message = f"{info} start failed, {str(e)}"
            finally:
                out.timecost = time.time() - _start_time
            return out

        outs = await self._apply_worker(apply_req, _start_worker)
        out = WorkerApplyOutput.reduce(outs)
        out.timecost = time.time() - start_time
        return out

    async def _stop_all_worker(
        self, apply_req: WorkerApplyRequest, ignore_exception: bool = False
    ) -> WorkerApplyOutput:
        start_time = time.time()

        async def _stop_worker(worker_run_data: WorkerRunData):
            _start_time = time.time()
            info = worker_run_data._to_print_key()
            out = WorkerApplyOutput("")
            try:
                await self.run_blocking_func(worker_run_data.worker.stop)
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
                    _deregister_func = self.deregister_func
                    if ignore_exception:

                        async def safe_deregister_func(run_data):
                            try:
                                await self.deregister_func(run_data)
                            except Exception as e:
                                logger.warning(
                                    f"Stop worker, ignored exception from deregister_func: {e}"
                                )

                        _deregister_func = safe_deregister_func
                    await _deregister_func(worker_run_data)
                # Remove metadata
                self._remove_worker(worker_run_data.worker_params)
                out.message = f"{info} stop successfully"
            except Exception as e:
                out.success = False
                out.message = f"{info} stop failed, {str(e)}"
            finally:
                out.timecost = time.time() - _start_time
            return out

        outs = await self._apply_worker(apply_req, _stop_worker)
        out = WorkerApplyOutput.reduce(outs)
        out.timecost = time.time() - start_time
        return out

    async def _restart_all_worker(
        self, apply_req: WorkerApplyRequest
    ) -> WorkerApplyOutput:
        out = await self._stop_all_worker(apply_req, ignore_exception=True)
        if not out.success:
            return out
        return await self._start_all_worker(apply_req)

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
            await self._restart_all_worker(apply_req)
            timecost = time.time() - start_time
            message = f"Update worker params and restart successfully"
        return WorkerApplyOutput(message=message, timecost=timecost)


class WorkerManagerAdapter(WorkerManager):
    def __init__(self, worker_manager: WorkerManager = None) -> None:
        self.worker_manager = worker_manager

    async def start(self):
        return await self.worker_manager.start()

    async def stop(self, ignore_exception: bool = False):
        return await self.worker_manager.stop(ignore_exception=ignore_exception)

    def after_start(self, listener: Callable[["WorkerManager"], None]):
        if listener is not None:
            self.worker_manager.after_start(listener)

    async def supported_models(self) -> List[WorkerSupportedModel]:
        return await self.worker_manager.supported_models()

    async def model_startup(self, startup_req: WorkerStartupRequest):
        return await self.worker_manager.model_startup(startup_req)

    async def model_shutdown(self, shutdown_req: WorkerStartupRequest):
        return await self.worker_manager.model_shutdown(shutdown_req)

    async def get_model_instances(
        self, worker_type: str, model_name: str, healthy_only: bool = True
    ) -> List[WorkerRunData]:
        return await self.worker_manager.get_model_instances(
            worker_type, model_name, healthy_only
        )

    def sync_get_model_instances(
        self, worker_type: str, model_name: str, healthy_only: bool = True
    ) -> List[WorkerRunData]:
        return self.worker_manager.sync_get_model_instances(
            worker_type, model_name, healthy_only
        )

    async def select_one_instance(
        self, worker_type: str, model_name: str, healthy_only: bool = True
    ) -> WorkerRunData:
        return await self.worker_manager.select_one_instance(
            worker_type, model_name, healthy_only
        )

    def sync_select_one_instance(
        self, worker_type: str, model_name: str, healthy_only: bool = True
    ) -> WorkerRunData:
        return self.worker_manager.sync_select_one_instance(
            worker_type, model_name, healthy_only
        )

    async def generate_stream(self, params: Dict, **kwargs) -> Iterator[ModelOutput]:
        async for output in self.worker_manager.generate_stream(params, **kwargs):
            yield output

    async def generate(self, params: Dict) -> ModelOutput:
        return await self.worker_manager.generate(params)

    async def embeddings(self, params: Dict) -> List[List[float]]:
        return await self.worker_manager.embeddings(params)

    def sync_embeddings(self, params: Dict) -> List[List[float]]:
        return self.worker_manager.sync_embeddings(params)

    async def worker_apply(self, apply_req: WorkerApplyRequest) -> WorkerApplyOutput:
        return await self.worker_manager.worker_apply(apply_req)

    async def parameter_descriptions(
        self, worker_type: str, model_name: str
    ) -> List[ParameterDescription]:
        return await self.worker_manager.parameter_descriptions(worker_type, model_name)


class _DefaultWorkerManagerFactory(WorkerManagerFactory):
    def __init__(
        self, system_app: SystemApp | None = None, worker_manager: WorkerManager = None
    ):
        super().__init__(system_app)
        self.worker_manager = worker_manager

    def create(self) -> WorkerManager:
        return self.worker_manager


worker_manager = WorkerManagerAdapter()
router = APIRouter()


async def generate_json_stream(params):
    from starlette.concurrency import iterate_in_threadpool

    async for output in worker_manager.generate_stream(
        params, async_wrapper=iterate_in_threadpool
    ):
        yield json.dumps(asdict(output), ensure_ascii=False).encode() + b"\0"


@router.post("/worker/generate_stream")
async def api_generate_stream(request: PromptRequest):
    params = request.dict(exclude_none=True)
    span_id = root_tracer.get_current_span_id()
    if "span_id" not in params and span_id:
        params["span_id"] = span_id
    generator = generate_json_stream(params)
    return StreamingResponse(generator)


@router.post("/worker/generate")
async def api_generate(request: PromptRequest):
    params = request.dict(exclude_none=True)
    span_id = root_tracer.get_current_span_id()
    if "span_id" not in params and span_id:
        params["span_id"] = span_id
    return await worker_manager.generate(params)


@router.post("/worker/embeddings")
async def api_embeddings(request: EmbeddingsRequest):
    params = request.dict(exclude_none=True)
    span_id = root_tracer.get_current_span_id()
    if "span_id" not in params and span_id:
        params["span_id"] = span_id
    return await worker_manager.embeddings(params)


@router.post("/worker/apply")
async def api_worker_apply(request: WorkerApplyRequest):
    return await worker_manager.worker_apply(request)


@router.get("/worker/parameter/descriptions")
async def api_worker_parameter_descs(
    model: str, worker_type: str = WorkerType.LLM.value
):
    return await worker_manager.parameter_descriptions(worker_type, model)


@router.get("/worker/models/supports")
async def api_supported_models():
    """Get all supported models.

    This method reads all models from the configuration file and tries to perform some basic checks on the model (like if the path exists).

    If it's a RemoteWorkerManager, this method returns the list of models supported by the entire cluster.
    """
    return await worker_manager.supported_models()


@router.post("/worker/models/startup")
async def api_model_startup(request: WorkerStartupRequest):
    """Start up a specific model."""
    return await worker_manager.model_startup(request)


@router.post("/worker/models/shutdown")
async def api_model_shutdown(request: WorkerStartupRequest):
    """Shut down a specific model."""
    return await worker_manager.model_shutdown(request)


def _setup_fastapi(
    worker_params: ModelWorkerParameters, app=None, ignore_exception: bool = False
):
    if not app:
        app = FastAPI()
        setup_http_service_logging()

    if worker_params.standalone:
        from dbgpt.model.cluster.controller.controller import initialize_controller
        from dbgpt.model.cluster.controller.controller import (
            router as controller_router,
        )

        if not worker_params.controller_addr:
            # if we have http_proxy or https_proxy in env, the server can not start
            # so set it to empty here
            os.environ["http_proxy"] = ""
            os.environ["https_proxy"] = ""
            worker_params.controller_addr = f"http://127.0.0.1:{worker_params.port}"
        logger.info(
            f"Run WorkerManager with standalone mode, controller_addr: {worker_params.controller_addr}"
        )
        initialize_controller(app=app)
        app.include_router(controller_router, prefix="/api")

    @app.on_event("startup")
    async def startup_event():
        async def start_worker_manager():
            try:
                await worker_manager.start()
            except Exception as e:
                logger.error(f"Error starting worker manager: {e}")
                sys.exit(1)

        # It cannot be blocked here because the startup of worker_manager depends on the fastapi app (registered to the controller)
        asyncio.create_task(start_worker_manager())

    @app.on_event("shutdown")
    async def startup_event():
        await worker_manager.stop(ignore_exception=ignore_exception)

    return app


def _parse_worker_params(
    model_name: str = None, model_path: str = None, **kwargs
) -> ModelWorkerParameters:
    worker_args = EnvArgumentParser()
    env_prefix = None
    if model_name:
        env_prefix = EnvArgumentParser.get_env_prefix(model_name)
    worker_params: ModelWorkerParameters = worker_args.parse_args_into_dataclass(
        ModelWorkerParameters,
        env_prefixes=[env_prefix],
        model_name=model_name,
        model_path=model_path,
        **kwargs,
    )
    env_prefix = EnvArgumentParser.get_env_prefix(worker_params.model_name)
    # Read parameters agein with prefix of model name.
    new_worker_params = worker_args.parse_args_into_dataclass(
        ModelWorkerParameters,
        env_prefixes=[env_prefix],
        model_name=worker_params.model_name,
        model_path=worker_params.model_path,
        **kwargs,
    )
    worker_params.update_from(new_worker_params)

    # logger.info(f"Worker params: {worker_params}")
    return worker_params


def _create_local_model_manager(
    worker_params: ModelWorkerParameters,
) -> LocalWorkerManager:
    from dbgpt.util.net_utils import _get_ip_address

    host = (
        worker_params.worker_register_host
        if worker_params.worker_register_host
        else _get_ip_address()
    )
    port = worker_params.port
    if not worker_params.register or not worker_params.controller_addr:
        logger.info(
            f"Not register current to controller, register: {worker_params.register}, controller_addr: {worker_params.controller_addr}"
        )
        return LocalWorkerManager(host=host, port=port)
    else:
        from dbgpt.model.cluster.controller.controller import ModelRegistryClient

        client = ModelRegistryClient(worker_params.controller_addr)

        async def register_func(worker_run_data: WorkerRunData):
            instance = ModelInstance(
                model_name=worker_run_data.worker_key, host=host, port=port
            )
            return await client.register_instance(instance)

        async def deregister_func(worker_run_data: WorkerRunData):
            instance = ModelInstance(
                model_name=worker_run_data.worker_key, host=host, port=port
            )
            return await client.deregister_instance(instance)

        async def send_heartbeat_func(worker_run_data: WorkerRunData):
            instance = ModelInstance(
                model_name=worker_run_data.worker_key, host=host, port=port
            )
            return await client.send_heartbeat(instance)

        return LocalWorkerManager(
            register_func=register_func,
            deregister_func=deregister_func,
            send_heartbeat_func=send_heartbeat_func,
            host=host,
            port=port,
        )


def _build_worker(worker_params: ModelWorkerParameters):
    worker_class = worker_params.worker_class
    if worker_class:
        from dbgpt.util.module_utils import import_from_checked_string

        worker_cls = import_from_checked_string(worker_class, ModelWorker)
        logger.info(f"Import worker class from {worker_class} successfully")
    else:
        if (
            worker_params.worker_type is None
            or worker_params.worker_type == WorkerType.LLM
        ):
            from dbgpt.model.cluster.worker.default_worker import DefaultModelWorker

            worker_cls = DefaultModelWorker
        elif worker_params.worker_type == WorkerType.TEXT2VEC:
            from dbgpt.model.cluster.worker.embedding_worker import (
                EmbeddingsModelWorker,
            )

            worker_cls = EmbeddingsModelWorker
        else:
            raise Exception("Unsupported worker type: {worker_params.worker_type}")

    return worker_cls()


def _start_local_worker(
    worker_manager: WorkerManagerAdapter, worker_params: ModelWorkerParameters
):
    with root_tracer.start_span(
        "WorkerManager._start_local_worker",
        span_type=SpanType.RUN,
        metadata={
            "run_service": SpanTypeRunName.WORKER_MANAGER,
            "params": _get_dict_from_obj(worker_params),
            "sys_infos": _get_dict_from_obj(get_system_info()),
        },
    ):
        worker = _build_worker(worker_params)
        if not worker_manager.worker_manager:
            worker_manager.worker_manager = _create_local_model_manager(worker_params)
        worker_manager.worker_manager.add_worker(worker, worker_params)


def _start_local_embedding_worker(
    worker_manager: WorkerManagerAdapter,
    embedding_model_name: str = None,
    embedding_model_path: str = None,
):
    if not embedding_model_name or not embedding_model_path:
        return
    embedding_worker_params = ModelWorkerParameters(
        model_name=embedding_model_name,
        model_path=embedding_model_path,
        worker_type=WorkerType.TEXT2VEC,
        worker_class="dbgpt.model.cluster.worker.embedding_worker.EmbeddingsModelWorker",
    )
    logger.info(
        f"Start local embedding worker with embedding parameters\n{embedding_worker_params}"
    )
    _start_local_worker(worker_manager, embedding_worker_params)


def initialize_worker_manager_in_client(
    app=None,
    include_router: bool = True,
    model_name: str = None,
    model_path: str = None,
    run_locally: bool = True,
    controller_addr: str = None,
    local_port: int = 5000,
    embedding_model_name: str = None,
    embedding_model_path: str = None,
    start_listener: Callable[["WorkerManager"], None] = None,
    system_app: SystemApp = None,
):
    """Initialize WorkerManager in client.
    If run_locally is True:
    1. Start ModelController
    2. Start LocalWorkerManager
    3. Start worker in LocalWorkerManager
    4. Register worker to ModelController

    otherwise:
    1. Build ModelRegistryClient with controller address
    2. Start RemoteWorkerManager

    """
    global worker_manager

    if not app:
        raise Exception("app can't be None")

    worker_params: ModelWorkerParameters = _parse_worker_params(
        model_name=model_name, model_path=model_path, controller_addr=controller_addr
    )

    controller_addr = None
    if run_locally:
        # TODO start ModelController
        worker_params.standalone = True
        worker_params.register = True
        worker_params.port = local_port
        logger.info(f"Worker params: {worker_params}")
        _setup_fastapi(worker_params, app, ignore_exception=True)
        _start_local_worker(worker_manager, worker_params)
        worker_manager.after_start(start_listener)
        _start_local_embedding_worker(
            worker_manager, embedding_model_name, embedding_model_path
        )
    else:
        from dbgpt.model.cluster.controller.controller import (
            ModelRegistryClient,
            initialize_controller,
        )
        from dbgpt.model.cluster.worker.remote_manager import RemoteWorkerManager

        if not worker_params.controller_addr:
            raise ValueError("Controller can`t be None")
        controller_addr = worker_params.controller_addr
        logger.info(f"Worker params: {worker_params}")
        client = ModelRegistryClient(worker_params.controller_addr)
        worker_manager.worker_manager = RemoteWorkerManager(client)
        worker_manager.after_start(start_listener)
        initialize_controller(
            app=app, remote_controller_addr=worker_params.controller_addr
        )
        loop = asyncio.get_event_loop()
        loop.run_until_complete(worker_manager.start())

    if include_router and app:
        # mount WorkerManager router
        app.include_router(router, prefix="/api")
    if system_app:
        system_app.register(_DefaultWorkerManagerFactory, worker_manager)


def run_worker_manager(
    app=None,
    include_router: bool = True,
    model_name: str = None,
    model_path: str = None,
    standalone: bool = False,
    port: int = None,
    embedding_model_name: str = None,
    embedding_model_path: str = None,
    start_listener: Callable[["WorkerManager"], None] = None,
    **kwargs,
):
    global worker_manager

    worker_params: ModelWorkerParameters = _parse_worker_params(
        model_name=model_name,
        model_path=model_path,
        standalone=standalone,
        port=port,
        **kwargs,
    )

    setup_logging(
        "dbgpt",
        logging_level=worker_params.log_level,
        logger_filename=worker_params.log_file,
    )

    embedded_mod = True
    logger.info(f"Worker params: {worker_params}")
    if not app:
        # Run worker manager independently
        embedded_mod = False
        app = _setup_fastapi(worker_params)

    system_app = SystemApp(app)
    initialize_tracer(
        system_app,
        os.path.join(LOGDIR, worker_params.tracer_file),
        root_operation_name="DB-GPT-WorkerManager-Entry",
        tracer_storage_cls=worker_params.tracer_storage_cls,
    )

    _start_local_worker(worker_manager, worker_params)
    _start_local_embedding_worker(
        worker_manager, embedding_model_name, embedding_model_path
    )

    worker_manager.after_start(start_listener)

    if include_router:
        app.include_router(router, prefix="/api")

    if not embedded_mod:
        import uvicorn

        uvicorn.run(
            app, host=worker_params.host, port=worker_params.port, log_level="info"
        )
    else:
        # Embedded mod, start worker manager
        loop = asyncio.get_event_loop()
        loop.run_until_complete(worker_manager.start())


if __name__ == "__main__":
    run_worker_manager()
