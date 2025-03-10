import asyncio
from abc import ABC, abstractmethod
from concurrent.futures import Future
from dataclasses import dataclass
from datetime import datetime
from typing import AsyncIterator, Callable, Dict, List, Optional

from dbgpt.component import BaseComponent, ComponentType, SystemApp
from dbgpt.core import ModelMetadata, ModelOutput
from dbgpt.core.interface.parameter import BaseDeployModelParameters
from dbgpt.model.base import WorkerApplyOutput, WorkerSupportedModel
from dbgpt.model.cluster.base import WorkerApplyRequest, WorkerStartupRequest
from dbgpt.model.cluster.worker_base import ModelWorker
from dbgpt.model.parameter import ModelWorkerParameters
from dbgpt.util.parameter_utils import ParameterDescription


@dataclass
class WorkerRunData:
    host: str
    port: int
    worker_type: str
    worker_key: str
    worker: ModelWorker
    worker_params: ModelWorkerParameters
    model_params: BaseDeployModelParameters
    stop_event: asyncio.Event
    semaphore: asyncio.Semaphore = None
    command_args: List[str] = None
    _heartbeat_future: Optional[Future] = None
    _last_heartbeat: Optional[datetime] = None
    # Remove from the registry, Just for stop worker
    remove_from_registry: bool = False

    def _to_print_key(self):
        model_name = self.model_params.name
        provider = self.model_params.provider
        host = self.host
        port = self.port
        return f"model {model_name}@{provider}({host}:{port})"

    @property
    def stopped(self):
        """Check if the worker is stopped""" ""
        return self.stop_event.is_set()


class WorkerManager(ABC):
    @abstractmethod
    async def start(self):
        """Start worker manager

        Raises:
            Exception: if start worker manager not successfully
        """

    @abstractmethod
    async def stop(self, ignore_exception: bool = False):
        """Stop worker manager"""

    @abstractmethod
    def after_start(self, listener: Callable[["WorkerManager"], None]):
        """Add a listener after WorkerManager startup"""

    @abstractmethod
    async def get_model_instances(
        self, worker_type: str, model_name: str, healthy_only: bool = True
    ) -> List[WorkerRunData]:
        """Asynchronous get model instances by worker type and model name"""

    @abstractmethod
    async def get_all_model_instances(
        self, worker_type: str, healthy_only: bool = True
    ) -> List[WorkerRunData]:
        """Asynchronous get all model instances

        Args:
            worker_type (str): worker type
            healthy_only (bool, optional): only return healthy instances.
                Defaults to True.

        Returns:
            List[WorkerRunData]: worker run data list
        """

    @abstractmethod
    def sync_get_model_instances(
        self, worker_type: str, model_name: str, healthy_only: bool = True
    ) -> List[WorkerRunData]:
        """Get model instances by worker type and model name"""

    @abstractmethod
    async def select_one_instance(
        self, worker_type: str, model_name: str, healthy_only: bool = True
    ) -> WorkerRunData:
        """Asynchronous select one instance"""

    @abstractmethod
    def sync_select_one_instance(
        self, worker_type: str, model_name: str, healthy_only: bool = True
    ) -> WorkerRunData:
        """Select one instance"""

    @abstractmethod
    async def supported_models(self) -> List[WorkerSupportedModel]:
        """List supported models"""

    @abstractmethod
    async def model_startup(self, startup_req: WorkerStartupRequest):
        """Create and start a model instance"""

    @abstractmethod
    async def model_shutdown(self, shutdown_req: WorkerStartupRequest):
        """Shutdown model instance"""

    @abstractmethod
    async def generate_stream(
        self, params: Dict, **kwargs
    ) -> AsyncIterator[ModelOutput]:
        """Generate stream result, chat scene"""

    @abstractmethod
    async def generate(self, params: Dict) -> ModelOutput:
        """Generate non stream result"""

    @abstractmethod
    async def embeddings(self, params: Dict) -> List[List[float]]:
        """Asynchronous embed input"""

    @abstractmethod
    def sync_embeddings(self, params: Dict) -> List[List[float]]:
        """Embed input

        This function may be passed to a third-party system call for synchronous calls.
        We must provide a synchronous version.
        """

    @abstractmethod
    async def count_token(self, params: Dict) -> int:
        """Count token of prompt

        Args:
            params (Dict): parameters, eg.
                {"prompt": "hello", "model": "vicuna-13b-v1.5"}

        Returns:
            int: token count
        """

    @abstractmethod
    async def get_model_metadata(self, params: Dict) -> ModelMetadata:
        """Get model metadata

        Args:
            params (Dict): parameters, eg. {"model": "vicuna-13b-v1.5"}
        """

    @abstractmethod
    async def worker_apply(self, apply_req: WorkerApplyRequest) -> WorkerApplyOutput:
        """Worker apply"""

    @abstractmethod
    async def parameter_descriptions(
        self, worker_type: str, model_name: str
    ) -> List[ParameterDescription]:
        """Get parameter descriptions of model"""


class WorkerManagerFactory(BaseComponent, ABC):
    name = ComponentType.WORKER_MANAGER_FACTORY.value

    def init_app(self, system_app: SystemApp):
        pass

    @abstractmethod
    def create(self) -> WorkerManager:
        """Create worker manager"""
