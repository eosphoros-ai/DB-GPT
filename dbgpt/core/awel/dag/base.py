import asyncio
import contextvars
import logging
import threading
import uuid
from abc import ABC, abstractmethod
from collections import deque
from concurrent.futures import Executor
from typing import Any, Callable, Dict, List, Optional, Sequence, Set, Union

from dbgpt.component import SystemApp

from ..resource.base import ResourceGroup
from ..task.base import TaskContext, TaskOutput

logger = logging.getLogger(__name__)

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
    _system_app: SystemApp = None
    _executor: Executor = None

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

    @classmethod
    def get_current_system_app(cls) -> SystemApp:
        # if not cls._system_app:
        #     raise RuntimeError("System APP not set for DAGVar")
        return cls._system_app

    @classmethod
    def set_current_system_app(cls, system_app: SystemApp) -> None:
        if cls._system_app:
            logger.warn("System APP has already set, nothing to do")
        else:
            cls._system_app = system_app

    @classmethod
    def get_executor(cls) -> Executor:
        return cls._executor

    @classmethod
    def set_executor(cls, executor: Executor) -> None:
        cls._executor = executor


class DAGLifecycle:
    """The lifecycle of DAG"""

    async def before_dag_run(self):
        """The callback before DAG run"""
        pass

    async def after_dag_end(self):
        """The callback after DAG end,

        This method may be called multiple times, please make sure it is idempotent.
        """
        pass


class DAGNode(DAGLifecycle, DependencyMixin, ABC):
    resource_group: Optional[ResourceGroup] = None
    """The resource group of current DAGNode"""

    def __init__(
        self,
        dag: Optional["DAG"] = None,
        node_id: Optional[str] = None,
        node_name: Optional[str] = None,
        system_app: Optional[SystemApp] = None,
        executor: Optional[Executor] = None,
        **kwargs,
    ) -> None:
        super().__init__()
        self._upstream: List["DAGNode"] = []
        self._downstream: List["DAGNode"] = []
        self._dag: Optional["DAG"] = dag or DAGVar.get_current_dag()
        self._system_app: Optional[SystemApp] = (
            system_app or DAGVar.get_current_system_app()
        )
        self._executor: Optional[Executor] = executor or DAGVar.get_executor()
        if not node_id and self._dag:
            node_id = self._dag._new_node_id()
        self._node_id: str = node_id
        self._node_name: str = node_name

    @property
    def node_id(self) -> str:
        return self._node_id

    @property
    @abstractmethod
    def dev_mode(self) -> bool:
        """Whether current DAGNode is in dev mode"""

    @property
    def system_app(self) -> SystemApp:
        return self._system_app

    def set_system_app(self, system_app: SystemApp) -> None:
        """Set system app for current DAGNode

        Args:
            system_app (SystemApp): The system app
        """
        self._system_app = system_app

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
    def dag(self) -> "DAG":
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

    def __repr__(self):
        cls_name = self.__class__.__name__
        if self.node_name and self.node_name:
            return f"{cls_name}(node_id={self.node_id}, node_name={self.node_name})"
        if self.node_id:
            return f"{cls_name}(node_id={self.node_id})"
        if self.node_name:
            return f"{cls_name}(node_name={self.node_name})"
        else:
            return f"{cls_name}"

    def __str__(self):
        return self.__repr__()


def _build_task_key(task_name: str, key: str) -> str:
    return f"{task_name}___$$$$$$___{key}"


