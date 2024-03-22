"""The base module of DAG.

DAG is the core component of AWEL, it is used to define the relationship between tasks.
"""
import asyncio
import contextvars
import logging
import threading
import uuid
from abc import ABC, abstractmethod
from collections import deque
from concurrent.futures import Executor
from typing import Any, Callable, Dict, List, Optional, Sequence, Set, Union, cast

from dbgpt.component import SystemApp

from ..flow.base import ViewMixin
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
    """The mixin class for DAGNode.

    This class defines the interface for setting upstream and downstream nodes.

    And it also implements the operator << and >> for setting upstream
    and downstream nodes.
    """

    @abstractmethod
    def set_upstream(self, nodes: DependencyType) -> None:
        """Set one or more upstream nodes for this node.

        Args:
            nodes (DependencyType): Upstream nodes to be set to current node.

        Raises:
            ValueError: If no upstream nodes are provided or if an argument is
            not a DependencyMixin.
        """

    @abstractmethod
    def set_downstream(self, nodes: DependencyType) -> None:
        """Set one or more downstream nodes for this node.

        Args:
            nodes (DependencyType): Downstream nodes to be set to current node.

        Raises:
            ValueError: If no downstream nodes are provided or if an argument is
            not a DependencyMixin.
        """

    def __lshift__(self, nodes: DependencyType) -> DependencyType:
        """Set upstream nodes for current node.

        Implements: self << nodes.

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
        """Set downstream nodes for current node.

        Implements: self >> nodes.

        Examples:
            .. code-block:: python

                # means node.set_downstream(next_node)
                node >> next_node

                # means node2.set_downstream([next_node])
                node2 >> [next_node]

        """
        self.set_downstream(nodes)
        return nodes

    def __rrshift__(self, nodes: DependencyType) -> "DependencyMixin":
        """Set upstream nodes for current node.

        Implements: [node] >> self
        """
        self.__lshift__(nodes)
        return self

    def __rlshift__(self, nodes: DependencyType) -> "DependencyMixin":
        """Set downstream nodes for current node.

        Implements: [node] << self
        """
        self.__rshift__(nodes)
        return self


class DAGVar:
    """The DAGVar is used to store the current DAG context."""

    _thread_local = threading.local()
    _async_local: contextvars.ContextVar = contextvars.ContextVar(
        "current_dag_stack", default=deque()
    )
    _system_app: Optional[SystemApp] = None
    # The executor for current DAG, this is used run some sync tasks in async DAG
    _executor: Optional[Executor] = None

    @classmethod
    def enter_dag(cls, dag) -> None:
        """Enter a DAG context.

        Args:
            dag (DAG): The DAG to enter
        """
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
        """Exit a DAG context."""
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
        """Get the current DAG.

        Returns:
            Optional[DAG]: The current DAG
        """
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
    def get_current_system_app(cls) -> Optional[SystemApp]:
        """Get the current system app.

        Returns:
            Optional[SystemApp]: The current system app
        """
        # if not cls._system_app:
        #     raise RuntimeError("System APP not set for DAGVar")
        return cls._system_app

    @classmethod
    def set_current_system_app(cls, system_app: SystemApp) -> None:
        """Set the current system app.

        Args:
            system_app (SystemApp): The system app to set
        """
        if cls._system_app:
            logger.warning("System APP has already set, nothing to do")
        else:
            cls._system_app = system_app

    @classmethod
    def get_executor(cls) -> Optional[Executor]:
        """Get the current executor.

        Returns:
            Optional[Executor]: The current executor
        """
        return cls._executor

    @classmethod
    def set_executor(cls, executor: Executor) -> None:
        """Set the current executor.

        Args:
            executor (Executor): The executor to set
        """
        cls._executor = executor


class DAGLifecycle:
    """The lifecycle of DAG."""

    async def before_dag_run(self):
        """Execute before DAG run."""
        pass

    async def after_dag_end(self):
        """Execute after DAG end.

        This method may be called multiple times, please make sure it is idempotent.
        """
        pass


class DAGNode(DAGLifecycle, DependencyMixin, ViewMixin, ABC):
    """The base class of DAGNode."""

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
        """Initialize a DAGNode.

        Args:
            dag (Optional["DAG"], optional): The DAG to add this node to.
            Defaults to None.
            node_id (Optional[str], optional): The node id. Defaults to None.
            node_name (Optional[str], optional): The node name. Defaults to None.
            system_app (Optional[SystemApp], optional): The system app.
            Defaults to None.
            executor (Optional[Executor], optional): The executor. Defaults to None.
        """
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
        self._node_id: Optional[str] = node_id
        self._node_name: Optional[str] = node_name
        if self._dag:
            self._dag._append_node(self)

    @property
    def node_id(self) -> str:
        """Return the node id of current DAGNode."""
        if not self._node_id:
            raise ValueError("Node id not set for current DAGNode")
        return self._node_id

    @property
    @abstractmethod
    def dev_mode(self) -> bool:
        """Whether current DAGNode is in dev mode."""

    @property
    def system_app(self) -> Optional[SystemApp]:
        """Return the system app of current DAGNode."""
        return self._system_app

    def set_system_app(self, system_app: SystemApp) -> None:
        """Set system app for current DAGNode.

        Args:
            system_app (SystemApp): The system app
        """
        self._system_app = system_app

    def set_node_id(self, node_id: str) -> None:
        """Set node id for current DAGNode.

        Args:
            node_id (str): The node id
        """
        self._node_id = node_id

    def __hash__(self) -> int:
        """Return the hash value of current DAGNode.

        If the node_id is not None, return the hash value of node_id.
        """
        if self.node_id:
            return hash(self.node_id)
        else:
            return super().__hash__()

    def __eq__(self, other: Any) -> bool:
        """Return whether the current DAGNode is equal to other DAGNode."""
        if not isinstance(other, DAGNode):
            return False
        return self.node_id == other.node_id

    @property
    def node_name(self) -> Optional[str]:
        """Return the node name of current DAGNode.

        Returns:
            Optional[str]: The node name of current DAGNode
        """
        return self._node_name

    @property
    def dag(self) -> Optional["DAG"]:
        """Return the DAG of current DAGNode.

        Returns:
            Optional["DAG"]: The DAG of current DAGNode
        """
        return self._dag

    def set_upstream(self, nodes: DependencyType) -> None:
        """Set upstream nodes for current node.

        Args:
            nodes (DependencyType): Upstream nodes to be set to current node.
        """
        self.set_dependency(nodes)

    def set_downstream(self, nodes: DependencyType) -> None:
        """Set downstream nodes for current node.

        Args:
            nodes (DependencyType): Downstream nodes to be set to current node.
        """
        self.set_dependency(nodes, is_upstream=False)

    @property
    def upstream(self) -> List["DAGNode"]:
        """Return the upstream nodes of current DAGNode.

        Returns:
            List["DAGNode"]: The upstream nodes of current DAGNode
        """
        return self._upstream

    @property
    def downstream(self) -> List["DAGNode"]:
        """Return the downstream nodes of current DAGNode.

        Returns:
            List["DAGNode"]: The downstream nodes of current DAGNode
        """
        return self._downstream

    def set_dependency(self, nodes: DependencyType, is_upstream: bool = True) -> None:
        """Set dependency for current node.

        Args:
            nodes (DependencyType): The nodes to set dependency to current node.
            is_upstream (bool, optional): Whether set upstream nodes. Defaults to True.
        """
        if not isinstance(nodes, Sequence):
            nodes = [nodes]
        if not all(isinstance(node, DAGNode) for node in nodes):
            raise ValueError(
                "all nodes to set dependency to current node must be instance "
                "of 'DAGNode'"
            )
        nodes = cast(Sequence[DAGNode], nodes)
        dags = set([node.dag for node in nodes if node.dag])  # noqa: C403
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
        """Return the representation of current DAGNode."""
        cls_name = self.__class__.__name__
        if self.node_id and self.node_name:
            return f"{cls_name}(node_id={self.node_id}, node_name={self.node_name})"
        if self.node_id:
            return f"{cls_name}(node_id={self.node_id})"
        if self.node_name:
            return f"{cls_name}(node_name={self.node_name})"
        else:
            return f"{cls_name}"

    @property
    def graph_str(self):
        """Return the graph string of current DAGNode."""
        cls_name = self.__class__.__name__
        if self.node_id and self.node_name:
            return f"{self.node_id}({cls_name},{self.node_name})"
        if self.node_id:
            return f"{self.node_id}({cls_name})"
        if self.node_name:
            return f"{self.node_name}_{cls_name}({cls_name})"
        else:
            return f"{cls_name}"

    def __str__(self):
        """Return the string of current DAGNode."""
        return self.__repr__()


def _build_task_key(task_name: str, key: str) -> str:
    return f"{task_name}___$$$$$$___{key}"


class DAGContext:
    """The context of current DAG, created when the DAG is running.

    Every DAG has been triggered will create a new DAGContext.
    """

    def __init__(
        self,
        node_to_outputs: Dict[str, TaskContext],
        share_data: Dict[str, Any],
        streaming_call: bool = False,
        node_name_to_ids: Optional[Dict[str, str]] = None,
    ) -> None:
        """Initialize a DAGContext.

        Args:
            node_to_outputs (Dict[str, TaskContext]): The task outputs of current DAG.
            share_data (Dict[str, Any]): The share data of current DAG.
            streaming_call (bool, optional): Whether the current DAG is streaming call.
                Defaults to False.
            node_name_to_ids (Optional[Dict[str, str]], optional): The node name to node
        """
        if not node_name_to_ids:
            node_name_to_ids = {}
        self._streaming_call = streaming_call
        self._curr_task_ctx: Optional[TaskContext] = None
        self._share_data: Dict[str, Any] = share_data
        self._node_to_outputs: Dict[str, TaskContext] = node_to_outputs
        self._node_name_to_ids: Dict[str, str] = node_name_to_ids

    @property
    def _task_outputs(self) -> Dict[str, TaskContext]:
        """Return the task outputs of current DAG.

        Just use for internal for now.
        Returns:
            Dict[str, TaskContext]: The task outputs of current DAG
        """
        return self._node_to_outputs

    @property
    def current_task_context(self) -> TaskContext:
        """Return the current task context."""
        if not self._curr_task_ctx:
            raise RuntimeError("Current task context not set")
        return self._curr_task_ctx

    @property
    def streaming_call(self) -> bool:
        """Whether the current DAG is streaming call."""
        return self._streaming_call

    def set_current_task_context(self, _curr_task_ctx: TaskContext) -> None:
        """Set the current task context.

        When the task is running, the current task context
        will be set to the task context.

        TODO: We should support parallel task running in the future.
        """
        self._curr_task_ctx = _curr_task_ctx

    def get_task_output(self, task_name: str) -> TaskOutput:
        """Get the task output by task name.

        Args:
            task_name (str): The task name

        Returns:
            TaskOutput: The task output
        """
        if task_name is None:
            raise ValueError("task_name can't be None")
        node_id = self._node_name_to_ids.get(task_name)
        if not node_id:
            raise ValueError(f"Task name {task_name} not in DAG")
        task_output = self._task_outputs.get(node_id)
        if not task_output:
            raise ValueError(f"Task output for task {task_name} not exists")
        return task_output.task_output

    async def get_from_share_data(self, key: str) -> Any:
        """Get share data by key.

        Args:
            key (str): The share data key

        Returns:
            Any: The share data, you can cast it to the real type
        """
        logger.debug(f"Get share data by key {key} from {id(self._share_data)}")
        return self._share_data.get(key)

    async def save_to_share_data(
        self, key: str, data: Any, overwrite: bool = False
    ) -> None:
        """Save share data by key.

        Args:
            key (str): The share data key
            data (Any): The share data
            overwrite (bool): Whether overwrite the share data if the key
                already exists. Defaults to None.
        """
        if key in self._share_data and not overwrite:
            raise ValueError(f"Share data key {key} already exists")
        logger.debug(f"Save share data by key {key} to {id(self._share_data)}")
        self._share_data[key] = data

    async def get_task_share_data(self, task_name: str, key: str) -> Any:
        """Get share data by task name and key.

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
        """Save share data by task name and key.

        Args:
            task_name (str): The task name
            key (str): The share data key
            data (Any): The share data
            overwrite (bool): Whether overwrite the share data if the key
                already exists. Defaults to None.

        Raises:
            ValueError: If the share data key already exists and overwrite is not True
        """
        if task_name is None:
            raise ValueError("task_name can't be None")
        if key is None:
            raise ValueError("key can't be None")
        await self.save_to_share_data(_build_task_key(task_name, key), data, overwrite)


