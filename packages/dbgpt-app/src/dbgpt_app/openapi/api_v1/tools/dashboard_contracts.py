"""Describe the registered Dashboard tools using their actual validation models."""

import json
from typing import Any, Dict, Iterable

from pydantic import Field

from dbgpt.agent.expand.actions.react_action import Terminate
from dbgpt.agent.resource import ToolPack
from dbgpt.agent.resource.tool.base import BaseTool

from ..dashboard.release_features import layout_templates_enabled
from ..dashboard.schemas import (
    DashboardChangeProposalRequest,
    DashboardPlan,
    DashboardQueryDraftRequest,
)


class DashboardProposalToolInput(DashboardChangeProposalRequest):
    """One authoritative proposal shape for tool documentation and validation."""

    dashboard_id: str = Field(min_length=1, max_length=64)
    annotation_id: str = Field(min_length=1, max_length=64)


def model_tool_parameters(model) -> Dict[str, Any]:
    """Generate flat tool declarations without duplicating the service contract."""
    schema = model.model_json_schema()
    required = set(schema.get("required", []))
    result = {}
    for name, field in schema["properties"].items():
        result[name] = {
            "type": field.get("type", "object"),
            "required": name in required,
            "description": _schema_type(field),
        }
        if "default" in field:
            result[name]["default"] = field["default"]
    return result


class _CheckedDashboardTool(BaseTool):
    """Keep the original tool, but reject unknown keys BEFORE pack filtering.

    ReAct rebuilds ToolPack from its resources before dispatch. The guard must
    therefore live on the tool, not only on a specialized ToolPack instance.
    """

    def __init__(self, delegate: BaseTool):
        self.delegate = delegate

    @property
    def name(self):
        return self.delegate.name

    @property
    def description(self):
        return self.delegate.description

    @property
    def args(self):
        return self.delegate.args

    @property
    def is_async(self):
        return self.delegate.is_async

    def validate_call_args(self, arguments):
        unknown = sorted(set(arguments).difference(self.args))
        if unknown:
            # Report keys, never SQL, values or credentials. Do not silently
            # rewrap a malformed call and count it as first-attempt acceptance.
            hint = (
                " Put widget rows in widget_queries.widgets, not top-level widgets."
                if "widget_queries" in self.args
                else ""
            )
            raise ValueError(
                f"Unknown top-level arguments for {self.name}: "
                f"{', '.join(str(key)[:80] for key in unknown[:8])}. "
                f"Allowed keys: {', '.join(self.args)}.{hint}"
            )
        self.delegate.validate_call_args(arguments)

    def parse_execute_args(self, **kwargs):
        return self.delegate.parse_execute_args(**kwargs)

    async def get_prompt(self, **kwargs):
        return await self.delegate.get_prompt(**kwargs)

    def execute(self, *args, **kwargs):
        return self.delegate.execute(*args, **kwargs)

    async def async_execute(self, *args, **kwargs):
        return await self.delegate.async_execute(*args, **kwargs)


def make_dashboard_tool_pack(
    resources: Iterable[Any], user_input: str, *, read_only_annotation: bool = False
) -> ToolPack:
    """Narrow actual capabilities by workflow; render only the resulting registry."""
    if read_only_annotation:
        allowed = {"load_dashboard_draft", "resolve_dashboard_reference"}
    elif "[[dashboard-annotation:" in user_input:
        allowed = {
            "load_dashboard_draft",
            "resolve_dashboard_reference",
            "propose_dashboard_change",
        }
    elif "[[confirm-dashboard:" in user_input:
        allowed = {
            "load_dashboard_draft",
            "create_dashboard_draft",
            "repair_dashboard_draft",
        }
    elif "[[revise-dashboard-plan:" in user_input:
        allowed = {"load_dashboard_draft", "revise_dashboard_plan"}
    elif "[[modify-dashboard:" in user_input:
        allowed = {
            "load_dashboard_draft",
            "resolve_dashboard_reference",
            "modify_dashboard_draft",
            "repair_dashboard_draft",
            "sql_query",
        }
    else:
        # An ordinary natural-language turn can plan a new board OR identify an
        # existing one to edit. Do not infer a new capability boundary from words
        # inside negations (e.g. "do not change the empty year"). Confirmation,
        # revision, repair and annotation capabilities require their own phase.
        allowed = {
            "sql_query",
            "plan_dashboard",
            "load_dashboard_draft",
            "resolve_dashboard_reference",
            "modify_dashboard_draft",
        }
    allowed.update({"question", "terminate"})
    return ToolPack(
        [
            resource
            if isinstance(resource, Terminate)
            else _CheckedDashboardTool(resource)
            for resource in ToolPack(list(resources)).sub_resources
            if resource.name in allowed
        ]
    )


