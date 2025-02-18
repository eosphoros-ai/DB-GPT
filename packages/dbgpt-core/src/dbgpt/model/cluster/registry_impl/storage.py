import logging
import threading
import time
from concurrent.futures import Executor, ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from dbgpt.component import SystemApp
from dbgpt.core.interface.storage import (
    QuerySpec,
    ResourceIdentifier,
    StorageInterface,
    StorageItem,
)
from dbgpt.util.executor_utils import blocking_func_to_async

from ...base import ModelInstance
from ..registry import ModelRegistry

logger = logging.getLogger(__name__)


@dataclass
class ModelInstanceIdentifier(ResourceIdentifier):
    identifier_split: str = field(default="___$$$$___", init=False)
    model_name: str
    host: str
    port: int

    def __post_init__(self):
        """Post init method."""
        if self.model_name is None:
            raise ValueError("model_name is required.")
        if self.host is None:
            raise ValueError("host is required.")
        if self.port is None:
            raise ValueError("port is required.")

        if any(
            self.identifier_split in key
            for key in [self.model_name, self.host, str(self.port)]
            if key is not None
        ):
            raise ValueError(
                f"identifier_split {self.identifier_split} is not allowed in "
                f"model_name, host, port."
            )

    @property
    def str_identifier(self) -> str:
        """Return the string identifier of the identifier."""
        return self.identifier_split.join(
            key
            for key in [
                self.model_name,
                self.host,
                str(self.port),
            ]
            if key is not None
        )

    def to_dict(self) -> Dict:
        """Convert the identifier to a dict.

        Returns:
            Dict: The dict of the identifier.
        """
        return {
            "model_name": self.model_name,
            "host": self.host,
            "port": self.port,
        }


@dataclass
class ModelInstanceStorageItem(StorageItem):
    model_name: str
    host: str
    port: int
    weight: Optional[float] = 1.0
    check_healthy: Optional[bool] = True
    healthy: Optional[bool] = False
    enabled: Optional[bool] = True
    prompt_template: Optional[str] = None
    last_heartbeat: Optional[datetime] = None
    _identifier: ModelInstanceIdentifier = field(init=False)

    def __post_init__(self):
        """Post init method."""
        # Convert last_heartbeat to datetime if it's a timestamp
        if isinstance(self.last_heartbeat, (int, float)):
            self.last_heartbeat = datetime.fromtimestamp(self.last_heartbeat)

        self._identifier = ModelInstanceIdentifier(
            model_name=self.model_name,
            host=self.host,
            port=self.port,
        )

    @property
    def identifier(self) -> ModelInstanceIdentifier:
        return self._identifier

    def merge(self, other: "StorageItem") -> None:
        if not isinstance(other, ModelInstanceStorageItem):
            raise ValueError(f"Cannot merge with {type(other)}")
        self.from_object(other)

    def to_dict(self) -> Dict:
        last_heartbeat = self.last_heartbeat.timestamp()
        return {
            "model_name": self.model_name,
            "host": self.host,
            "port": self.port,
            "weight": self.weight,
            "check_healthy": self.check_healthy,
            "healthy": self.healthy,
            "enabled": self.enabled,
            "prompt_template": self.prompt_template,
            "last_heartbeat": last_heartbeat,
        }

    def from_object(self, item: "ModelInstanceStorageItem") -> None:
        """Build the item from another item."""
        self.model_name = item.model_name
        self.host = item.host
        self.port = item.port
        self.weight = item.weight
        self.check_healthy = item.check_healthy
        self.healthy = item.healthy
        self.enabled = item.enabled
        self.prompt_template = item.prompt_template
        self.last_heartbeat = item.last_heartbeat

    @classmethod
    def from_model_instance(cls, instance: ModelInstance) -> "ModelInstanceStorageItem":
        return cls(
            model_name=instance.model_name,
            host=instance.host,
            port=instance.port,
            weight=instance.weight,
            check_healthy=instance.check_healthy,
            healthy=instance.healthy,
            enabled=instance.enabled,
            prompt_template=instance.prompt_template,
            last_heartbeat=instance.last_heartbeat,
        )

    @classmethod
    def to_model_instance(cls, item: "ModelInstanceStorageItem") -> ModelInstance:
        return ModelInstance(
            model_name=item.model_name,
            host=item.host,
            port=item.port,
            weight=item.weight,
            check_healthy=item.check_healthy,
            healthy=item.healthy,
            enabled=item.enabled,
            prompt_template=item.prompt_template,
            last_heartbeat=item.last_heartbeat,
        )


