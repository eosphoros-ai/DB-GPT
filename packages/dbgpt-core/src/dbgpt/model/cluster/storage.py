"""Model storage module.

Persist the model information to the storage.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from dbgpt.core import QuerySpec, ResourceIdentifier, StorageInterface, StorageItem

from ..parameter import WorkerType
from .base import WorkerStartupRequest


@dataclass
class ModelStorageIdentifier(ResourceIdentifier):
    identifier_split: str = field(default="___$$$$___", init=False)
    model: str
    worker_type: str
    sys_code: Optional[str] = None
    user_name: Optional[str] = None

    def __post_init__(self):
        """Post init method."""
        if self.model is None:
            raise ValueError("model name is required.")
        if self.worker_type is None:
            raise ValueError("worker type is required.")

        if any(
            self.identifier_split in key
            for key in [
                self.model,
                self.sys_code,
                self.user_name,
                self.worker_type,
            ]
            if key is not None
        ):
            raise ValueError(
                f"identifier_split {self.identifier_split} is not allowed in "
                f"model, sys_code, user_name, worker_type"
            )

    @property
    def str_identifier(self) -> str:
        """Return the string identifier of the identifier."""
        keys = [
            self.model,
            self.worker_type,
            self.sys_code or "",
            self.user_name or "",
        ]
        return self.identifier_split.join(keys)

    def to_dict(self) -> Dict:
        """Convert the identifier to a dict.

        Returns:
            Dict: The dict of the identifier.
        """
        return {
            "model": self.model,
            "worker_type": self.worker_type,
            "sys_code": self.sys_code,
            "user_name": self.user_name,
        }


@dataclass
class ModelStorageItem(StorageItem):
    """Model storage item."""

    host: str = field(metadata={"help": "The host of the worker"})
    port: int = field(metadata={"help": "The port of the worker"})
    model: str = field(metadata={"help": "The model name"})
    provider: str = field(metadata={"help": "The provider of the model"})
    worker_type: str = field(
        metadata={"help": "The worker type of the model, e.g. llm, tex2vec, reranker"}
    )
    enabled: bool = field(
        default=True,
        metadata={
            "help": "Whether the model is enabled, if it is enabled, it will be started"
            " when the system starts"
        },
    )
    worker_name: Optional[str] = field(
        default=None, metadata={"help": "The name of the worker"}
    )
    params: Dict[str, Any] = field(
        default_factory=dict, metadata={"help": "The parameters of the model"}
    )
    description: Optional[str] = field(
        default=None, metadata={"help": "The description of the model"}
    )
    sys_code: Optional[str] = field(
        default=None,
        metadata={"help": "The system code for the worker, used for authentication"},
    )
    user_name: Optional[str] = field(
        default=None,
        metadata={"help": "The user name for the worker, used for authentication"},
    )

    _identifier: ModelStorageIdentifier = field(init=False)

    def __post_init__(self):
        """Post init method."""
        self._identifier = ModelStorageIdentifier(
            model=self.model,
            worker_type=self.worker_type,
            sys_code=self.sys_code,
            user_name=self.user_name,
        )

    @property
    def identifier(self) -> ResourceIdentifier:
        return self._identifier

    def merge(self, other: "ModelStorageItem") -> None:
        """Merge with another storage variables."""
        if not isinstance(other, ModelStorageItem):
            raise ValueError(f"Cannot merge with {type(other)}")
        self.from_object(other)

    def to_dict(self) -> Dict:
        return {
            "host": self.host,
            "port": self.port,
            "model": self.model,
            "provider": self.provider,
            "worker_type": self.worker_type,
            "enabled": self.enabled,
            "worker_name": self.worker_name,
            "params": self.params,
            "description": self.description,
            "sys_code": self.sys_code,
            "user_name": self.user_name,
        }

    def from_object(self, other: "ModelStorageItem") -> None:
        """Copy the values from another object."""
        self.host = other.host
        self.port = other.port
        self.provider = other.provider
        self.worker_type = other.worker_type
        self.enabled = other.enabled
        self.worker_name = other.worker_name
        self.params = other.params
        self.description = other.description
        self.sys_code = other.sys_code if other.sys_code else self.sys_code
        self.user_name = other.user_name if other.user_name else self.user_name

    @classmethod
    def from_startup_req(cls, request: WorkerStartupRequest) -> "ModelStorageItem":
        """Create a model storage item from a worker startup request."""
        return cls(
            host=request.host,
            port=request.port,
            model=request.model,
            provider=request.params.get("provider"),
            worker_type=request.worker_type.value,
            enabled=True,
            worker_name=request.worker_name,
            params=request.params,
            description=request.params.get("description"),
            sys_code=request.sys_code,
            user_name=request.user_name,
        )

    def to_startup_req(self) -> WorkerStartupRequest:
        """Convert the model storage item to a worker startup request."""
        return WorkerStartupRequest(
            host=self.host,
            port=self.port,
            model=self.model,
            worker_type=WorkerType.from_str(self.worker_type),
            params=self.params,
            worker_name=self.worker_name,
            sys_code=self.sys_code,
            user_name=self.user_name,
        )


class ModelStorage:
    def __init__(self, storage: StorageInterface):
        self._storage = storage

    def all_models(self, enabled: bool = True) -> List[WorkerStartupRequest]:
        """Get all stored models.

        Returns:
            List[WorkerStartupRequest]: The list of worker startup requests.
        """
        models = self._storage.query(
            QuerySpec(conditions={"enabled": enabled}), ModelStorageItem
        )
        return [model.to_startup_req() for model in models]

    def query_models(
        self,
        model_name: str,
        worker_type: str,
        sys_code: Optional[str] = None,
        user_name: Optional[str] = None,
        enabled: Optional[bool] = True,
        **kwargs,
    ) -> List[WorkerStartupRequest]:
        """Query models by the specified conditions.

        Args:
            model_name (str): The model name.
            worker_type (str): The worker type.
            sys_code (Optional[str], optional): The system code. Defaults to None.
            user_name (Optional[str], optional): The user name. Defaults to None.
            enabled (Optional[bool], optional): Whether the model is enabled. Defaults
                to True.

        Returns:
            List[WorkerStartupRequest]: The list of worker startup requests.
        """
        conditions = {
            "model": model_name,
            "worker_type": worker_type,
            "sys_code": sys_code,
            "user_name": user_name,
            "enabled": enabled,
        }
        conditions.update(kwargs)
        models = self._storage.query(QuerySpec(conditions=conditions), ModelStorageItem)
        return [model.to_startup_req() for model in models]

    def save_or_update(
        self, request: WorkerStartupRequest, enabled: bool = True
    ) -> None:
        """Save a model to the storage.

        Args:
            request (WorkerStartupRequest): The worker startup request.
            enabled (bool, optional): Whether the model is enabled. Defaults to True.
        """
        model = ModelStorageItem.from_startup_req(request)
        model.enabled = enabled
        self._storage.save_or_update(model)

    def delete(self, identifier: ModelStorageIdentifier) -> None:
        """Delete a model from the storage.

        Args:
            identifier (ModelStorageIdentifier): The identifier of the model.
        """
        self._storage.delete(identifier)
