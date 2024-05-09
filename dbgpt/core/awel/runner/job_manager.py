"""Job manager for DAG."""

import asyncio
import logging
import uuid
from typing import Dict, List, Optional, cast

from ..dag.base import DAGLifecycle
from ..operators.base import CALL_DATA, BaseOperator

logger = logging.getLogger(__name__)


class JobManager(DAGLifecycle):
    """Job manager for DAG.

    This class is used to manage the DAG lifecycle.
    """

    def __init__(
        self,
        root_nodes: List[BaseOperator],
        all_nodes: List[BaseOperator],
        end_node: BaseOperator,
        id2call_data: Dict[str, Optional[Dict]],
        node_name_to_ids: Dict[str, str],
    ) -> None:
        """Create a job manager.

        Args:
            root_nodes (List[BaseOperator]): The root nodes of the DAG.
            all_nodes (List[BaseOperator]): All nodes of the DAG.
            end_node (BaseOperator): The end node of the DAG.
            id2call_data (Dict[str, Optional[Dict]]): The call data of each node.
            node_name_to_ids (Dict[str, str]): The node name to node id mapping.
        """
        self._root_nodes = root_nodes
        self._all_nodes = all_nodes
        self._end_node = end_node
        self._id2node_data = id2call_data
        self._node_name_to_ids = node_name_to_ids

    @staticmethod
    def build_from_end_node(
        end_node: BaseOperator, call_data: Optional[CALL_DATA] = None
    ) -> "JobManager":
        """Build a job manager from the end node.

        This will get all upstream nodes from the end node, and build a job manager.

        Args:
            end_node (BaseOperator): The end node of the DAG.
            call_data (Optional[CALL_DATA], optional): The call data of the end node.
                Defaults to None.
        """
        nodes = _build_from_end_node(end_node)
        root_nodes = _get_root_nodes(nodes)
        id2call_data = _save_call_data(root_nodes, call_data)

        node_name_to_ids = {}
        for node in nodes:
            if node.node_name is not None:
                node_name_to_ids[node.node_name] = node.node_id

        return JobManager(root_nodes, nodes, end_node, id2call_data, node_name_to_ids)

    def get_call_data_by_id(self, node_id: str) -> Optional[Dict]:
        """Get the call data by node id.

        Args:
            node_id (str): The node id.
        """
        return self._id2node_data.get(node_id)

    async def before_dag_run(self):
        """Execute the callback before DAG run."""
        tasks = []
        for node in self._all_nodes:
            tasks.append(node.before_dag_run())
        await asyncio.gather(*tasks)

    async def after_dag_end(self, event_loop_task_id: int):
        """Execute the callback after DAG end."""
        tasks = []
        for node in self._all_nodes:
            tasks.append(node.after_dag_end(event_loop_task_id))
        await asyncio.gather(*tasks)


def _save_call_data(
    root_nodes: List[BaseOperator], call_data: Optional[CALL_DATA]
) -> Dict[str, Optional[Dict]]:
    id2call_data: Dict[str, Optional[Dict]] = {}
    logger.debug(f"_save_call_data: {call_data}, root_nodes: {root_nodes}")
    if not call_data:
        return id2call_data
    if len(root_nodes) == 1:
        node = root_nodes[0]
        logger.debug(f"Save call data to node {node.node_id}, call_data: {call_data}")
        id2call_data[node.node_id] = call_data
    else:
        for node in root_nodes:
            node_id = node.node_id
            logger.debug(
                f"Save call data to node {node.node_id}, call_data: "
                f"{call_data.get(node_id)}"
            )
            id2call_data[node_id] = call_data.get(node_id)
    return id2call_data


def _build_from_end_node(end_node: BaseOperator) -> List[BaseOperator]:
    """Build all nodes from the end node."""
    nodes = []
    if isinstance(end_node, BaseOperator) and not end_node._node_id:
        end_node.set_node_id(str(uuid.uuid4()))
    nodes.append(end_node)
    for node in end_node.upstream:
        node = cast(BaseOperator, node)
        nodes += _build_from_end_node(node)
    return nodes


def _get_root_nodes(nodes: List[BaseOperator]) -> List[BaseOperator]:
    return list(set(filter(lambda x: not x.upstream, nodes)))
