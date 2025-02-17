from contextlib import asynccontextmanager
from typing import Callable, Dict, Iterator, List, Optional, Tuple, Type

import pytest
import pytest_asyncio

from dbgpt.core import ModelMetadata, ModelOutput
from dbgpt.core.interface.parameter import (
    BaseDeployModelParameters,
)
from dbgpt.model.adapter.hf_adapter import HFLLMDeployModelParameters
from dbgpt.model.base import ModelInstance
from dbgpt.model.cluster.registry import EmbeddedModelRegistry, ModelRegistry
from dbgpt.model.cluster.worker.manager import (
    LocalWorkerManager,
    WorkerManager,
)
from dbgpt.model.cluster.worker_base import ModelWorker
from dbgpt.model.parameter import ModelWorkerParameters, WorkerType
from dbgpt.rag.embedding import CrossEncoderRerankEmbeddings
from dbgpt.rag.embedding.embeddings import HFEmbeddingDeployModelParameters


@pytest.fixture
def model_registry(request):
    return EmbeddedModelRegistry()


@pytest.fixture
def model_instance():
    return ModelInstance(
        model_name="test_model",
        host="192.168.1.1",
        port=5000,
    )


class MockModelWorker(ModelWorker):
    def __init__(
        self,
        model_parameters: BaseDeployModelParameters,
        worker_type: str = WorkerType.LLM.value,
        error_worker: bool = False,
        stop_error: bool = False,
        stream_messages: List[str] = None,
        embeddings: List[List[float]] = None,
    ) -> None:
        super().__init__()
        if not stream_messages:
            stream_messages = []
        if not embeddings:
            embeddings = []
        self.model_parameters = model_parameters
        self._worker_type = worker_type
        self.error_worker = error_worker
        self.stop_error = stop_error
        self.stream_messages = stream_messages
        self._embeddings = embeddings

    @property
    def model_name(self) -> str:
        return self.model_parameters.name

    def worker_type(self) -> WorkerType:
        return WorkerType.from_str(self._worker_type)

    def model_param_class(self) -> Type[BaseDeployModelParameters]:
        return self.model_parameters.__class__

    def load_worker(
        self, model_name: str, deploy_model_params: BaseDeployModelParameters, **kwargs
    ) -> None:
        pass

    def start(self, command_args: List[str] = None) -> None:
        if self.error_worker:
            raise Exception("Start worker error for mock")

    def stop(self) -> None:
        if self.stop_error:
            raise Exception("Stop worker error for mock")

    def generate_stream(self, params: Dict) -> Iterator[ModelOutput]:
        full_text = ""
        for msg in self.stream_messages:
            full_text += msg
            yield ModelOutput(text=full_text, error_code=0)

    def generate(self, params: Dict) -> ModelOutput:
        output = None
        for out in self.generate_stream(params):
            output = out
        return output

    def count_token(self, prompt: str) -> int:
        return len(prompt)

    def get_model_metadata(self, params: Dict) -> ModelMetadata:
        return ModelMetadata(
            model=self.model_parameters.name,
        )

    def embeddings(self, params: Dict) -> List[List[float]]:
        return self._embeddings


def _DEFAULT_GEN_WORKER_FUN(worker_type, worker_class):
    return MockModelWorker(
        HFLLMDeployModelParameters(name=_TEST_MODEL_NAME, path=_TEST_MODEL_PATH),
        worker_type=worker_type,
    )


