"""Component module for dbgpt.

Manages the lifecycle and registration of components.
"""

from __future__ import annotations

import asyncio
import atexit
import logging
import sys
import threading
from abc import ABC, abstractmethod
from enum import Enum
from typing import TYPE_CHECKING, Dict, Optional, Type, TypeVar, Union

from dbgpt.util import AppConfig
from dbgpt.util.annotations import PublicAPI

# Checking for type hints during runtime
if TYPE_CHECKING:
    from fastapi import FastAPI

logger = logging.getLogger(__name__)


class LifeCycle:
    """This class defines hooks for lifecycle events of a component.

    Execution order of lifecycle hooks:
    1. on_init
    2. after_init
    3. before_start(async_before_start)
    4. after_start(async_after_start)
    5. before_stop(async_before_stop)
    """

    def on_init(self):
        """Called when the component is being initialized."""
        pass

    def after_init(self):
        """Called after the component has been initialized.

        For most cases, you should initialize your database connection here.
        """
        pass

    async def async_on_init(self):
        """Asynchronous version of on_init."""
        pass

    def before_start(self):
        """Called before the component starts.

        This method is called after the component has been initialized and before it is
        started.
        """
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
    PLUGIN_HUB = "dbgpt_plugin_hub"
    MULTI_AGENTS = "dbgpt_multi_agents"
    EXECUTOR_DEFAULT = "dbgpt_thread_pool_default"
    TRACER = "dbgpt_tracer"
    TRACER_SPAN_STORAGE = "dbgpt_tracer_span_storage"
    RAG_GRAPH_DEFAULT = "dbgpt_rag_engine_default"
    AWEL_TRIGGER_MANAGER = "dbgpt_awel_trigger_manager"
    AWEL_DAG_MANAGER = "dbgpt_awel_dag_manager"
    UNIFIED_METADATA_DB_MANAGER_FACTORY = "dbgpt_unified_metadata_db_manager_factory"
    CONNECTOR_MANAGER = "dbgpt_connector_manager"
    RAG_STORAGE_MANAGER = "dbgpt_rag_storage_manager"
    AGENT_MANAGER = "dbgpt_agent_manager"
    RESOURCE_MANAGER = "dbgpt_resource_manager"
    VARIABLES_PROVIDER = "dbgpt_variables_provider"
    FILE_STORAGE_CLIENT = "dbgpt_file_storage_client"


