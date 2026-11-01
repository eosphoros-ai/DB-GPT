"""Policy fragments for traceable report generation.

The ReAct runtime should only compose policies.  Report-specific instructions
live here so deployments can replace or disable them without editing the agent
loop or carrying the report prompt on unrelated turns.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TraceableReportPolicy:
    """Declarative policy for object-level report provenance."""

    enabled: bool = True
    require_object_bindings: bool = True
    strict_knowledge_requirements: bool = False

    def instructions(self) -> str:
        if not self.enabled:
            return ""
        opening = (
            "Finish analysis, then call generate_report; its dedicated agent owns "
            "the template, evidence bindings and repairs."
        )
        bindings = (
            "Bind every KPI, table, figure and numeric conclusion to its producer "
            "using data-dbgpt-artifacts. Tell generate_report the required content."
            if self.require_object_bindings
            else "Use the manifest only to cite evidence relevant to the report."
        )
        return (
            "## Traceable Report Policy\n"
            f"{opening}\n"
            f"{bindings}\n"
            "Missing KB lookup warns. Link each adopted KB rule's captured slice "
            "to its methodology statement; lookup or whole-page links do not count. "
            "Explain only adopted rules relevant to this analysis, once each. "
            "Keep methodology notes brief; do not reproduce KB checklists or "
            "tool instructions in report prose. "
            "Numeric values use SQL/Python sources; citations must be valid. Reuse "
            "saved results/spec, never write or patch HTML. See "
            "skills/business-report/SKILL.md. For status=needs_analysis, use "
            "code_interpreter only for missing_calculation from "
            "REPORT_CALCULATION_INPUTS, print JSON, then resume generate_report. "
            "Draft HTML is a preview; only status=completed means completion. "
            "Stop when retryable=false."
        )


DEFAULT_TRACEABLE_REPORT_POLICY = TraceableReportPolicy()


__all__ = ["DEFAULT_TRACEABLE_REPORT_POLICY", "TraceableReportPolicy"]