class DAG:
    """The DAG class.

    Manage the DAG nodes and the relationship between them.
    """

    def __init__(
        self, dag_id: str, resource_group: Optional[ResourceGroup] = None
    ) -> None:
        """Initialize a DAG."""
        self._dag_id = dag_id
        self.node_map: Dict[str, DAGNode] = {}
        self.node_name_to_node: Dict[str, DAGNode] = {}
        self._root_nodes: List[DAGNode] = []
        self._leaf_nodes: List[DAGNode] = []
        self._trigger_nodes: List[DAGNode] = []
        self._resource_group: Optional[ResourceGroup] = resource_group

    def _append_node(self, node: DAGNode) -> None:
        if node.node_id in self.node_map:
            return
        if node.node_name:
            if node.node_name in self.node_name_to_node:
                raise ValueError(
                    f"Node name {node.node_name} already exists in DAG {self.dag_id}"
                )
            self.node_name_to_node[node.node_name] = node
        node_id = node.node_id
        if not node_id:
            raise ValueError("Node id can't be None")
        self.node_map[node_id] = node
        # clear cached nodes
        self._root_nodes = []
        self._leaf_nodes = []

    def _new_node_id(self) -> str:
        return str(uuid.uuid4())

    @property
    def dag_id(self) -> str:
        """Return the dag id of current DAG."""
        return self._dag_id

    def _build(self) -> None:
        from ..operators.common_operator import TriggerOperator

        nodes: Set[DAGNode] = set()
        for _, node in self.node_map.items():
            nodes = nodes.union(_get_nodes(node))
        self._root_nodes = list(set(filter(lambda x: not x.upstream, nodes)))
        self._leaf_nodes = list(set(filter(lambda x: not x.downstream, nodes)))
        self._trigger_nodes = list(
            set(filter(lambda x: isinstance(x, TriggerOperator), nodes))
        )

    @property
    def root_nodes(self) -> List[DAGNode]:
        """Return the root nodes of current DAG.

        Returns:
            List[DAGNode]: The root nodes of current DAG, no repeat
        """
        if not self._root_nodes:
            self._build()
        return self._root_nodes

    @property
    def leaf_nodes(self) -> List[DAGNode]:
        """Return the leaf nodes of current DAG.

        Returns:
            List[DAGNode]: The leaf nodes of current DAG, no repeat
        """
        if not self._leaf_nodes:
            self._build()
        return self._leaf_nodes

    @property
    def trigger_nodes(self) -> List[DAGNode]:
        """Return the trigger nodes of current DAG.

        Returns:
            List[DAGNode]: The trigger nodes of current DAG, no repeat
        """
        if not self._trigger_nodes:
            self._build()
        return self._trigger_nodes

    async def _after_dag_end(self) -> None:
        """Execute after DAG end."""
        tasks = []
        for node in self.node_map.values():
            tasks.append(node.after_dag_end())
        await asyncio.gather(*tasks)

    def print_tree(self) -> None:
        """Print the DAG tree"""  # noqa: D400
        _print_format_dag_tree(self)

    def visualize_dag(self, view: bool = True, **kwargs) -> Optional[str]:
        """Visualize the DAG.

        Args:
            view (bool, optional): Whether view the DAG graph. Defaults to True,
                if True, it will open the graph file with your default viewer.
        """
        self.print_tree()
        return _visualize_dag(self, view=view, **kwargs)

    def show(self, mermaid: bool = False) -> Any:
        """Return the graph of current DAG."""
        dot, mermaid_str = _get_graph(self)
        return mermaid_str if mermaid else dot

    def __enter__(self):
        """Enter a DAG context."""
        DAGVar.enter_dag(self)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit a DAG context."""
        DAGVar.exit_dag()

    def __hash__(self) -> int:
        """Return the hash value of current DAG.

        If the dag_id is not None, return the hash value of dag_id.
        """
        if self.dag_id:
            return hash(self.dag_id)
        else:
            return super().__hash__()

    def __eq__(self, other):
        """Return whether the current DAG is equal to other DAG."""
        if not isinstance(other, DAG):
            return False
        return self.dag_id == other.dag_id

    def __repr__(self):
        """Return the representation of current DAG."""
        return f"DAG(dag_id={self.dag_id})"


def _get_nodes(node: DAGNode, is_upstream: Optional[bool] = True) -> Set[DAGNode]:
    nodes: Set[DAGNode] = set()
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
    level_dict: Optional[Dict[int, Any]] = None,
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


def _get_graph(dag: DAG):
    try:
        from graphviz import Digraph
    except ImportError:
        logger.warn("Can't import graphviz, skip visualize DAG")
        return None, None
    dot = Digraph(name=dag.dag_id)
    mermaid_str = "graph TD;\n"  # Initialize Mermaid graph definition
    # Record the added edges to avoid adding duplicate edges
    added_edges = set()

    def add_edges(node: DAGNode):
        nonlocal mermaid_str
        if node.downstream:
            for downstream_node in node.downstream:
                # Check if the edge has been added
                if (str(node), str(downstream_node)) not in added_edges:
                    dot.edge(str(node), str(downstream_node))
                    mermaid_str += f"    {node.graph_str} --> {downstream_node.graph_str};\n"  # noqa
                    added_edges.add((str(node), str(downstream_node)))
                add_edges(downstream_node)

    for root in dag.root_nodes:
        add_edges(root)
    return dot, mermaid_str


def _visualize_dag(
    dag: DAG, view: bool = True, generate_mermaid: bool = True, **kwargs
) -> Optional[str]:
    """Visualize the DAG.

    Args:
        dag (DAG): The DAG to visualize
        view (bool, optional): Whether view the DAG graph. Defaults to True.
        generate_mermaid (bool, optional): Whether to generate a Mermaid syntax file.
            Defaults to True.

    Returns:
        Optional[str]: The filename of the DAG graph
    """
    dot, mermaid_str = _get_graph(dag)
    if not dot:
        return None
    filename = f"dag-vis-{dag.dag_id}.gv"
    if "filename" in kwargs:
        filename = kwargs["filename"]
        del kwargs["filename"]

    if "directory" not in kwargs:
        from dbgpt.configs.model_config import LOGDIR

        kwargs["directory"] = LOGDIR

    # Generate Mermaid syntax file if requested
    if generate_mermaid:
        mermaid_filename = filename.replace(".gv", ".md")
        with open(
            f"{kwargs.get('directory', '')}/{mermaid_filename}", "w"
        ) as mermaid_file:
            logger.info(f"Writing Mermaid syntax to {mermaid_filename}")
            mermaid_file.write(mermaid_str)

    return dot.render(filename, view=view, **kwargs)