class MockLocalWorkerManager(LocalWorkerManager):
    def __init__(
        self,
        gen_worker_fun: Callable[[Optional[str], Optional[str]], ModelWorker],
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self._gen_worker_fun = gen_worker_fun

    def _build_worker(
        self, worker_type: Optional[str], worker_class: Optional[str]
    ) -> ModelWorker:
        return self._gen_worker_fun(worker_type, worker_class)


_TEST_MODEL_NAME = "vicuna-13b-v1.5"
_TEST_MODEL_PATH = "/app/models/vicuna-13b-v1.5"

ClusterType = Tuple[WorkerManager, ModelRegistry]


def _new_worker_params(
    worker_type: str = WorkerType.LLM.value,
) -> ModelWorkerParameters:
    return ModelWorkerParameters(worker_type=worker_type)


def _create_workers(
    num_workers: int,
    error_worker: bool = False,
    stop_error: bool = False,
    worker_type: str = WorkerType.LLM.value,
    stream_messages: List[str] = None,
    embeddings: List[List[float]] = None,
    host: str = "127.0.0.1",
    start_port=8001,
) -> List[Tuple[ModelWorker, BaseDeployModelParameters, ModelInstance]]:
    workers = []
    for i in range(num_workers):
        model_name = f"test-model-name-{i}"
        model_path = f"test-model-path-{i}"
        if worker_type == WorkerType.LLM:
            model_parameters = HFLLMDeployModelParameters(
                name=model_name, path=model_path
            )
        elif worker_type == WorkerType.TEXT2VEC:
            model_parameters = HFEmbeddingDeployModelParameters(
                name=model_name, path=model_path
            )
        elif worker_type == WorkerType.RERANKER:
            model_parameters = CrossEncoderRerankEmbeddings(
                name=model_name, path=model_path
            )
        else:
            raise ValueError(f"Invalid worker type: {worker_type}")
        worker = MockModelWorker(
            model_parameters,
            worker_type=worker_type,
            error_worker=error_worker,
            stop_error=stop_error,
            stream_messages=stream_messages,
            embeddings=embeddings,
        )
        model_instance = ModelInstance(
            model_name=WorkerType.to_worker_key(model_name, worker_type),
            host=host,
            port=start_port + i,
            healthy=True,
        )
        workers.append((worker, model_parameters, model_instance))
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
    stream_messages = kwargs.get("stream_messages", [])
    embeddings = kwargs.get("embeddings", [])
    gen_worker_fun = kwargs.get("gen_worker_fun", _DEFAULT_GEN_WORKER_FUN)

    worker_manager = MockLocalWorkerManager(
        gen_worker_fun=gen_worker_fun,
        register_func=register_func,
        deregister_func=deregister_func,
        send_heartbeat_func=send_heartbeat_func,
        model_registry=model_registry,
    )

    for worker, deploy_params, model_instance in _create_workers(
        num_workers,
        error_worker,
        stop_error,
        stream_messages=stream_messages,
        embeddings=embeddings,
    ):
        worker_params = ModelWorkerParameters(
            worker_type=WorkerType.LLM.value,
        )
        worker_manager.add_worker(worker, worker_params, deploy_params)
    if workers:
        for worker, deploy_params, model_instance in workers:
            worker_params = ModelWorkerParameters(
                worker_type=worker.worker_type(),
            )
            worker_manager.add_worker(worker, worker_params, deploy_params)

    if start:
        await worker_manager.start()

    yield worker_manager
    if stop:
        await worker_manager.stop()


async def _create_model_registry(
    workers: List[Tuple[ModelWorker, ModelWorkerParameters, ModelInstance]],
) -> ModelRegistry:
    registry = EmbeddedModelRegistry()
    for _, _, inst in workers:
        assert await registry.register_instance(inst) is True
    return registry


@pytest_asyncio.fixture
async def manager_2_workers(request):
    param = getattr(request, "param", {})
    async with _start_worker_manager(num_workers=2, **param) as worker_manager:
        yield worker_manager


@pytest_asyncio.fixture
async def manager_with_2_workers(request):
    param = getattr(request, "param", {})
    workers = _create_workers(2, stream_messages=param.get("stream_messages", []))
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


@asynccontextmanager
async def _new_cluster(**kwargs) -> ClusterType:
    num_workers = kwargs.get("num_workers", 0)
    workers = _create_workers(
        num_workers, stream_messages=kwargs.get("stream_messages", [])
    )
    if "num_workers" in kwargs:
        del kwargs["num_workers"]
    registry = await _create_model_registry(
        workers,
    )
    async with _start_worker_manager(workers=workers, **kwargs) as worker_manager:
        yield (worker_manager, registry)


@pytest_asyncio.fixture
async def cluster_2_workers(request):
    param = getattr(request, "param", {})
    workers = _create_workers(2)
    registry = await _create_model_registry(workers)
    async with _start_worker_manager(workers=workers, **param) as worker_manager:
        yield (worker_manager, registry)
