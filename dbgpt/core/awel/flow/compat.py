"""Compatibility mapping for flow classes."""

from typing import Dict, Optional

_COMPAT_FLOW_MAPPING: Dict[str, str] = {}


_OLD_AGENT_RESOURCE_MODULE_1 = "dbgpt.serve.agent.team.layout.agent_operator_resource"
_OLD_AGENT_RESOURCE_MODULE_2 = "dbgpt.agent.plan.awel.agent_operator_resource"
_NEW_AGENT_RESOURCE_MODULE = "dbgpt.agent.core.plan.awel.agent_operator_resource"


def _register(
    old_module: str, new_module: str, old_name: str, new_name: Optional[str] = None
):
    if not new_name:
        new_name = old_name
    _COMPAT_FLOW_MAPPING[f"{old_module}.{old_name}"] = f"{new_module}.{new_name}"


def get_new_class_name(old_class_name: str) -> Optional[str]:
    """Get the new class name for the old class name."""
    new_cls_name = _COMPAT_FLOW_MAPPING.get(old_class_name, None)
    return new_cls_name


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