class DAGContext:
    """The context of current DAG, created when the DAG is running

    Every DAG has been triggered will create a new DAGContext.
    """

    def __init__(
        self,
        streaming_call: bool = False,
        node_to_outputs: Dict[str, TaskContext] = None,
        node_name_to_ids: Dict[str, str] = None,
    ) -> None:
        if not node_to_outputs:
            node_to_outputs = {}
        if not node_name_to_ids:
            node_name_to_ids = {}
        self._streaming_call = streaming_call
        self._curr_task_ctx = None
        self._share_data: Dict[str, Any] = {}
        self._node_to_outputs = node_to_outputs
        self._node_name_to_ids = node_name_to_ids

    @property
    def _task_outputs(self) -> Dict[str, TaskContext]:
        """The task outputs of current DAG

        Just use for internal for now.
        Returns:
            Dict[str, TaskContext]: The task outputs of current DAG
        """
        return self._node_to_outputs

    @property
    def current_task_context(self) -> TaskContext:
        return self._curr_task_ctx

    @property
    def streaming_call(self) -> bool:
        """Whether the current DAG is streaming call"""
        return self._streaming_call

    def set_current_task_context(self, _curr_task_ctx: TaskContext) -> None:
        self._curr_task_ctx = _curr_task_ctx

    def get_task_output(self, task_name: str) -> TaskOutput:
        """Get the task output by task name

        Args:
            task_name (str): The task name

        Returns:
            TaskOutput: The task output
        """
        if task_name is None:
            raise ValueError("task_name can't be None")
        node_id = self._node_name_to_ids.get(task_name)
        if node_id:
            raise ValueError(f"Task name {task_name} not exists in DAG")
        return self._task_outputs.get(node_id).task_output

    async def get_from_share_data(self, key: str) -> Any:
        return self._share_data.get(key)

    async def save_to_share_data(
        self, key: str, data: Any, overwrite: bool = False
    ) -> None:
        if key in self._share_data and not overwrite:
            raise ValueError(f"Share data key {key} already exists")
        self._share_data[key] = data

    async def get_task_share_data(self, task_name: str, key: str) -> Any:
        """Get share data by task name and key

        Args:
            task_name (str): The task name
            key (str): The share data key

        Returns:
            Any: The share data
        """
        if task_name is None:
            raise ValueError("task_name can't be None")
        if key is None:
            raise ValueError("key can't be None")
        return self.get_from_share_data(_build_task_key(task_name, key))

    async def save_task_share_data(
        self, task_name: str, key: str, data: Any, overwrite: bool = False
    ) -> None:
        """Save share data by task name and key

        Args:
            task_name (str): The task name
            key (str): The share data key
            data (Any): The share data
            overwrite (bool): Whether overwrite the share data if the key already exists.
                Defaults to None.

        Raises:
            ValueError: If the share data key already exists and overwrite is not True
        """
        if task_name is None:
            raise ValueError("task_name can't be None")
        if key is None:
            raise ValueError("key can't be None")
        await self.save_to_share_data(_build_task_key(task_name, key), data, overwrite)


class DAG:
    def __init__(
        self, dag_id: str, resource_group: Optional[ResourceGroup] = None
    ) -> None:
        self._dag_id = dag_id
        self.node_map: Dict[str, DAGNode] = {}
        self.node_name_to_node: Dict[str, DAGNode] = {}
        self._root_nodes: List[DAGNode] = None
        self._leaf_nodes: List[DAGNode] = None
        self._trigger_nodes: List[DAGNode] = None

    def _append_node(self, node: DAGNode) -> None:
        if node.node_id in self.node_map:
            return
        if node.node_name:
            if node.node_name in self.node_name_to_node:
                raise ValueError(
                    f"Node name {node.node_name} already exists in DAG {self.dag_id}"
                )
            self.node_name_to_node[node.node_name] = node
        self.node_map[node.node_id] = node
        # clear cached nodes
        self._root_nodes = None
        self._leaf_nodes = None

    def _new_node_id(self) -> str:
        return str(uuid.uuid4())

    @property
    def dag_id(self) -> str:
        return self._dag_id

    def _build(self) -> None:
        from ..operator.common_operator import TriggerOperator

        nodes = set()
        for _, node in self.node_map.items():
            nodes = nodes.union(_get_nodes(node))
        self._root_nodes = list(set(filter(lambda x: not x.upstream, nodes)))
        self._leaf_nodes = list(set(filter(lambda x: not x.downstream, nodes)))
        self._trigger_nodes = list(
            set(filter(lambda x: isinstance(x, TriggerOperator), nodes))
        )

    @property
    def root_nodes(self) -> List[DAGNode]:
        """The root nodes of current DAG

        Returns:
            List[DAGNode]: The root nodes of current DAG, no repeat
        """
        if not self._root_nodes:
            self._build()
        return self._root_nodes

    @property
    def leaf_nodes(self) -> List[DAGNode]:
        """The leaf nodes of current DAG

        Returns:
            List[DAGNode]: The leaf nodes of current DAG, no repeat
        """
        if not self._leaf_nodes:
            self._build()
        return self._leaf_nodes

    @property
    def trigger_nodes(self) -> List[DAGNode]:
        """The trigger nodes of current DAG

        Returns:
            List[DAGNode]: The trigger nodes of current DAG, no repeat
        """
        if not self._trigger_nodes:
            self._build()
        return self._trigger_nodes

    async def _after_dag_end(self) -> None:
        """The callback after DAG end"""
        tasks = []
        for node in self.node_map.values():
            tasks.append(node.after_dag_end())
        await asyncio.gather(*tasks)

    def print_tree(self) -> None:
        """Print the DAG tree"""
        _print_format_dag_tree(self)

    def visualize_dag(self, view: bool = True, **kwargs) -> Optional[str]:
        """Create the DAG graph"""
        self.print_tree()
        return _visualize_dag(self, view=view, **kwargs)

    def __enter__(self):
        DAGVar.enter_dag(self)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        DAGVar.exit_dag()

    def __repr__(self):
        return f"DAG(dag_id={self.dag_id})"


