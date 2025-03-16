"""Compatibility mapping for flow classes."""

import logging
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class _RegisterItem:
    """Register item for compatibility mapping."""

    old_module: str
    new_module: str
    old_name: str
    new_name: Optional[str] = None
    after: Optional[str] = None

    def old_cls_key(self) -> str:
        """Get the old class key."""
        return f"{self.old_module}.{self.old_name}"

    def new_cls_key(self) -> str:
        """Get the new class key."""
        return f"{self.new_module}.{self.new_name}"


@dataclass
class FlowCompatMetadata:
    type: str
    type_cls: str
    type_name: str
    name: str = field(
        metadata={"help": "Name of the operator or resource"},
    )
    id: str = field(
        metadata={"help": "ID of the operator or resource"},
    )
    category: str = field(
        metadata={"help": "Category of the operator or resource"},
    )
    parameters: List[str] = field(
        default_factory=list, metadata={"help": "Parameters, just include the name"}
    )
    outputs: List[str] = field(
        default_factory=list, metadata={"help": "Outputs, just include the name"}
    )
    inputs: List[str] = field(
        default_factory=list, metadata={"help": "Inputs, just include the name"}
    )
    version: str = field(default="v1")

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class _FlowCompat:
    curr_version: str
    last_support_version: str
    metadata: FlowCompatMetadata


_COMPAT_FLOW_MAPPING: Dict[str, _RegisterItem] = {}
_TYPE_NAME_TO_COMPAT_METADATA: Dict[str, List[_FlowCompat]] = defaultdict(list)

_OLD_AGENT_OPERATOR_MODULE = "dbgpt.serve.agent.team.layout.agent_operator"
_NEW_AGENT_OPERATOR_MODULE = "dbgpt.agent.core.plan.awel.agent_operator"

_OLD_AGENT_RESOURCE_MODULE_1 = "dbgpt.serve.agent.team.layout.agent_operator_resource"
_OLD_AGENT_RESOURCE_MODULE_2 = "dbgpt.agent.plan.awel.agent_operator_resource"
_NEW_AGENT_RESOURCE_MODULE = "dbgpt.agent.core.plan.awel.agent_operator_resource"


def _register(
    old_module: str,
    new_module: str,
    old_name: str,
    new_name: Optional[str] = None,
    after_version: Optional[str] = None,
):
    if not new_name:
        new_name = old_name
    item = _RegisterItem(old_module, new_module, old_name, new_name, after_version)
    _COMPAT_FLOW_MAPPING[item.old_cls_key()] = item


def _register_flow_compat(
    curr_version: str, last_support_version: str, metadata: FlowCompatMetadata
):
    # We use type_name as the key
    # For example, dbgpt.core.DefaultLLMOperator may be refactor to
    # dbgpt_ext.DefaultLLMOperator, so we use DefaultLLMOperator as the key
    _TYPE_NAME_TO_COMPAT_METADATA[metadata.type_name].append(
        _FlowCompat(curr_version, last_support_version, metadata)
    )


def get_new_class_name(old_class_name: str) -> Optional[str]:
    """Get the new class name for the old class name."""
    from dbgpt import __version__

    if old_class_name in _COMPAT_FLOW_MAPPING:
        item = _COMPAT_FLOW_MAPPING[old_class_name]
        return item.new_cls_key()
    type_name = old_class_name.split(".")[-1]
    if type_name in _TYPE_NAME_TO_COMPAT_METADATA:
        compat_list = _TYPE_NAME_TO_COMPAT_METADATA[type_name]
        if len(compat_list) > 1:
            raise ValueError(f"Multiple compat metadata found for {old_class_name}")
        compat_metadata = compat_list[0]
        if _compare_compat_version(__version__, compat_metadata.last_support_version):
            compat_cls = compat_metadata.metadata.type_cls
            logger.info(
                f"For {old_class_name}, found compat class {compat_cls} in version "
                f"{__version__}"
            )
            return compat_cls
        else:
            logger.warning(
                f"Class {old_class_name} is not supported in version {__version__}"
            )
    return None


def _compare_compat_version(curr_version: str, last_support_version: str) -> bool:
    """Compare two version strings."""
    v1 = curr_version.split(".")
    v2 = last_support_version.split(".")
    if int(v1[0]) != int(v2[0]):
        # Major version is different
        return False
    # Major version is less than or equal
    return int(v1[1]) <= int(v2[1])


_register(
    _OLD_AGENT_RESOURCE_MODULE_1,
    _NEW_AGENT_RESOURCE_MODULE,
    "AwelAgentResource",
    "AWELAgentResource",
)
_register(
    _OLD_AGENT_RESOURCE_MODULE_2,
    _NEW_AGENT_RESOURCE_MODULE,
    "AWELAgentResource",
)
_register(
    _OLD_AGENT_RESOURCE_MODULE_1,
    _NEW_AGENT_RESOURCE_MODULE,
    "AwelAgentConfig",
    "AWELAgentConfig",
)
_register(
    _OLD_AGENT_RESOURCE_MODULE_2,
    _NEW_AGENT_RESOURCE_MODULE,
    "AWELAgentConfig",
    "AWELAgentConfig",
)
_register(
    _OLD_AGENT_RESOURCE_MODULE_1, _NEW_AGENT_RESOURCE_MODULE, "AwelAgent", "AWELAgent"
)

_register(
    _OLD_AGENT_RESOURCE_MODULE_2, _NEW_AGENT_RESOURCE_MODULE, "AWELAgent", "AWELAgent"
)

_register(
    _OLD_AGENT_RESOURCE_MODULE_1,
    _NEW_AGENT_RESOURCE_MODULE,
    "AwelAgentKnowledgeResource",
    "AWELAgentKnowledgeResource",
)
_register(
    _OLD_AGENT_RESOURCE_MODULE_1,
    _NEW_AGENT_RESOURCE_MODULE,
    "AgentPrompt",
)


# AGENT Operator
_register(
    _OLD_AGENT_RESOURCE_MODULE_1,
    _NEW_AGENT_RESOURCE_MODULE,
    "AwelAgentOperator",
    "AWELAgentOperator",
)
_register(
    _OLD_AGENT_RESOURCE_MODULE_1,
    _NEW_AGENT_RESOURCE_MODULE,
    "AgentBranchOperator",
)
_register(
    _OLD_AGENT_RESOURCE_MODULE_1,
    _NEW_AGENT_RESOURCE_MODULE,
    "AgentBranchJoinOperator",
)

_register(
    _OLD_AGENT_OPERATOR_MODULE,
    _NEW_AGENT_OPERATOR_MODULE,
    "AgentDummyTrigger",
)
_register(
    _OLD_AGENT_OPERATOR_MODULE,
    _NEW_AGENT_OPERATOR_MODULE,
    "AgentDummyTrigger",
)


_register(
    "dbgpt.storage.vector_store.connector",
    "dbgpt.serve.rag.connector",
    "VectorStoreConnector",
    after_version="v0.5.8",
)
