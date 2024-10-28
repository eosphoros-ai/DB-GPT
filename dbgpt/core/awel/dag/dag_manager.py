"""DAGManager is a component of AWEL, it is used to manage DAGs.

DAGManager will load DAGs from dag_dirs, and register the trigger nodes
to TriggerManager.
"""

import logging
import threading
from collections import defaultdict
from typing import Dict, List, Optional, Set

from dbgpt._private.pydantic import BaseModel, Field, model_to_dict
from dbgpt.component import BaseComponent, ComponentType, SystemApp

from .. import BaseOperator
from ..trigger.base import TriggerMetadata
from .base import DAG
from .loader import LocalFileDAGLoader

logger = logging.getLogger(__name__)


class DAGMetadata(BaseModel):
    """Metadata for the DAG."""

    triggers: List[TriggerMetadata] = Field(
        default_factory=list, description="The trigger metadata"
    )
    sse_output: bool = Field(
        default=False, description="Whether the DAG is a server-sent event output"
    )
    streaming_output: bool = Field(
        default=False, description="Whether the DAG is a streaming output"
    )
    tags: Optional[Dict[str, str]] = Field(
        default=None, description="The tags of the DAG"
    )

    def to_dict(self):
        """Convert the metadata to dict."""
        triggers_dict = []
        for trigger in self.triggers:
            triggers_dict.append(trigger.dict())
        dict_value = model_to_dict(self, exclude={"triggers"})
        dict_value["triggers"] = triggers_dict
        return dict_value


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
        self._dag_metadata_map: Dict[str, DAGMetadata] = {}
        self._tags_to_dag_ids: Dict[str, Dict[str, Set[str]]] = {}
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

            trigger_metadata: List["TriggerMetadata"] = []
            dag_metadata = _parse_metadata(dag)
            if self._trigger_manager:
                for trigger in dag.trigger_nodes:
                    tm = self._trigger_manager.register_trigger(
                        trigger, self.system_app
                    )
                    if tm:
                        trigger_metadata.append(tm)
                self._trigger_manager.after_register()
            else:
                logger.warning("No trigger manager, not register dag trigger")
            dag_metadata.triggers = trigger_metadata
            self._dag_metadata_map[dag_id] = dag_metadata
            tags = dag_metadata.tags
            if tags:
                for tag_key, tag_value in tags.items():
                    if tag_key not in self._tags_to_dag_ids:
                        self._tags_to_dag_ids[tag_key] = defaultdict(set)
                    self._tags_to_dag_ids[tag_key][tag_value].add(dag_id)

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
            metadata = self._dag_metadata_map[dag_id]
            del self.dag_map[dag_id]
            del self._dag_metadata_map[dag_id]
            if metadata.tags:
                for tag_key, tag_value in metadata.tags.items():
                    if tag_key in self._tags_to_dag_ids:
                        self._tags_to_dag_ids[tag_key][tag_value].remove(dag_id)

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

    def get_dags_by_tag(self, tag_key: str, tag_value) -> List[DAG]:
        """Get all DAGs with the given tag."""
        if not tag_value:
            return []
        with self.lock:
            dag_ids = self._tags_to_dag_ids.get(tag_key, {}).get(tag_value, set())
            return [self.dag_map[dag_id] for dag_id in dag_ids]

    def get_dags_by_tag_key(self, tag_key: str) -> Dict[str, List[DAG]]:
        """Get all DAGs with the given tag key."""
        with self.lock:
            value_dict = self._tags_to_dag_ids.get(tag_key, {})
            result = {}
            for k, v in value_dict.items():
                result[k] = [self.dag_map[dag_id] for dag_id in v]
            return result

    def get_dag_metadata(
        self, dag_id: Optional[str] = None, alias_name: Optional[str] = None
    ) -> Optional[DAGMetadata]:
        """Get a DAGMetadata by dag_id or alias_name."""
        dag = self.get_dag(dag_id, alias_name)
        if not dag:
            return None
        return self._dag_metadata_map.get(dag.dag_id)


def _parse_metadata(dag: DAG) -> DAGMetadata:
    from ..util.chat_util import _is_sse_output

    metadata = DAGMetadata()
    metadata.tags = dag.tags
    if not dag.leaf_nodes:
        return metadata
    end_node = dag.leaf_nodes[0]
    if not isinstance(end_node, BaseOperator):
        return metadata
    metadata.sse_output = _is_sse_output(end_node)
    metadata.streaming_output = end_node.streaming_operator
    return metadata
