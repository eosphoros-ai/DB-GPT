"""Trigger manager for AWEL.

After DB-GPT started, the trigger manager will be initialized and register all triggers
"""
import logging
from abc import ABC, abstractmethod
from collections import defaultdict
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set, Union

from dbgpt.component import BaseComponent, ComponentType, SystemApp

from ..util.http_util import join_paths
from .base import Trigger

if TYPE_CHECKING:
    from fastapi import APIRouter


logger = logging.getLogger(__name__)


class TriggerManager(ABC):
    """Base class for trigger manager."""

    @abstractmethod
    def register_trigger(self, trigger: Any, system_app: SystemApp) -> None:
        """Register a trigger to current manager."""

    @abstractmethod
    def unregister_trigger(self, trigger: Any, system_app: SystemApp) -> None:
        """Unregister a trigger to current manager."""

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
        self._inited = False
        self._router_prefix = router_prefix
        self._router = router
        self._trigger_map: Dict[str, Trigger] = {}
        self._router_tables: Dict[str, Set[str]] = defaultdict(set)

    def register_trigger(self, trigger: Any, system_app: SystemApp) -> None:
        """Register a trigger to current manager."""
        from .http_trigger import HttpTrigger

        if not isinstance(trigger, HttpTrigger):
            raise ValueError(f"Current trigger {trigger} not an object of HttpTrigger")
        trigger_id = trigger.node_id
        if trigger_id not in self._trigger_map:
            path = join_paths(self._router_prefix, trigger._endpoint)
            methods = trigger._methods
            # Check whether the route is already registered
            self._register_route_tables(path, methods)
            try:
                if trigger.register_to_app():
                    app = system_app.app
                    if not app:
                        raise ValueError("System app not initialized")
                    # Mount to app, support dynamic route.
                    trigger.mount_to_app(app, self._router_prefix)
                else:
                    trigger.mount_to_router(self._router, self._router_prefix)
                self._trigger_map[trigger_id] = trigger
            except Exception as e:
                self._unregister_route_tables(path, methods)
                raise e

    def unregister_trigger(self, trigger: Any, system_app: SystemApp) -> None:
        """Unregister a trigger to current manager."""
        from .http_trigger import HttpTrigger

        if not isinstance(trigger, HttpTrigger):
            raise ValueError(f"Current trigger {trigger} not an object of Trigger")
        trigger_id = trigger.node_id
        if trigger_id in self._trigger_map:
            if trigger.register_to_app():
                app = system_app.app
                if not app:
                    raise ValueError("System app not initialized")
                trigger.remove_from_app(app, self._router_prefix)
                self._unregister_route_tables(
                    join_paths(self._router_prefix, trigger._endpoint), trigger._methods
                )
            del self._trigger_map[trigger_id]

    def _init_app(self, system_app: SystemApp):
        # if self._inited:
        #     return None
        if not self.keep_running():
            return
        logger.info(
            f"Include router {self._router} to prefix path {self._router_prefix}"
        )
        app = system_app.app
        if not app:
            raise RuntimeError("System app not initialized")
        app.include_router(self._router, prefix=self._router_prefix, tags=["AWEL"])
        # self._inited = True

    def keep_running(self) -> bool:
        """Whether keep running.

        Returns:
            bool: Whether keep running, True means keep running, False means stop.
        """
        return len(self._trigger_map) > 0

    def _register_route_tables(
        self, path: str, methods: Optional[Union[str, List[str]]]
    ):
        methods = self._parse_methods(methods)
        tables = self._router_tables[path]
        for m in methods:
            if m in tables:
                raise ValueError(f"Route {path} method {m} already registered")
            tables.add(m)
        self._router_tables[path] = tables

    def _unregister_route_tables(
        self, path: str, methods: Optional[Union[str, List[str]]]
    ):
        methods = self._parse_methods(methods)
        tables = self._router_tables[path]
        for m in methods:
            if m in tables:
                tables.remove(m)
        self._router_tables[path] = tables

    def _parse_methods(self, methods: Optional[Union[str, List[str]]]) -> List[str]:
        if not methods:
            return ["GET"]
        elif isinstance(methods, str):
            return [methods]
        return [m.upper() for m in methods]


class DefaultTriggerManager(TriggerManager, BaseComponent):
    """Default trigger manager for AWEL.

    Manage all trigger managers. Just support http trigger now.
    """

    name = ComponentType.AWEL_TRIGGER_MANAGER

    def __init__(self, system_app: SystemApp | None = None):
        """Initialize a DefaultTriggerManager."""
        self.system_app = system_app
        self._http_trigger: Optional[HttpTriggerManager] = None
        super().__init__()

    def init_app(self, system_app: SystemApp):
        """Initialize the trigger manager."""
        self.system_app = system_app
        if system_app and self.system_app.app:
            self._http_trigger = HttpTriggerManager()

    def register_trigger(self, trigger: Any, system_app: SystemApp) -> None:
        """Register a trigger to current manager."""
        from .http_trigger import HttpTrigger

        if isinstance(trigger, HttpTrigger):
            logger.info(f"Register trigger {trigger}")
            if not self._http_trigger:
                raise ValueError("Http trigger manager not initialized")
            self._http_trigger.register_trigger(trigger, system_app)

    def unregister_trigger(self, trigger: Any, system_app: SystemApp) -> None:
        """Unregister a trigger to current manager."""
        from .http_trigger import HttpTrigger

        if isinstance(trigger, HttpTrigger):
            logger.info(f"Unregister trigger {trigger}")
            if not self._http_trigger:
                raise ValueError("Http trigger manager not initialized")
            self._http_trigger.unregister_trigger(trigger, system_app)

    def after_register(self) -> None:
        """After register, init the trigger manager."""
        if self.system_app and self._http_trigger:
            self._http_trigger._init_app(self.system_app)

    def keep_running(self) -> bool:
        """Whether keep running.

        Returns:
            bool: Whether keep running, True means keep running, False means stop.
        """
        if not self._http_trigger:
            return False
        return self._http_trigger.keep_running()
