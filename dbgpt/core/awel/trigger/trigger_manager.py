"""Trigger manager for AWEL.

After DB-GPT started, the trigger manager will be initialized and register all triggers
"""
import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Dict, Optional

from dbgpt.component import BaseComponent, ComponentType, SystemApp

from .base import Trigger

if TYPE_CHECKING:
    from fastapi import APIRouter


logger = logging.getLogger(__name__)


class TriggerManager(ABC):
    """Base class for trigger manager."""

    @abstractmethod
    def register_trigger(self, trigger: Any) -> None:
        """Register a trigger to current manager."""

    def keep_running(self) -> bool:
        """Whether keep running.

        Returns:
            bool: Whether keep running, True means keep running, False means stop.
        """
        return False


class HttpTriggerManager(TriggerManager):
    """Http trigger manager.

    Register all http triggers to a router.
    """

    def __init__(
        self,
        router: Optional["APIRouter"] = None,
        router_prefix: str = "/api/v1/awel/trigger",
    ) -> None:
        """Initialize a HttpTriggerManager.

        Args:
            router (Optional["APIRouter"], optional): The router. Defaults to None.
            If None, will create a new FastAPI router.
            router_prefix (str, optional): The router prefix. Defaults
            to "/api/v1/awel/trigger".
        """
        if not router:
            from fastapi import APIRouter

            router = APIRouter()
        self._router_prefix = router_prefix
        self._router = router
        self._trigger_map: Dict[str, Trigger] = {}

    def register_trigger(self, trigger: Any) -> None:
        """Register a trigger to current manager."""
        from .http_trigger import HttpTrigger

        if not isinstance(trigger, HttpTrigger):
            raise ValueError(f"Current trigger {trigger} not an object of HttpTrigger")
        trigger_id = trigger.node_id
        if trigger_id not in self._trigger_map:
            trigger.mount_to_router(self._router)
            self._trigger_map[trigger_id] = trigger

    def _init_app(self, system_app: SystemApp):
        if not self.keep_running():
            return
        logger.info(
            f"Include router {self._router} to prefix path {self._router_prefix}"
        )
        app = system_app.app
        if not app:
            raise RuntimeError("System app not initialized")
        app.include_router(self._router, prefix=self._router_prefix, tags=["AWEL"])

    def keep_running(self) -> bool:
        """Whether keep running.

        Returns:
            bool: Whether keep running, True means keep running, False means stop.
        """
        return len(self._trigger_map) > 0


class DefaultTriggerManager(TriggerManager, BaseComponent):
    """Default trigger manager for AWEL.

    Manage all trigger managers. Just support http trigger now.
    """

    name = ComponentType.AWEL_TRIGGER_MANAGER

    def __init__(self, system_app: SystemApp | None = None):
        """Initialize a DefaultTriggerManager."""
        self.system_app = system_app
        self.http_trigger = HttpTriggerManager()
        super().__init__(None)

    def init_app(self, system_app: SystemApp):
        """Initialize the trigger manager."""
        self.system_app = system_app

    def register_trigger(self, trigger: Any) -> None:
        """Register a trigger to current manager."""
        from .http_trigger import HttpTrigger

        if isinstance(trigger, HttpTrigger):
            logger.info(f"Register trigger {trigger}")
            self.http_trigger.register_trigger(trigger)
        else:
            raise ValueError(f"Unsupport trigger: {trigger}")

    def after_register(self) -> None:
        """After register, init the trigger manager."""
        if self.system_app:
            self.http_trigger._init_app(self.system_app)

    def keep_running(self) -> bool:
        """Whether keep running.

        Returns:
            bool: Whether keep running, True means keep running, False means stop.
        """
        return self.http_trigger.keep_running()