class StorageModelRegistry(ModelRegistry):
    def __init__(
        self,
        storage: StorageInterface,
        system_app: SystemApp | None = None,
        executor: Optional[Executor] = None,
        heartbeat_interval_secs: float | int = 60,
        heartbeat_timeout_secs: int = 120,
    ):
        super().__init__(system_app)
        self._storage = storage
        self._executor = executor or ThreadPoolExecutor(max_workers=2)
        self.heartbeat_interval_secs = heartbeat_interval_secs
        self.heartbeat_timeout_secs = heartbeat_timeout_secs
        self.heartbeat_thread = threading.Thread(target=self._heartbeat_checker)
        self.heartbeat_thread.daemon = True
        self.heartbeat_thread.start()

    @classmethod
    def from_url(
        cls,
        db_url: str,
        db_name: str,
        engine_args: Optional[Dict[str, Any]] = None,
        try_to_create_db: bool = False,
        **kwargs,
    ) -> "StorageModelRegistry":
        from dbgpt.storage.metadata.db_manager import DatabaseManager, initialize_db
        from dbgpt.storage.metadata.db_storage import SQLAlchemyStorage
        from dbgpt.util.serialization.json_serialization import JsonSerializer

        from .db_storage import ModelInstanceEntity, ModelInstanceItemAdapter

        if engine_args is None:
            engine_args = {
                "pool_size": 5,
                "max_overflow": 10,
                "pool_timeout": 30,
                "pool_recycle": 3600,
                "pool_pre_ping": True,
            }

        db: DatabaseManager = initialize_db(
            db_url, db_name, engine_args, try_to_create_db=try_to_create_db
        )
        storage_adapter = ModelInstanceItemAdapter()
        serializer = JsonSerializer()
        storage = SQLAlchemyStorage(
            db,
            ModelInstanceEntity,
            storage_adapter,
            serializer,
        )
        return cls(storage, **kwargs)

    async def _get_instances_by_model(
        self, model_name: str, host: str, port: int, healthy_only: bool = False
    ) -> Tuple[List[ModelInstanceStorageItem], List[ModelInstanceStorageItem]]:
        query_spec = QuerySpec(conditions={"model_name": model_name})
        # Query all instances of the model
        instances = await blocking_func_to_async(
            self._executor, self._storage.query, query_spec, ModelInstanceStorageItem
        )
        if healthy_only:
            instances = [ins for ins in instances if ins.healthy is True]
        exist_ins = [ins for ins in instances if ins.host == host and ins.port == port]
        return instances, exist_ins

    def _heartbeat_checker(self):
        while True:
            all_instances: List[ModelInstanceStorageItem] = self._storage.query(
                QuerySpec(conditions={}), ModelInstanceStorageItem
            )
            for instance in all_instances:
                if (
                    instance.check_healthy
                    and datetime.now() - instance.last_heartbeat
                    > timedelta(seconds=self.heartbeat_timeout_secs)
                ):
                    instance.healthy = False
                    self._storage.update(instance)
            time.sleep(self.heartbeat_interval_secs)

    async def register_instance(self, instance: ModelInstance) -> bool:
        model_name = instance.model_name.strip()
        host = instance.host.strip()
        port = instance.port
        _, exist_ins = await self._get_instances_by_model(
            model_name, host, port, healthy_only=False
        )
        if exist_ins:
            # Exist instances, just update the instance
            # One exist instance at most
            ins: ModelInstanceStorageItem = exist_ins[0]
            # Update instance
            ins.weight = instance.weight
            ins.healthy = True
            ins.prompt_template = instance.prompt_template
            ins.last_heartbeat = datetime.now()
            await blocking_func_to_async(self._executor, self._storage.update, ins)
        else:
            # No exist instance, save the new instance
            new_inst = ModelInstanceStorageItem.from_model_instance(instance)
            new_inst.healthy = True
            new_inst.last_heartbeat = datetime.now()
            await blocking_func_to_async(self._executor, self._storage.save, new_inst)
        return True

    async def deregister_instance(self, instance: ModelInstance) -> bool:
        """Deregister a model instance.

        If the instance exists, set the instance as unhealthy, nothing to do if the
        instance does not exist.

        Args:
            instance (ModelInstance): The instance to deregister.
        """
        model_name = instance.model_name.strip()
        host = instance.host.strip()
        port = instance.port
        _, exist_ins = await self._get_instances_by_model(
            model_name, host, port, healthy_only=False
        )
        if exist_ins:
            ins = exist_ins[0]
            ins.healthy = False
            if instance.remove_from_registry:
                logger.info(
                    f"Remove instance {model_name}@{host}:{port} from registry."
                )
                await blocking_func_to_async(
                    self._executor, self._storage.delete, ins.identifier
                )
            else:
                logger.info(f"Set instance {model_name}@{host}:{port} as unhealthy.")
                await blocking_func_to_async(self._executor, self._storage.update, ins)
        return True

    async def get_all_instances(
        self, model_name: str, healthy_only: bool = False
    ) -> List[ModelInstance]:
        """Get all instances of a model(Async).

        Args:
            model_name (str): The model name.
            healthy_only (bool): Whether only get healthy instances. Defaults to False.
        """
        return await blocking_func_to_async(
            self._executor, self.sync_get_all_instances, model_name, healthy_only
        )

    def sync_get_all_instances(
        self, model_name: str, healthy_only: bool = False
    ) -> List[ModelInstance]:
        """Get all instances of a model.

        Args:
            model_name (str): The model name.
            healthy_only (bool): Whether only get healthy instances. Defaults to False.

        Returns:
            List[ModelInstance]: The list of instances.
        """
        instances = self._storage.query(
            QuerySpec(conditions={"model_name": model_name}), ModelInstanceStorageItem
        )
        if healthy_only:
            instances = [ins for ins in instances if ins.healthy is True]
        return [ModelInstanceStorageItem.to_model_instance(ins) for ins in instances]

    async def get_all_model_instances(
        self, healthy_only: bool = False
    ) -> List[ModelInstance]:
        """Get all model instances.

        Args:
            healthy_only (bool): Whether only get healthy instances. Defaults to False.

        Returns:
            List[ModelInstance]: The list of instances.
        """
        all_instances = await blocking_func_to_async(
            self._executor,
            self._storage.query,
            QuerySpec(conditions={}),
            ModelInstanceStorageItem,
        )
        if healthy_only:
            all_instances = [ins for ins in all_instances if ins.healthy is True]
        return [
            ModelInstanceStorageItem.to_model_instance(ins) for ins in all_instances
        ]

    async def send_heartbeat(self, instance: ModelInstance) -> bool:
        """Receive heartbeat from model instance.

        Update the last heartbeat time of the instance. If the instance does not exist,
        register the instance.

        Args:
            instance (ModelInstance): The instance to send heartbeat.

        Returns:
            bool: True if the heartbeat is received successfully.
        """
        model_name = instance.model_name.strip()
        host = instance.host.strip()
        port = instance.port
        _, exist_ins = await self._get_instances_by_model(
            model_name, host, port, healthy_only=False
        )
        if not exist_ins:
            # register new instance from heartbeat
            await self.register_instance(instance)
            return True
        else:
            ins = exist_ins[0]
            ins.last_heartbeat = datetime.now()
            ins.healthy = True
            await blocking_func_to_async(self._executor, self._storage.update, ins)
            return True
