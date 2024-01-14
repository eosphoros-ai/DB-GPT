import asyncio
import logging
import uuid
from typing import Dict, List, Optional, Set

from ..dag.base import DAG, DAGLifecycle
from ..operator.base import CALL_DATA, BaseOperator

logger = logging.getLogger(__name__)


class DAGNodeInstance:
    def __init__(self, node_instance: DAG) -> None:
        pass


class DAGInstance:
    def __init__(self, dag: DAG) -> None:
        self._dag = dag


class JobManager(DAGLifecycle):
    def __init__(
        self,
        root_nodes: List[BaseOperator],
        all_nodes: List[BaseOperator],
        end_node: BaseOperator,
        id2call_data: Dict[str, Dict],
        node_name_to_ids: Dict[str, str],
    ) -> None:
        self._root_nodes = root_nodes
        self._all_nodes = all_nodes
        self._end_node = end_node
        self._id2node_data = id2call_data
        self._node_name_to_ids = node_name_to_ids

    @staticmethod
    def build_from_end_node(
        end_node: BaseOperator, call_data: Optional[CALL_DATA] = None
    ) -> "JobManager":
        nodes = _build_from_end_node(end_node)
        root_nodes = _get_root_nodes(nodes)
        id2call_data = _save_call_data(root_nodes, call_data)

        node_name_to_ids = {}
        for node in nodes:
            if node.node_name is not None:
                node_name_to_ids[node.node_name] = node.node_id

        return JobManager(root_nodes, nodes, end_node, id2call_data, node_name_to_ids)

    def get_call_data_by_id(self, node_id: str) -> Optional[Dict]:
        return self._id2node_data.get(node_id)

    async def before_dag_run(self):
        """The callback before DAG run"""
        tasks = []
        for node in self._all_nodes:
            tasks.append(node.before_dag_run())
        await asyncio.gather(*tasks)

    async def after_dag_end(self):
        """The callback after DAG end"""
        tasks = []
        for node in self._all_nodes:
            tasks.append(node.after_dag_end())
        await asyncio.gather(*tasks)


def _save_call_data(
    root_nodes: List[BaseOperator], call_data: CALL_DATA
) -> Dict[str, Dict]:
    id2call_data = {}
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
                f"Save call data to node {node.node_id}, call_data: {call_data.get(node_id)}"
            )
            id2call_data[node_id] = call_data.get(node_id)
    return id2call_data


def _build_from_end_node(end_node: BaseOperator) -> List[BaseOperator]:
    """Build all nodes from the end node."""
    nodes = []
    if isinstance(end_node, BaseOperator):
        task_id = end_node.node_id
        if not task_id:
            task_id = str(uuid.uuid4())
            end_node.set_node_id(task_id)
    nodes.append(end_node)
    for node in end_node.upstream:
        nodes += _build_from_end_node(node)
    return nodes


def _get_root_nodes(nodes: List[BaseOperator]) -> List[BaseOperator]:
    return list(set(filter(lambda x: not x.upstream, nodes)))