_EMPTY_DEFAULT_COMPONENT = "_EMPTY_DEFAULT_COMPONENT"


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

        This method needs to be implemented by every component to define how it
        integrates with the main system app.
        """

    @classmethod
    def get_instance(
        cls: Type[T],
        system_app: SystemApp,
        default_component=_EMPTY_DEFAULT_COMPONENT,
        or_register_component: Optional[Type[T]] = None,
        *args,
        **kwargs,
    ) -> T:
        """Get the current component instance.

        Args:
            system_app (SystemApp): The system app
            default_component : The default component instance if not retrieve by name
            or_register_component (Type[T]): The new component to register if not
                retrieve by name

        Returns:
            T: The component instance
        """
        # Check for keyword argument conflicts
        if "default_component" in kwargs:
            raise ValueError(
                "default_component argument given in both fixed and **kwargs"
            )
        if "or_register_component" in kwargs:
            raise ValueError(
                "or_register_component argument given in both fixed and **kwargs"
            )
        kwargs["default_component"] = default_component
        kwargs["or_register_component"] = or_register_component
        return system_app.get_component(
            cls.name,
            cls,
            *args,
            **kwargs,
        )


T = TypeVar("T", bound=BaseComponent)


@PublicAPI(stability="beta")
class SystemApp(LifeCycle):
    """Main System Application class that manages the lifecycle and registration of
    components."""

    def __init__(
        self,
        asgi_app: Optional["FastAPI"] = None,
        app_config: Optional[AppConfig] = None,
    ) -> None:
        self.components: Dict[
            str, BaseComponent
        ] = {}  # Dictionary to store registered components.
        self._asgi_app = asgi_app
        self._app_config = app_config or AppConfig()
        self._stop_event = threading.Event()
        self._stop_event.clear()
        self._build()

    @property
    def app(self) -> Optional["FastAPI"]:
        """Returns the internal ASGI app."""
        return self._asgi_app

    @property
    def config(self) -> AppConfig:
        """Returns the internal AppConfig."""
        return self._app_config

    def register(self, component: Type[T], *args, **kwargs) -> T:
        """Register a new component by its type.

        Args:
            component (Type[T]): The component class to register

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
        component_type: Type,
        default_component=_EMPTY_DEFAULT_COMPONENT,
        or_register_component: Optional[Type[T]] = None,
        *args,
        **kwargs,
    ) -> T:
        """Retrieve a registered component by its name and type.

        Args:
            name (Union[str, ComponentType]): Component name
            component_type (Type[T]): The type of current retrieve component
            default_component : The default component instance if not retrieve by name
            or_register_component (Type[T]): The new component to register if not
                retrieve by name

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

    def on_init(self):
        """Invoke the on_init hooks for all registered components."""
        copied_view = {k: v for k, v in self.components.items()}
        for _, v in copied_view.items():
            v.on_init()

    def after_init(self):
        """Invoke the after_init hooks for all registered components."""
        copied_view = {k: v for k, v in self.components.items()}
        for _, v in copied_view.items():
            v.after_init()

    async def async_on_init(self):
        """Asynchronously invoke the on_init hooks for all registered components."""

        copied_view = {k: v for k, v in self.components.items()}
        tasks = [v.async_on_init() for _, v in copied_view.items()]
        await asyncio.gather(*tasks)

    def before_start(self):
        """Invoke the before_start hooks for all registered components."""
        copied_view = {k: v for k, v in self.components.items()}
        for _, v in copied_view.items():
            v.before_start()

    async def async_before_start(self):
        """Asynchronously invoke the before_start hooks.

        It will invoke all registered components' async_before_start hooks.
        """
        copied_view = {k: v for k, v in self.components.items()}
        tasks = [v.async_before_start() for _, v in copied_view.items()]
        await asyncio.gather(*tasks)

    def after_start(self):
        """Invoke the after_start hooks for all registered components."""
        copied_view = {k: v for k, v in self.components.items()}
        for _, v in copied_view.items():
            v.after_start()

    async def async_after_start(self):
        """Asynchronously invoke the after_start hooks for all registered components."""
        copied_view = {k: v for k, v in self.components.items()}
        tasks = [v.async_after_start() for _, v in copied_view.items()]
        await asyncio.gather(*tasks)

    def before_stop(self):
        """Invoke the before_stop hooks for all registered components."""
        if self._stop_event.is_set():
            return

        copied_view = {k: v for k, v in self.components.items()}
        for _, v in copied_view.items():
            try:
                v.before_stop()
            except Exception:
                pass
        self._stop_event.set()

    async def async_before_stop(self):
        """Asynchronously invoke the before_stop hooks for all registered components."""
        copied_view = {k: v for k, v in self.components.items()}
        tasks = [v.async_before_stop() for _, v in copied_view.items()]
        await asyncio.gather(*tasks)

    def _build(self):
        """Integrate lifecycle events with the internal ASGI app if available."""
        if not self.app:
            self._register_exit_handler()
            return
        from dbgpt.util.fastapi import register_event_handler

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

        async def shutdown_event():
            """ASGI app shutdown event handler."""
            await self.async_before_stop()
            self.before_stop()

        register_event_handler(self.app, "startup", startup_event)
        register_event_handler(self.app, "shutdown", shutdown_event)

    def _register_exit_handler(self):
        """Register an exit handler to stop the system app."""
        atexit.register(self.before_stop)
