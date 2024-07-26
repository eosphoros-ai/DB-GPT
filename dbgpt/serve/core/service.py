from abc import ABC, abstractmethod
from typing import Generic, Optional

from dbgpt.component import BaseComponent, SystemApp
from dbgpt.core.awel.dag.dag_manager import DAGManager
from dbgpt.serve.core.config import BaseServeConfig
from dbgpt.storage.metadata._base_dao import REQ, RES, BaseDao, T


class BaseService(BaseComponent, Generic[T, REQ, RES], ABC):
    name = "dbgpt_serve_base_service"

    _dag_manager: Optional[DAGManager] = None
    _system_app: Optional[SystemApp] = None

    def __init__(self, system_app):
        super().__init__(system_app)
        self._system_app = system_app

    def init_app(self, system_app: SystemApp):
        """Initialize the service

        Args:
            system_app (SystemApp): The system app
        """
        self._system_app = system_app

    @property
    @abstractmethod
    def dao(self) -> BaseDao[T, REQ, RES]:
        """Returns the internal DAO."""

    @property
    @abstractmethod
    def config(self) -> BaseServeConfig:
        """Returns the internal ServeConfig."""

    def create(self, request: REQ) -> RES:
        """Create a new entity

        Args:
            request (REQ): The request

        Returns:
            RES: The response
        """
        return self.dao.create(request)

    @property
    def dag_manager(self) -> DAGManager:
        if self._dag_manager is None:
            raise ValueError("DAGManager is not initialized")
        return self._dag_manager

    def before_start(self):
        """Execute before the application starts"""
        # if not self._system_app
        self._dag_manager = DAGManager.get_instance(self._system_app)
