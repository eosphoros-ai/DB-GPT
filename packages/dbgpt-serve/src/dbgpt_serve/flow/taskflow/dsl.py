"""TaskFlow DSL (taskflow/1) — the product-layer flow definition.

TaskFlow DSL is a coarse-grained, product-oriented graph description. It is
compiled into an AWEL ``FlowData`` by
:class:`dbgpt_serve.flow.taskflow.compiler.TaskFlowCompiler` and never executed
directly.

Example:

.. code-block:: json

    {
      "format": "taskflow/1",
      "nodes": [
        {"id": "n1", "kind": "start", "config": {}},
        {"id": "n2", "kind": "db_query",
         "config": {"datasource": "mysql_prod", "max_rows": 1000}},
        {"id": "n3", "kind": "output", "config": {}}
      ],
      "edges": [["n1", "n2"], ["n2", "n3"]]
    }
"""

from typing import Any, Dict, List, Optional, Tuple

from dbgpt._private.pydantic import BaseModel, ConfigDict, Field, field_validator

TASKFLOW_FORMAT = "taskflow/1"

# Reserved execution-policy keys (accepted but not yet wired, see P1).
RESERVED_CONFIG_KEYS = {"retry", "timeout_s", "parallel_with_prev"}


class TaskFlowNodeModel(BaseModel):
    """One product node in the TaskFlow DSL."""

    model_config = ConfigDict(extra="ignore")

    id: str = Field(..., description="Unique node id inside the DSL")
    kind: str = Field(..., description="The product node kind")
    label: Optional[str] = Field(
        None, description="Optional custom display name of the node"
    )
    config: Dict[str, Any] = Field(
        default_factory=dict, description="Product-level config of the node"
    )


class TaskFlowDSL(BaseModel):
    """The TaskFlow DSL document."""

    model_config = ConfigDict(extra="ignore")

    format: str = Field(TASKFLOW_FORMAT, description="DSL format version")
    nodes: List[TaskFlowNodeModel] = Field(default_factory=list)
    edges: List[Tuple[str, str]] = Field(
        default_factory=list, description="[source_id, target_id] pairs"
    )
    viewport: Optional[Dict[str, Any]] = None

    @field_validator("edges", mode="before")
    @classmethod
    def _normalize_edges(cls, value):
        """Accept [[src, tgt], ...] or [{"source": ..., "target": ...}, ...]."""
        if not value:
            return []
        edges = []
        for item in value:
            if isinstance(item, dict):
                edges.append((item["source"], item["target"]))
            else:
                pair = list(item)
                if len(pair) != 2:
                    raise ValueError(f"Invalid edge: {item}")
                edges.append((pair[0], pair[1]))
        return edges


class TaskFlowDSLError(ValueError):
    """Raised when the TaskFlow DSL is invalid."""


def parse_dsl(data: Dict[str, Any]) -> TaskFlowDSL:
    """Parse a dict into a TaskFlowDSL with format checking."""
    if not isinstance(data, dict):
        raise TaskFlowDSLError("TaskFlow source must be a JSON object")
    fmt = data.get("format", TASKFLOW_FORMAT)
    if fmt != TASKFLOW_FORMAT:
        raise TaskFlowDSLError(
            f"Unsupported taskflow format: {fmt}, expected {TASKFLOW_FORMAT}"
        )
    try:
        return TaskFlowDSL(**data)
    except Exception as e:
        raise TaskFlowDSLError(f"Invalid taskflow DSL: {e}") from e


def validate_dsl(dsl: TaskFlowDSL, known_kinds: Dict[str, Any]) -> None:
    """Validate the DSL structure.

    Args:
        dsl: The parsed DSL.
        known_kinds: The registered node kinds (kind -> spec).

    Raises:
        TaskFlowDSLError: If the DSL is invalid.
    """
    if not dsl.nodes:
        raise TaskFlowDSLError("TaskFlow has no nodes")
    ids = [n.id for n in dsl.nodes]
    if len(set(ids)) != len(ids):
        raise TaskFlowDSLError("Duplicate node ids in TaskFlow")
    id_set = set(ids)
    for node in dsl.nodes:
        if node.kind not in known_kinds:
            raise TaskFlowDSLError(f"Unknown node kind: {node.kind} (node {node.id})")
    starts = [n for n in dsl.nodes if n.kind == "start"]
    if len(starts) != 1:
        raise TaskFlowDSLError(
            f"TaskFlow must have exactly one 'start' node, got {len(starts)}"
        )
    outputs = [n for n in dsl.nodes if n.kind == "output"]
    if len(outputs) != 1:
        raise TaskFlowDSLError(
            f"TaskFlow must have exactly one 'output' node, got {len(outputs)}"
        )

    incoming = {i: 0 for i in id_set}
    outgoing = {i: 0 for i in id_set}
    for src, tgt in dsl.edges:
        if src not in id_set or tgt not in id_set:
            raise TaskFlowDSLError(f"Edge references unknown node: {src} -> {tgt}")
        if src == tgt:
            raise TaskFlowDSLError(f"Self loop is not allowed: {src}")
        outgoing[src] += 1
        incoming[tgt] += 1

    for node in dsl.nodes:
        if node.kind == "start" and incoming[node.id] > 0:
            raise TaskFlowDSLError("The 'start' node cannot have incoming edges")
        if node.kind == "output" and outgoing[node.id] > 0:
            raise TaskFlowDSLError("The 'output' node cannot have outgoing edges")
        if node.kind not in ("start",) and incoming[node.id] == 0:
            raise TaskFlowDSLError(
                f"Node {node.id} ({node.kind}) is not connected from upstream"
            )

    # Cycle check (Kahn)
    indegree = dict(incoming)
    queue = [i for i in id_set if indegree[i] == 0]
    visited = 0
    adjacency: Dict[str, List[str]] = {i: [] for i in id_set}
    for src, tgt in dsl.edges:
        adjacency[src].append(tgt)
    while queue:
        current = queue.pop()
        visited += 1
        for nxt in adjacency[current]:
            indegree[nxt] -= 1
            if indegree[nxt] == 0:
                queue.append(nxt)
    if visited != len(id_set):
        raise TaskFlowDSLError("TaskFlow graph has a cycle")


def topo_order(dsl: TaskFlowDSL) -> List[str]:
    """Return DSL node ids in topological order (stable by declaration)."""
    declaration = {n.id: i for i, n in enumerate(dsl.nodes)}
    indegree = {n.id: 0 for n in dsl.nodes}
    adjacency: Dict[str, List[str]] = {n.id: [] for n in dsl.nodes}
    for src, tgt in dsl.edges:
        adjacency[src].append(tgt)
        indegree[tgt] += 1
    queue = sorted(
        [i for i, d in indegree.items() if d == 0], key=lambda i: declaration[i]
    )
    order = []
    while queue:
        current = queue.pop(0)
        order.append(current)
        for nxt in sorted(adjacency[current], key=lambda i: declaration[i]):
            indegree[nxt] -= 1
            if indegree[nxt] == 0:
                queue.append(nxt)
                queue.sort(key=lambda i: declaration[i])
    return order
