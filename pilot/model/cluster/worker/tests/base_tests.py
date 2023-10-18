import pytest
import pytest_asyncio
from contextlib import contextmanager, asynccontextmanager
from typing import List, Iterator, Dict, Tuple
from pilot.model.parameter import ModelParameters, ModelWorkerParameters, WorkerType
from pilot.model.base import ModelOutput
from pilot.model.cluster.worker_base import ModelWorker
from pilot.model.cluster.worker.manager import (
    LocalWorkerManager,
    RegisterFunc,
    DeregisterFunc,
    SendHeartbeatFunc,
    ApplyFunction,
)


class MockModelWorker(ModelWorker):
    def __init__(
        self,
        model_parameters: ModelParameters,
        error_worker: bool = False,
        stop_error: bool = False,
        stream_messags: List[str] = None,
        embeddings: List[List[float]] = None,
    ) -> None:
        super().__init__()
        if not stream_messags:
            stream_messags = []
        if not embeddings:
            embeddings = []
        self.model_parameters = model_parameters
        self.error_worker = error_worker
        self.stop_error = stop_error
        self.stream_messags = stream_messags
        self._embeddings = embeddings

    def parse_parameters(self, command_args: List[str] = None) -> ModelParameters:
        return self.model_parameters

    def load_worker(self, model_name: str, model_path: str, **kwargs) -> None:
        pass

    def start(
        self, model_params: ModelParameters = None, command_args: List[str] = None
    ) -> None:
        if self.error_worker:
            raise Exception("Start worker error for mock")

    def stop(self) -> None:
        if self.stop_error:
            raise Exception("Stop worker error for mock")

    def generate_stream(self, params: Dict) -> Iterator[ModelOutput]:
        for msg in self.stream_messags:
            yield ModelOutput(text=msg, error_code=0)

    def generate(self, params: Dict) -> ModelOutput:
        output = None
        for out in self.generate_stream(params):
            output = out
        return output

    def embeddings(self, params: Dict) -> List[List[float]]:
        return self._embeddings


_TEST_MODEL_NAME = "vicuna-13b-v1.5"
_TEST_MODEL_PATH = "/app/models/vicuna-13b-v1.5"


def _new_worker_params(
    model_name: str = _TEST_MODEL_NAME,
    model_path: str = _TEST_MODEL_PATH,
    worker_type: str = WorkerType.LLM.value,
) -> ModelWorkerParameters:
    return ModelWorkerParameters(
        model_name=model_name, model_path=model_path, worker_type=worker_type
    )


def _create_workers(
    num_workers: int,
    error_worker: bool = False,
    stop_error: bool = False,
    worker_type: str = WorkerType.LLM.value,
    stream_messags: List[str] = None,
    embeddings: List[List[float]] = None,
) -> List[Tuple[ModelWorker, ModelWorkerParameters]]:
    workers = []
    for i in range(num_workers):
        model_name = f"test-model-name-{i}"
        model_path = f"test-model-path-{i}"
        model_parameters = ModelParameters(model_name=model_name, model_path=model_path)
        worker = MockModelWorker(
            model_parameters,
            error_worker=error_worker,
            stop_error=stop_error,
            stream_messags=stream_messags,
            embeddings=embeddings,
        )
        worker_params = _new_worker_params(
            model_name, model_path, worker_type=worker_type
        )
        workers.append((worker, worker_params))
    return workers


@asynccontextmanager
async def _start_worker_manager(**kwargs):
    register_func = kwargs.get("register_func")
    deregister_func = kwargs.get("deregister_func")
    send_heartbeat_func = kwargs.get("send_heartbeat_func")
    model_registry = kwargs.get("model_registry")
    workers = kwargs.get("workers")
    num_workers = int(kwargs.get("num_workers", 0))
    start = kwargs.get("start", True)
    stop = kwargs.get("stop", True)
    error_worker = kwargs.get("error_worker", False)
    stop_error = kwargs.get("stop_error", False)
    stream_messags = kwargs.get("stream_messags", [])
    embeddings = kwargs.get("embeddings", [])

    worker_manager = LocalWorkerManager(
        register_func=register_func,
        deregister_func=deregister_func,
        send_heartbeat_func=send_heartbeat_func,
        model_registry=model_registry,
    )

    for worker, worker_params in _create_workers(
        num_workers, error_worker, stop_error, stream_messags, embeddings
    ):
        worker_manager.add_worker(worker, worker_params)
    if workers:
        for worker, worker_params in workers:
            worker_manager.add_worker(worker, worker_params)

    if start:
        await worker_manager.start()

    yield worker_manager
    if stop:
        await worker_manager.stop()


@pytest_asyncio.fixture
async def manager_2_workers(request):
    param = getattr(request, "param", {})
    async with _start_worker_manager(num_workers=2, **param) as worker_manager:
        yield worker_manager


@pytest_asyncio.fixture
async def manager_with_2_workers(request):
    param = getattr(request, "param", {})
    workers = _create_workers(2, stream_messags=param.get("stream_messags", []))
    async with _start_worker_manager(workers=workers, **param) as worker_manager:
        yield (worker_manager, workers)


@pytest_asyncio.fixture
async def manager_2_embedding_workers(request):
    param = getattr(request, "param", {})
    workers = _create_workers(
        2, worker_type=WorkerType.TEXT2VEC.value, embeddings=param.get("embeddings", [])
    )
    async with _start_worker_manager(workers=workers, **param) as worker_manager:
        yield (worker_manager, workers)
