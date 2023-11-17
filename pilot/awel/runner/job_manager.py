from typing import List, Set, Optional, Dict
import uuid
import logging
from ..dag.base import DAG

from ..operator.base import BaseOperator, CALL_DATA

logger = logging.getLogger(__name__)


class DAGNodeInstance:
    def __init__(self, node_instance: DAG) -> None:
        pass


class DAGInstance:
    def __init__(self, dag: DAG) -> None:
        self._dag = dag


class JobManager:
    def __init__(
        self,
        root_nodes: List[BaseOperator],
        all_nodes: List[BaseOperator],
        end_node: BaseOperator,
        id2call_data: Dict[str, Dict],
    ) -> None:
        self._root_nodes = root_nodes
        self._all_nodes = all_nodes
        self._end_node = end_node
        self._id2node_data = id2call_data

    @staticmethod
    def build_from_end_node(
        end_node: BaseOperator, call_data: Optional[CALL_DATA] = None
    ) -> "JobManager":
        nodes = _build_from_end_node(end_node)
        root_nodes = _get_root_nodes(nodes)
        id2call_data = _save_call_data(root_nodes, call_data)
        return JobManager(root_nodes, nodes, end_node, id2call_data)

    def get_call_data_by_id(self, node_id: str) -> Optional[Dict]:
        return self._id2node_data.get(node_id)


def _save_call_data(
    root_nodes: List[BaseOperator], call_data: CALL_DATA
) -> Dict[str, Dict]:
    id2call_data = {}
    logger.debug(f"_save_call_data: {call_data}, root_nodes: {root_nodes}")
    if not call_data:
        return id2call_data
    if len(root_nodes) == 1:
        node = root_nodes[0]
        logger.info(f"Save call data to node {node.node_id}, call_data: {call_data}")
        id2call_data[node.node_id] = call_data
    else:
        for node in root_nodes:
            node_id = node.node_id
            logger.info(
                f"Save call data to node {node.node_id}, call_data: {call_data.get(node_id)}"
            )
            id2call_data[node_id] = call_data.get(node_id)
    return id2call_data


def _build_from_end_node(end_node: BaseOperator) -> List[BaseOperator]:
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
