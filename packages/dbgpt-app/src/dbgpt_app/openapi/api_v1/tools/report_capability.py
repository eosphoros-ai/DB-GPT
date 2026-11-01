"""Composable traceable-report capability for an agent ToolPack.

This is deliberately a small capability bundle, not a replacement Agent or a
business plugin.  It lets a host decide whether report rendering/provenance
tools are available while execution capture remains a generic context feature.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

from .html_interpreter import make_html_interpreter
from .report_evidence import make_report_evidence_manifest
from .report_policy import DEFAULT_TRACEABLE_REPORT_POLICY, TraceableReportPolicy


@dataclass(frozen=True)
class TraceableReportCapability:
    policy: TraceableReportPolicy
    tools: List[Any]

    @property
    def prompt_fragment(self) -> str:
        return self.policy.instructions()


def make_traceable_report_capability(
    react_state: Dict[str, Any], skills_dir: str
) -> TraceableReportCapability:
    """Create report tools from a policy without coupling the ReAct loop to them."""
    policy = DEFAULT_TRACEABLE_REPORT_POLICY
    if not policy.enabled:
        return TraceableReportCapability(policy=policy, tools=[])
    return TraceableReportCapability(
        policy=policy,
        tools=[
            make_html_interpreter(react_state, skills_dir),
            make_report_evidence_manifest(react_state),
        ],
    )


__all__ = ["TraceableReportCapability", "make_traceable_report_capability"]
