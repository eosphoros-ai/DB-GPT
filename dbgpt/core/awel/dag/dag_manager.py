"""DAGManager is a component of AWEL, it is used to manage DAGs.

DAGManager will load DAGs from dag_dirs, and register the trigger nodes
to TriggerManager.
"""
import logging
import threading
from typing import Dict, List, Optional

from dbgpt.component import BaseComponent, ComponentType, SystemApp

from .base import DAG
from .loader import LocalFileDAGLoader

logger = logging.getLogger(__name__)


class DAGManager(BaseComponent):
    """The component of DAGManager."""

    name = ComponentType.AWEL_DAG_MANAGER

    def __init__(self, system_app: SystemApp, dag_dirs: List[str]):
        """Initialize a DAGManager.

        Args:
            system_app (SystemApp): The system app.
            dag_dirs (List[str]): The directories to load DAGs.
        """
        from ..trigger.trigger_manager import DefaultTriggerManager

        super().__init__(system_app)
        self.lock = threading.Lock()
        self.dag_loader = LocalFileDAGLoader(dag_dirs)
        self.system_app = system_app
        self.dag_map: Dict[str, DAG] = {}
        self.dag_alias_map: Dict[str, str] = {}
        self._trigger_manager: Optional["DefaultTriggerManager"] = None

    def init_app(self, system_app: SystemApp):
        """Initialize the DAGManager."""
        self.system_app = system_app

    def load_dags(self):
        """Load DAGs from dag_dirs."""
        dags = self.dag_loader.load_dags()
        for dag in dags:
            self.register_dag(dag)

    def before_start(self):
        """Execute before the application starts."""
        from ..trigger.trigger_manager import DefaultTriggerManager

        self._trigger_manager = self.system_app.get_component(
            ComponentType.AWEL_TRIGGER_MANAGER,
            DefaultTriggerManager,
            default_component=None,
        )

    def after_start(self):
        """Execute after the application starts."""
        self.load_dags()

    def register_dag(self, dag: DAG, alias_name: Optional[str] = None):
        """Register a DAG."""
        with self.lock:
            dag_id = dag.dag_id
            if dag_id in self.dag_map:
                raise ValueError(
                    f"Register DAG error, DAG ID {dag_id} has already exist"
                )
            self.dag_map[dag_id] = dag
            if alias_name:
                self.dag_alias_map[alias_name] = dag_id

            if self._trigger_manager:
                for trigger in dag.trigger_nodes:
                    self._trigger_manager.register_trigger(trigger, self.system_app)
                self._trigger_manager.after_register()
            else:
                logger.warning("No trigger manager, not register dag trigger")

    def unregister_dag(self, dag_id: str):
        """Unregister a DAG."""
        with self.lock:
            if dag_id not in self.dag_map:
                raise ValueError(
                    f"Unregister DAG error, DAG ID {dag_id} does not exist"
                )
            dag = self.dag_map[dag_id]

            # Collect aliases to remove
            # TODO(fangyinc): It can be faster if we maintain a reverse map
            aliases_to_remove = [
                alias_name
                for alias_name, _dag_id in self.dag_alias_map.items()
                if _dag_id == dag_id
            ]
            # Remove collected aliases
            for alias_name in aliases_to_remove:
                del self.dag_alias_map[alias_name]

            if self._trigger_manager:
                for trigger in dag.trigger_nodes:
                    self._trigger_manager.unregister_trigger(trigger, self.system_app)
            # Finally remove the DAG from the map
            del self.dag_map[dag_id]

    def get_dag(
        self, dag_id: Optional[str] = None, alias_name: Optional[str] = None
    ) -> Optional[DAG]:
        """Get a DAG by dag_id or alias_name."""
        # Not lock, because it is read only and need to be fast
        if dag_id and dag_id in self.dag_map:
            return self.dag_map[dag_id]
        if alias_name in self.dag_alias_map:
            return self.dag_map.get(self.dag_alias_map[alias_name])
        return None
