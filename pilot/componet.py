from __future__ import annotations

from abc import ABC, abstractmethod
import sys
from typing import Type, Dict, TypeVar, Optional, Union, TYPE_CHECKING
from enum import Enum
import logging
import asyncio

# Checking for type hints during runtime
if TYPE_CHECKING:
    from fastapi import FastAPI

logger = logging.getLogger(__name__)


class LifeCycle:
    """This class defines hooks for lifecycle events of a component."""

    def before_start(self):
        """Called before the component starts."""
        pass

    async def async_before_start(self):
        """Asynchronous version of before_start."""
        pass

    def after_start(self):
        """Called after the component has started."""
        pass

    async def async_after_start(self):
        """Asynchronous version of after_start."""
        pass

    def before_stop(self):
        """Called before the component stops."""
        pass

    async def async_before_stop(self):
        """Asynchronous version of before_stop."""
        pass


class ComponetType(str, Enum):
    WORKER_MANAGER = "dbgpt_worker_manager"
    MODEL_CONTROLLER = "dbgpt_model_controller"


class BaseComponet(LifeCycle, ABC):
    """Abstract Base Component class. All custom components should extend this."""

    name = "base_dbgpt_componet"

    def __init__(self, system_app: Optional[SystemApp] = None):
        if system_app is not None:
            self.init_app(system_app)

    @abstractmethod
    def init_app(self, system_app: SystemApp):
        """Initialize the component with the main application.

        This method needs to be implemented by every component to define how it integrates
        with the main system app.
        """
        pass


T = TypeVar("T", bound=BaseComponet)


class SystemApp(LifeCycle):
    """Main System Application class that manages the lifecycle and registration of components."""

    def __init__(self, asgi_app: Optional["FastAPI"] = None) -> None:
        self.componets: Dict[
            str, BaseComponet
        ] = {}  # Dictionary to store registered components.
        self._asgi_app = asgi_app

    @property
    def app(self) -> Optional["FastAPI"]:
        """Returns the internal ASGI app."""
        return self._asgi_app

    def register(self, componet: Type[BaseComponet], *args, **kwargs):
        """Register a new component by its type."""
        instance = componet(self, *args, **kwargs)
        self.register_instance(instance)

    def register_instance(self, instance: T):
        """Register an already initialized component."""
        name = instance.name
        if isinstance(name, ComponetType):
            name = name.value
        if name in self.componets:
            raise RuntimeError(
                f"Componse name {name} already exists: {self.componets[name]}"
            )
        logger.info(f"Register componet with name {name} and instance: {instance}")
        self.componets[name] = instance
        instance.init_app(self)

    def get_componet(self, name: Union[str, ComponetType], componet_type: Type[T]) -> T:
        """Retrieve a registered component by its name and type."""
        if isinstance(name, ComponetType):
            name = name.value
        component = self.componets.get(name)
        if not component:
            raise ValueError(f"No component found with name {name}")
        if not isinstance(component, componet_type):
            raise TypeError(f"Component {name} is not of type {componet_type}")
        return component

    def before_start(self):
        """Invoke the before_start hooks for all registered components."""
        for _, v in self.componets.items():
            v.before_start()

    async def async_before_start(self):
        """Asynchronously invoke the before_start hooks for all registered components."""
        tasks = [v.async_before_start() for _, v in self.componets.items()]
        await asyncio.gather(*tasks)

    def after_start(self):
        """Invoke the after_start hooks for all registered components."""
        for _, v in self.componets.items():
            v.after_start()

    async def async_after_start(self):
        """Asynchronously invoke the after_start hooks for all registered components."""
        tasks = [v.async_after_start() for _, v in self.componets.items()]
        await asyncio.gather(*tasks)

    def before_stop(self):
        """Invoke the before_stop hooks for all registered components."""
        for _, v in self.componets.items():
            try:
                v.before_stop()
            except Exception as e:
                pass

    async def async_before_stop(self):
        """Asynchronously invoke the before_stop hooks for all registered components."""
        tasks = [v.async_before_stop() for _, v in self.componets.items()]
        await asyncio.gather(*tasks)

    def _build(self):
        """Integrate lifecycle events with the internal ASGI app if available."""
        if not self.app:
            return

        @self.app.on_event("startup")
        async def startup_event():
            """ASGI app startup event handler."""

            async def _startup_func():
                try:
                    await self.async_after_start()
                except Exception as e:
                    logger.error(f"Error starting system app: {e}")
                    sys.exit(1)

            asyncio.create_task(_startup_func())
            self.after_start()

        @self.app.on_event("shutdown")
        async def shutdown_event():
            """ASGI app shutdown event handler."""
            await self.async_before_stop()
            self.before_stop()