def _get_nodes(node: DAGNode, is_upstream: Optional[bool] = True) -> set[DAGNode]:
    nodes = set()
    if not node:
        return nodes
    nodes.add(node)
    stream_nodes = node.upstream if is_upstream else node.downstream
    for node in stream_nodes:
        nodes = nodes.union(_get_nodes(node, is_upstream))
    return nodes


def _print_format_dag_tree(dag: DAG) -> None:
    for node in dag.root_nodes:
        _print_dag(node)


def _print_dag(
    node: DAGNode,
    level: int = 0,
    prefix: str = "",
    last: bool = True,
    level_dict: Dict[str, Any] = None,
):
    if level_dict is None:
        level_dict = {}

    connector = " -> " if level != 0 else ""
    new_prefix = prefix
    if last:
        if level != 0:
            new_prefix += "  "
        print(prefix + connector + str(node))
    else:
        if level != 0:
            new_prefix += "| "
        print(prefix + connector + str(node))

    level_dict[level] = level_dict.get(level, 0) + 1
    num_children = len(node.downstream)
    for i, child in enumerate(node.downstream):
        _print_dag(child, level + 1, new_prefix, i == num_children - 1, level_dict)


def _print_dag_tree(root_nodes: List[DAGNode], level_sep: str = "  ") -> None:
    def _print_node(node: DAGNode, level: int) -> None:
        print(f"{level_sep * level}{node}")

    _apply_root_node(root_nodes, _print_node)


def _apply_root_node(
    root_nodes: List[DAGNode],
    func: Callable[[DAGNode, int], None],
) -> None:
    for dag_node in root_nodes:
        _handle_dag_nodes(False, 0, dag_node, func)


def _handle_dag_nodes(
    is_down_to_up: bool,
    level: int,
    dag_node: DAGNode,
    func: Callable[[DAGNode, int], None],
):
    if not dag_node:
        return
    func(dag_node, level)
    stream_nodes = dag_node.upstream if is_down_to_up else dag_node.downstream
    level += 1
    for node in stream_nodes:
        _handle_dag_nodes(is_down_to_up, level, node, func)


def _visualize_dag(dag: DAG, view: bool = True, **kwargs) -> Optional[str]:
    """Visualize the DAG

    Args:
        dag (DAG): The DAG to visualize
        view (bool, optional): Whether view the DAG graph. Defaults to True.

    Returns:
        Optional[str]: The filename of the DAG graph
    """
    try:
        from graphviz import Digraph
    except ImportError:
        logger.warn("Can't import graphviz, skip visualize DAG")
        return None

    dot = Digraph(name=dag.dag_id)
    # Record the added edges to avoid adding duplicate edges
    added_edges = set()

    def add_edges(node: DAGNode):
        if node.downstream:
            for downstream_node in node.downstream:
                # Check if the edge has been added
                if (str(node), str(downstream_node)) not in added_edges:
                    dot.edge(str(node), str(downstream_node))
                    added_edges.add((str(node), str(downstream_node)))
                add_edges(downstream_node)

    for root in dag.root_nodes:
        add_edges(root)
    filename = f"dag-vis-{dag.dag_id}.gv"
    if "filename" in kwargs:
        filename = kwargs["filename"]
        del kwargs["filename"]

    if not "directory" in kwargs:
        from dbgpt.configs.model_config import LOGDIR

        kwargs["directory"] = LOGDIR

    return dot.render(filename, view=view, **kwargs)
