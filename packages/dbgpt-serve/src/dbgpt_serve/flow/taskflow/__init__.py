"""TaskFlow: the product-layer flow definition (DSL) and compiler.

TaskFlow is a coarse-grained, data-analysis oriented flow product built on top
of AWEL. Users compose *product nodes* (database query, AI analysis,
visualization, report...) in the TaskFlow editor; the DSL is compiled into an
AWEL ``FlowData`` and executed by the standard AWEL runtime (``chat_flow``
scene), so no new execution channel is introduced.
"""

from .compiler import TaskFlowCompiler, compile_taskflow
from .dsl import (
    TASKFLOW_FORMAT,
    TaskFlowDSL,
    TaskFlowDSLError,
    TaskFlowNodeModel,
    parse_dsl,
    topo_order,
    validate_dsl,
)
from .nodes import NODE_KINDS, get_node_kind_manifest

__all__ = [
    "TASKFLOW_FORMAT",
    "TaskFlowCompiler",
    "TaskFlowDSL",
    "TaskFlowDSLError",
    "TaskFlowNodeModel",
    "compile_taskflow",
    "parse_dsl",
    "topo_order",
    "validate_dsl",
    "NODE_KINDS",
    "get_node_kind_manifest",
]
