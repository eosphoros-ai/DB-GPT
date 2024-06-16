"""Compatibility mapping for flow classes."""

from dataclasses import dataclass
from typing import Dict, Optional


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


_COMPAT_FLOW_MAPPING: Dict[str, _RegisterItem] = {}


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


def get_new_class_name(old_class_name: str) -> Optional[str]:
    """Get the new class name for the old class name."""
    if old_class_name not in _COMPAT_FLOW_MAPPING:
        return None
    item = _COMPAT_FLOW_MAPPING[old_class_name]
    return item.new_cls_key()


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
    "dbgpt.storage.vector_store.connector",
    "dbgpt.serve.rag.connector",
    "VectorStoreConnector",
    after_version="v0.5.8",
)
