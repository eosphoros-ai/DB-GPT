import random
import threading
import time
import logging
from abc import ABC, abstractmethod
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import itertools

from dbgpt.component import BaseComponent, ComponentType, SystemApp
from dbgpt.model.base import ModelInstance


logger = logging.getLogger(__name__)


class ModelRegistry(BaseComponent, ABC):
    """
    Abstract base class for a model registry. It provides an interface
    for registering, deregistering, fetching instances, and sending heartbeats
    for instances.
    """

    name = ComponentType.MODEL_REGISTRY

    def __init__(self, system_app: SystemApp | None = None):
        self.system_app = system_app
        super().__init__(system_app)

    def init_app(self, system_app: SystemApp):
        """Initialize the component with the main application."""
        self.system_app = system_app

    @abstractmethod
    async def register_instance(self, instance: ModelInstance) -> bool:
        """
        Register a given model instance.

        Args:
        - instance (ModelInstance): The instance of the model to register.

        Returns:
        - bool: True if registration is successful, False otherwise.
        """
        pass

    @abstractmethod
    async def deregister_instance(self, instance: ModelInstance) -> bool:
        """
        Deregister a given model instance.

        Args:
        - instance (ModelInstance): The instance of the model to deregister.

        Returns:
        - bool: True if deregistration is successful, False otherwise.
        """

    @abstractmethod
    async def get_all_instances(
        self, model_name: str, healthy_only: bool = False
    ) -> List[ModelInstance]:
        """
        Fetch all instances of a given model. Optionally, fetch only the healthy instances.

        Args:
        - model_name (str): Name of the model to fetch instances for.
        - healthy_only (bool, optional): If set to True, fetches only the healthy instances.
                                         Defaults to False.

        Returns:
        - List[ModelInstance]: A list of instances for the given model.
        """

    @abstractmethod
    def sync_get_all_instances(
        self, model_name: str, healthy_only: bool = False
    ) -> List[ModelInstance]:
        """Fetch all instances of a given model. Optionally, fetch only the healthy instances."""

    @abstractmethod
    async def get_all_model_instances(
        self, healthy_only: bool = False
    ) -> List[ModelInstance]:
        """
        Fetch all instances of all models, Optionally, fetch only the healthy instances.

        Returns:
        - List[ModelInstance]: A list of instances for the all models.
        """

    async def select_one_health_instance(self, model_name: str) -> ModelInstance:
        """
        Selects one healthy and enabled instance for a given model.

        Args:
        - model_name (str): Name of the model.

        Returns:
        - ModelInstance: One randomly selected healthy and enabled instance, or None if no such instance exists.
        """
        instances = await self.get_all_instances(model_name, healthy_only=True)
        instances = [i for i in instances if i.enabled]
        if not instances:
            return None
        return random.choice(instances)

    @abstractmethod
    async def send_heartbeat(self, instance: ModelInstance) -> bool:
        """
        Send a heartbeat for a given model instance. This can be used to
        verify if the instance is still alive and functioning.

        Args:
        - instance (ModelInstance): The instance of the model to send a heartbeat for.

        Returns:
        - bool: True if heartbeat is successful, False otherwise.
        """


class EmbeddedModelRegistry(ModelRegistry):
    def __init__(
        self,
        system_app: SystemApp | None = None,
        heartbeat_interval_secs: int = 60,
        heartbeat_timeout_secs: int = 120,
    ):
        super().__init__(system_app)
        self.registry: Dict[str, List[ModelInstance]] = defaultdict(list)
        self.heartbeat_interval_secs = heartbeat_interval_secs
        self.heartbeat_timeout_secs = heartbeat_timeout_secs
        self.heartbeat_thread = threading.Thread(target=self._heartbeat_checker)
        self.heartbeat_thread.daemon = True
        self.heartbeat_thread.start()

    def _get_instances(
        self, model_name: str, host: str, port: int, healthy_only: bool = False
    ) -> Tuple[List[ModelInstance], List[ModelInstance]]:
        instances = self.registry[model_name]
        if healthy_only:
            instances = [ins for ins in instances if ins.healthy == True]
        exist_ins = [ins for ins in instances if ins.host == host and ins.port == port]
        return instances, exist_ins

    def _heartbeat_checker(self):
        while True:
            for instances in self.registry.values():
                for instance in instances:
                    if (
                        instance.check_healthy
                        and datetime.now() - instance.last_heartbeat
                        > timedelta(seconds=self.heartbeat_timeout_secs)
                    ):
                        instance.healthy = False
            time.sleep(self.heartbeat_interval_secs)

    async def register_instance(self, instance: ModelInstance) -> bool:
        model_name = instance.model_name.strip()
        host = instance.host.strip()
        port = instance.port

        instances, exist_ins = self._get_instances(
            model_name, host, port, healthy_only=False
        )
        if exist_ins:
            # One exist instance at most
            ins = exist_ins[0]
            # Update instance
            ins.weight = instance.weight
            ins.healthy = True
            ins.prompt_template = instance.prompt_template
            ins.last_heartbeat = datetime.now()
        else:
            instance.healthy = True
            instance.last_heartbeat = datetime.now()
            instances.append(instance)
        return True

    async def deregister_instance(self, instance: ModelInstance) -> bool:
        model_name = instance.model_name.strip()
        host = instance.host.strip()
        port = instance.port
        _, exist_ins = self._get_instances(model_name, host, port, healthy_only=False)
        if exist_ins:
            ins = exist_ins[0]
            ins.healthy = False
        return True

    async def get_all_instances(
        self, model_name: str, healthy_only: bool = False
    ) -> List[ModelInstance]:
        return self.sync_get_all_instances(model_name, healthy_only)

    def sync_get_all_instances(
        self, model_name: str, healthy_only: bool = False
    ) -> List[ModelInstance]:
        instances = self.registry[model_name]
        if healthy_only:
            instances = [ins for ins in instances if ins.healthy == True]
        return instances

    async def get_all_model_instances(
        self, healthy_only: bool = False
    ) -> List[ModelInstance]:
        logger.debug("Current registry metadata:\n{self.registry}")
        instances = list(itertools.chain(*self.registry.values()))
        if healthy_only:
            instances = [ins for ins in instances if ins.healthy == True]
        return instances

    async def send_heartbeat(self, instance: ModelInstance) -> bool:
        _, exist_ins = self._get_instances(
            instance.model_name, instance.host, instance.port, healthy_only=False
        )
        if not exist_ins:
            # register new install from heartbeat
            await self.register_instance(instance)
            return True

        ins = exist_ins[0]
        ins.last_heartbeat = datetime.now()
        ins.healthy = True
        return True