def _schema_type(schema: Dict[str, Any]) -> str:
    if "$ref" in schema:
        return schema["$ref"].rsplit("/", 1)[-1]
    if "anyOf" in schema:
        return " | ".join(_schema_type(item) for item in schema["anyOf"])
    if "allOf" in schema:
        return " & ".join(_schema_type(item) for item in schema["allOf"])
    if "enum" in schema:
        return " | ".join(
            json.dumps(item, ensure_ascii=False) for item in schema["enum"]
        )
    kind = schema.get("type", "any")
    if kind == "array":
        kind = f"array<{_schema_type(schema.get('items', {}))}>"
    elif kind == "object" and isinstance(schema.get("additionalProperties"), dict):
        kind = f"map<string, {_schema_type(schema['additionalProperties'])}>"
    constraints = {
        key: schema[key]
        for key in (
            "minimum",
            "maximum",
            "exclusiveMinimum",
            "minLength",
            "maxLength",
            "minItems",
            "maxItems",
            "pattern",
            "default",
        )
        if key in schema
    }
    if constraints:
        kind += " " + json.dumps(constraints, ensure_ascii=False, separators=(",", ":"))
    return kind


def validation_model_contracts(models: Iterable[Any], *, include_notes=False) -> str:
    """Keep required fields, enums and bounds synchronized with Pydantic."""
    definitions: Dict[str, Any] = {}
    for model in models:
        schema = model.model_json_schema()
        if model is DashboardPlan and not layout_templates_enabled():
            # Legacy input remains readable, but is not an active model option.
            schema["properties"].pop("layout_template", None)
            schema.get("$defs", {}).pop("DashboardLayoutTemplate", None)
        definitions[model.__name__] = schema
        definitions.update(schema.get("$defs", {}))
    lines = ["Validation shapes (generated from server models; ! means required):"]
    for name, schema in definitions.items():
        if "properties" not in schema:
            lines.append(f"{name} = {_schema_type(schema)}")
            continue
        required = set(schema.get("required", []))
        fields = "; ".join(
            f"{key}{'!' if key in required else '?'}: {_schema_type(value)}"
            + (
                " (" + value["description"] + ")"
                if include_notes and value.get("description")
                else ""
            )
            for key, value in schema["properties"].items()
        )
        extra = "; no extra keys" if schema.get("additionalProperties") is False else ""
        lines.append(f"{name} = {{{fields}}}{extra}")
    return "\n".join(lines)


def describe_registered_tools(tool_pack: Any) -> str:
    """The displayed inventory is exactly the final, permission-filtered ToolPack."""
    # ReAct already injects each resource's complete description/parameter notes
    # in ACTION SPACE. Do not repeat those paragraphs in the workflow inventory.
    lines = [
        "Tool descriptions and parameter notes appear once in ACTION SPACE. "
        "Unknown top-level keys are rejected, not silently discarded."
    ]
    names = set()
    for resource in tool_pack.sub_resources:
        names.add(resource.name)
        parameters = {
            name: {
                "type": value.type,
                "required": value.required,
            }
            for name, value in resource.args.items()
        }
        lines.append(
            f"- {resource.name}: Action Input parameters: "
            + json.dumps(parameters, ensure_ascii=False, separators=(",", ":"))
        )
    models = []
    if names.intersection({"plan_dashboard", "revise_dashboard_plan"}):
        from ..dashboard.chart_selection import PLAN_POINT_GUIDANCE

        lines.append(PLAN_POINT_GUIDANCE)
        models.append(DashboardPlan)
    if names.intersection({"create_dashboard_draft", "repair_dashboard_draft"}):
        models.append(DashboardQueryDraftRequest)
        lines.append(
            "widget_queries is the OUTER tool argument; its widgets array is nested, "
            "never a top-level Action Input key. Creation passes dashboard_id and "
            "expected_revision alongside widget_queries. Repair puts identity inside "
            "widget_queries. Existing JSON-string and draft aliases remain accepted."
        )
    if models:
        lines.append(validation_model_contracts(models))
    if "propose_dashboard_change" in names:
        lines.append(
            "operations is an array of stable-id patch objects, not an operation "
            "name. Existing JSON-encoded arrays and the exact {operations:[...]} "
            "wrapper remain accepted. before/after are arrays of strings."
        )
        lines.append(
            validation_model_contracts([DashboardProposalToolInput], include_notes=True)
        )
    return "\n\n".join(lines)
