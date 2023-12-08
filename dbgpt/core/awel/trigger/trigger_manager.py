from abc import ABC, abstractmethod
from typing import Any, TYPE_CHECKING, Optional
import logging

if TYPE_CHECKING:
    from fastapi import APIRouter

from dbgpt.component import SystemApp, BaseComponent, ComponentType

logger = logging.getLogger(__name__)


class TriggerManager(ABC):
    @abstractmethod
    def register_trigger(self, trigger: Any) -> None:
        """ "Register a trigger to current manager"""


class HttpTriggerManager(TriggerManager):
    def __init__(
        self,
        router: Optional["APIRouter"] = None,
        router_prefix: Optional[str] = "/api/v1/awel/trigger",
    ) -> None:
        if not router:
            from fastapi import APIRouter

            router = APIRouter()
        self._router_prefix = router_prefix
        self._router = router
        self._trigger_map = {}

    def register_trigger(self, trigger: Any) -> None:
        from .http_trigger import HttpTrigger

        if not isinstance(trigger, HttpTrigger):
            raise ValueError(f"Current trigger {trigger} not an object of HttpTrigger")
        trigger: HttpTrigger = trigger
        trigger_id = trigger.node_id
        if trigger_id not in self._trigger_map:
            trigger.mount_to_router(self._router)
            self._trigger_map[trigger_id] = trigger

    def _init_app(self, system_app: SystemApp):
        logger.info(
            f"Include router {self._router} to prefix path {self._router_prefix}"
        )
        system_app.app.include_router(
            self._router, prefix=self._router_prefix, tags=["AWEL"]
        )


class DefaultTriggerManager(TriggerManager, BaseComponent):
    name = ComponentType.AWEL_TRIGGER_MANAGER

    def __init__(self, system_app: SystemApp | None = None):
        self.system_app = system_app
        self.http_trigger = HttpTriggerManager()
        super().__init__(None)

    def init_app(self, system_app: SystemApp):
        self.system_app = system_app

    def register_trigger(self, trigger: Any) -> None:
        from .http_trigger import HttpTrigger

        if isinstance(trigger, HttpTrigger):
            logger.info(f"Register trigger {trigger}")
            self.http_trigger.register_trigger(trigger)
        else:
            raise ValueError(f"Unsupport trigger: {trigger}")

    def after_register(self) -> None:
        self.http_trigger._init_app(self.system_app)
