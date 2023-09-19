import asyncio
from dataclasses import dataclass
from typing import List, Optional, Dict, Iterator, Callable
from abc import ABC, abstractmethod
from datetime import datetime
from concurrent.futures import Future
from pilot.component import BaseComponent, ComponentType, SystemApp
from pilot.model.base import WorkerSupportedModel, ModelOutput, WorkerApplyOutput
from pilot.model.cluster.worker_base import ModelWorker
from pilot.model.cluster.base import WorkerStartupRequest, WorkerApplyRequest
from pilot.model.parameter import ModelWorkerParameters, ModelParameters
from pilot.utils.parameter_utils import ParameterDescription


@dataclass
class WorkerRunData:
    host: str
    port: int
    worker_key: str
    worker: ModelWorker
    worker_params: ModelWorkerParameters
    model_params: ModelParameters
    stop_event: asyncio.Event
    semaphore: asyncio.Semaphore = None
    command_args: List[str] = None
    _heartbeat_future: Optional[Future] = None
    _last_heartbeat: Optional[datetime] = None


class WorkerManager(ABC):
    @abstractmethod
    async def start(self):
        """Start worker manager"""

    @abstractmethod
    async def stop(self):
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
    async def model_startup(self, startup_req: WorkerStartupRequest) -> bool:
        """Create and start a model instance"""

    @abstractmethod
    async def model_shutdown(self, shutdown_req: WorkerStartupRequest) -> bool:
        """Shutdown model instance"""

    @abstractmethod
    async def generate_stream(self, params: Dict, **kwargs) -> Iterator[ModelOutput]:
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
