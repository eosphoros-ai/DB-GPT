import random
import threading
import time
from abc import ABC, abstractmethod
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Tuple

from pilot.model.base import ModelInstance


class ModelRegistry(ABC):
    """
    Abstract base class for a model registry. It provides an interface
    for registering, deregistering, fetching instances, and sending heartbeats
    for instances.
    """

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
        self, heartbeat_interval_secs: int = 60, heartbeat_timeout_secs: int = 120
    ):
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
        print(self.registry)
        instances = self.registry[model_name]
        if healthy_only:
            instances = [ins for ins in instances if ins.healthy == True]
        return instances

    async def send_heartbeat(self, instance: ModelInstance) -> bool:
        _, exist_ins = self._get_instances(
            instance.model_name, instance.host, instance.port, healthy_only=False
        )
        if not exist_ins:
            return False

        ins = exist_ins[0]
        ins.last_heartbeat = datetime.now()
        ins.healthy = True
        return True


from pilot.utils.api_utils import _api_remote as api_remote


class ModelRegistryClient(ModelRegistry):
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url

    @api_remote(path="/api/controller/models", method="POST")
    async def register_instance(self, instance: ModelInstance) -> bool:
        pass

    @api_remote(path="/api/controller/models", method="DELETE")
    async def deregister_instance(self, instance: ModelInstance) -> bool:
        pass

    @api_remote(path="/api/controller/models")
    async def get_all_instances(
        self, model_name: str, healthy_only: bool = False
    ) -> List[ModelInstance]:
        pass

    @api_remote(path="/api/controller/models")
    async def select_one_health_instance(self, model_name: str) -> ModelInstance:
        instances = await self.get_all_instances(model_name, healthy_only=True)
        instances = [i for i in instances if i.enabled]
        if not instances:
            return None
        return random.choice(instances)

    @api_remote(path="/api/controller/heartbeat", method="POST")
    async def send_heartbeat(self, instance: ModelInstance) -> bool:
        pass
