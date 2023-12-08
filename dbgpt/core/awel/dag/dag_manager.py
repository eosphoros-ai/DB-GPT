from typing import Dict, Optional
import logging
from dbgpt.component import BaseComponent, ComponentType, SystemApp
from .loader import DAGLoader, LocalFileDAGLoader
from .base import DAG

logger = logging.getLogger(__name__)


class DAGManager(BaseComponent):
    name = ComponentType.AWEL_DAG_MANAGER

    def __init__(self, system_app: SystemApp, dag_filepath: str):
        super().__init__(system_app)
        self.dag_loader = LocalFileDAGLoader(dag_filepath)
        self.system_app = system_app
        self.dag_map: Dict[str, DAG] = {}

    def init_app(self, system_app: SystemApp):
        self.system_app = system_app

    def load_dags(self):
        dags = self.dag_loader.load_dags()
        triggers = []
        for dag in dags:
            dag_id = dag.dag_id
            if dag_id in self.dag_map:
                raise ValueError(f"Load DAG error, DAG ID {dag_id} has already exist")
            triggers += dag.trigger_nodes
        from ..trigger.trigger_manager import DefaultTriggerManager

        trigger_manager: DefaultTriggerManager = self.system_app.get_component(
            ComponentType.AWEL_TRIGGER_MANAGER,
            DefaultTriggerManager,
            default_component=None,
        )
        if trigger_manager:
            for trigger in triggers:
                trigger_manager.register_trigger(trigger)
            trigger_manager.after_register()
        else:
            logger.warn("No trigger manager, not register dag trigger")
