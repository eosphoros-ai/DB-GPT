from abc import ABC, abstractmethod
from typing import Optional, Dict, List, Sequence, Union, Any
import uuid
import contextvars
import threading
import asyncio
from collections import deque

from ..resource.base import ResourceGroup
from ..task.base import TaskContext

DependencyType = Union["DependencyMixin", Sequence["DependencyMixin"]]


def _is_async_context():
    try:
        loop = asyncio.get_running_loop()
        return asyncio.current_task(loop=loop) is not None
    except RuntimeError:
        return False


class DependencyMixin(ABC):
    @abstractmethod
    def set_upstream(self, nodes: DependencyType) -> "DependencyMixin":
        """Set one or more upstream nodes for this node.

        Args:
            nodes (DependencyType): Upstream nodes to be set to current node.

        Returns:
            DependencyMixin: Returns self to allow method chaining.

        Raises:
            ValueError: If no upstream nodes are provided or if an argument is not a DependencyMixin.
        """

    @abstractmethod
    def set_downstream(self, nodes: DependencyType) -> "DependencyMixin":
        """Set one or more downstream nodes for this node.

        Args:
            nodes (DependencyType): Downstream nodes to be set to current node.

        Returns:
            DependencyMixin: Returns self to allow method chaining.

        Raises:
            ValueError: If no downstream nodes are provided or if an argument is not a DependencyMixin.
        """

    def __lshift__(self, nodes: DependencyType) -> DependencyType:
        """Implements self << nodes

        Example:

        .. code-block:: python

            # means node.set_upstream(input_node)
            node << input_node

            # means node2.set_upstream([input_node])
            node2 << [input_node]
        """
        self.set_upstream(nodes)
        return nodes

    def __rshift__(self, nodes: DependencyType) -> DependencyType:
        """Implements self >> nodes

        Example:

        .. code-block:: python

            # means node.set_downstream(next_node)
            node >> next_node

            # means node2.set_downstream([next_node])
            node2 >> [next_node]

        """
        self.set_downstream(nodes)
        return nodes

    def __rrshift__(self, nodes: DependencyType) -> "DependencyMixin":
        """Implements [node] >> self"""
        self.__lshift__(nodes)
        return self

    def __rlshift__(self, nodes: DependencyType) -> "DependencyMixin":
        """Implements [node] << self"""
        self.__rshift__(nodes)
        return self


class DAGVar:
    _thread_local = threading.local()
    _async_local = contextvars.ContextVar("current_dag_stack", default=deque())

    @classmethod
    def enter_dag(cls, dag) -> None:
        is_async = _is_async_context()
        if is_async:
            stack = cls._async_local.get()
            stack.append(dag)
            cls._async_local.set(stack)
        else:
            if not hasattr(cls._thread_local, "current_dag_stack"):
                cls._thread_local.current_dag_stack = deque()
            cls._thread_local.current_dag_stack.append(dag)

    @classmethod
    def exit_dag(cls) -> None:
        is_async = _is_async_context()
        if is_async:
            stack = cls._async_local.get()
            if stack:
                stack.pop()
                cls._async_local.set(stack)
        else:
            if (
                hasattr(cls._thread_local, "current_dag_stack")
                and cls._thread_local.current_dag_stack
            ):
                cls._thread_local.current_dag_stack.pop()

    @classmethod
    def get_current_dag(cls) -> Optional["DAG"]:
        is_async = _is_async_context()
        if is_async:
            stack = cls._async_local.get()
            return stack[-1] if stack else None
        else:
            if (
                hasattr(cls._thread_local, "current_dag_stack")
                and cls._thread_local.current_dag_stack
            ):
                return cls._thread_local.current_dag_stack[-1]
            return None


class DAGNode(DependencyMixin, ABC):
    resource_group: Optional[ResourceGroup] = None
    """The resource group of current DAGNode"""

    def __init__(
        self, dag: Optional["DAG"] = None, node_id: str = None, node_name: str = None
    ) -> None:
        super().__init__()
        self._upstream: List["DAGNode"] = []
        self._downstream: List["DAGNode"] = []
        self._dag: Optional["DAG"] = dag or DAGVar.get_current_dag()
        if not node_id and self._dag:
            node_id = self._dag._new_node_id()
        self._node_id: str = node_id
        self._node_name: str = node_name

    @property
    def node_id(self) -> str:
        return self._node_id

    def set_node_id(self, node_id: str) -> None:
        self._node_id = node_id

    def __hash__(self) -> int:
        if self.node_id:
            return hash(self.node_id)
        else:
            return super().__hash__()

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, DAGNode):
            return False
        return self.node_id == other.node_id

    @property
    def node_name(self) -> str:
        return self._node_name

    @property
    def dag(self) -> "DAGNode":
        return self._dag

    def set_upstream(self, nodes: DependencyType) -> "DAGNode":
        self.set_dependency(nodes)

    def set_downstream(self, nodes: DependencyType) -> "DAGNode":
        self.set_dependency(nodes, is_upstream=False)

    @property
    def upstream(self) -> List["DAGNode"]:
        return self._upstream

    @property
    def downstream(self) -> List["DAGNode"]:
        return self._downstream

    def set_dependency(self, nodes: DependencyType, is_upstream: bool = True) -> None:
        if not isinstance(nodes, Sequence):
            nodes = [nodes]
        if not all(isinstance(node, DAGNode) for node in nodes):
            raise ValueError(
                "all nodes to set dependency to current node must be instance of 'DAGNode'"
            )
        nodes: Sequence[DAGNode] = nodes
        dags = set([node.dag for node in nodes if node.dag])
        if self.dag:
            dags.add(self.dag)
        if not dags:
            raise ValueError("set dependency to current node must in a DAG context")
        if len(dags) != 1:
            raise ValueError(
                "set dependency to current node just support in one DAG context"
            )
        dag = dags.pop()
        self._dag = dag

        dag._append_node(self)
        for node in nodes:
            if is_upstream and node not in self.upstream:
                node._dag = dag
                dag._append_node(node)

                self._upstream.append(node)
                node._downstream.append(self)
            elif node not in self._downstream:
                node._dag = dag
                dag._append_node(node)

                self._downstream.append(node)
                node._upstream.append(self)


class DAGContext:
    def __init__(self) -> None:
        self._curr_task_ctx = None
        self._share_data: Dict[str, Any] = {}

    @property
    def current_task_context(self) -> TaskContext:
        return self._curr_task_ctx

    def set_current_task_context(self, _curr_task_ctx: TaskContext) -> None:
        self._curr_task_ctx = _curr_task_ctx

    async def get_share_data(self, key: str) -> Any:
        return self._share_data.get(key)

    async def save_to_share_data(self, key: str, data: Any) -> None:
        self._share_data[key] = data


class DAG:
    def __init__(
        self, dag_id: str, resource_group: Optional[ResourceGroup] = None
    ) -> None:
        self.node_map: Dict[str, DAGNode] = {}

    def _append_node(self, node: DAGNode) -> None:
        self.node_map[node.node_id] = node

    def _new_node_id(self) -> str:
        return str(uuid.uuid4())

    def __enter__(self):
        DAGVar.enter_dag(self)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        DAGVar.exit_dag()
