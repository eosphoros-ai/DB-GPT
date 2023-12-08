from __future__ import annotations

from abc import ABC, abstractmethod
import sys
from typing import Type, Dict, TypeVar, Optional, Union, TYPE_CHECKING
from enum import Enum
import logging
import asyncio
from dbgpt.util.annotations import PublicAPI

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


class ComponentType(str, Enum):
    WORKER_MANAGER = "dbgpt_worker_manager"
    WORKER_MANAGER_FACTORY = "dbgpt_worker_manager_factory"
    MODEL_CONTROLLER = "dbgpt_model_controller"
    MODEL_REGISTRY = "dbgpt_model_registry"
    MODEL_API_SERVER = "dbgpt_model_api_server"
    MODEL_CACHE_MANAGER = "dbgpt_model_cache_manager"
    AGENT_HUB = "dbgpt_agent_hub"
    EXECUTOR_DEFAULT = "dbgpt_thread_pool_default"
    TRACER = "dbgpt_tracer"
    TRACER_SPAN_STORAGE = "dbgpt_tracer_span_storage"
    RAG_GRAPH_DEFAULT = "dbgpt_rag_engine_default"
    AWEL_TRIGGER_MANAGER = "dbgpt_awel_trigger_manager"
    AWEL_DAG_MANAGER = "dbgpt_awel_dag_manager"


@PublicAPI(stability="beta")
class BaseComponent(LifeCycle, ABC):
    """Abstract Base Component class. All custom components should extend this."""

    name = "base_dbgpt_component"

    def __init__(self, system_app: Optional[SystemApp] = None):
        if system_app is not None:
            self.init_app(system_app)

    @abstractmethod
    def init_app(self, system_app: SystemApp):
        """Initialize the component with the main application.

        This method needs to be implemented by every component to define how it integrates
        with the main system app.
        """


T = TypeVar("T", bound=BaseComponent)

_EMPTY_DEFAULT_COMPONENT = "_EMPTY_DEFAULT_COMPONENT"


@PublicAPI(stability="beta")
class SystemApp(LifeCycle):
    """Main System Application class that manages the lifecycle and registration of components."""

    def __init__(self, asgi_app: Optional["FastAPI"] = None) -> None:
        self.components: Dict[
            str, BaseComponent
        ] = {}  # Dictionary to store registered components.
        self._asgi_app = asgi_app

    @property
    def app(self) -> Optional["FastAPI"]:
        """Returns the internal ASGI app."""
        return self._asgi_app

    def register(self, component: Type[BaseComponent], *args, **kwargs) -> T:
        """Register a new component by its type.

        Args:
            component (Type[BaseComponent]): The component class to register

        Returns:
            T: The instance of registered component
        """
        instance = component(self, *args, **kwargs)
        self.register_instance(instance)
        return instance

    def register_instance(self, instance: T) -> T:
        """Register an already initialized component.

        Args:
            instance (T): The component instance to register

        Returns:
            T: The instance of registered component
        """
        name = instance.name
        if isinstance(name, ComponentType):
            name = name.value
        if name in self.components:
            raise RuntimeError(
                f"Componse name {name} already exists: {self.components[name]}"
            )
        logger.info(f"Register component with name {name} and instance: {instance}")
        self.components[name] = instance
        instance.init_app(self)
        return instance

    def get_component(
        self,
        name: Union[str, ComponentType],
        component_type: Type[T],
        default_component=_EMPTY_DEFAULT_COMPONENT,
        or_register_component: Type[BaseComponent] = None,
        *args,
        **kwargs,
    ) -> T:
        """Retrieve a registered component by its name and type.

        Args:
            name (Union[str, ComponentType]): Component name
            component_type (Type[T]): The type of current retrieve component
            default_component : The default component instance if not retrieve by name
            or_register_component (Type[BaseComponent]): The new component to register if not retrieve by name

        Returns:
            T: The instance retrieved by component name
        """
        if isinstance(name, ComponentType):
            name = name.value
        component = self.components.get(name)
        if not component:
            if or_register_component:
                return self.register(or_register_component, *args, **kwargs)
            if default_component != _EMPTY_DEFAULT_COMPONENT:
                return default_component
            raise ValueError(f"No component found with name {name}")
        if not isinstance(component, component_type):
            raise TypeError(f"Component {name} is not of type {component_type}")
        return component

    def before_start(self):
        """Invoke the before_start hooks for all registered components."""
        for _, v in self.components.items():
            v.before_start()

    async def async_before_start(self):
        """Asynchronously invoke the before_start hooks for all registered components."""
        tasks = [v.async_before_start() for _, v in self.components.items()]
        await asyncio.gather(*tasks)

    def after_start(self):
        """Invoke the after_start hooks for all registered components."""
        for _, v in self.components.items():
            v.after_start()

    async def async_after_start(self):
        """Asynchronously invoke the after_start hooks for all registered components."""
        tasks = [v.async_after_start() for _, v in self.components.items()]
        await asyncio.gather(*tasks)

    def before_stop(self):
        """Invoke the before_stop hooks for all registered components."""
        for _, v in self.components.items():
            try:
                v.before_stop()
            except Exception as e:
                pass

    async def async_before_stop(self):
        """Asynchronously invoke the before_stop hooks for all registered components."""
        tasks = [v.async_before_stop() for _, v in self.components.items()]
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
