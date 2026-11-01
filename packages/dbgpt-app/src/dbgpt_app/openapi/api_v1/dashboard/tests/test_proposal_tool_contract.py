"""Exercise annotation parameters through the real pack/repack dispatcher."""

import json

import pytest

from dbgpt.agent.expand.actions.tool_action import run_tool
from dbgpt_app.openapi.api_v1.dashboard.planner import DashboardPlannerService
from dbgpt_app.openapi.api_v1.dashboard.schemas import (
    DashboardAnnotationCreateRequest,
    DashboardChangeProposalRequest,
    DashboardPatchOp,
)
from dbgpt_app.openapi.api_v1.tools.dashboard import make_dashboard_planner_tools
from dbgpt_app.openapi.api_v1.tools.dashboard_contracts import (
    DashboardProposalToolInput,
    describe_registered_tools,
    make_dashboard_tool_pack,
)

from .test_annotations import _target  # noqa: F401
from .test_annotations import annotation_services as _annotation_services_fixture

annotation_services = _annotation_services_fixture


def _proposal(annotation_services):
    annotations, dashboards, _, connector = annotation_services
    created = annotations.create_annotation(
        "annotation-dashboard",
        DashboardAnnotationCreateRequest(
            base_revision=1, target=_target(), prompt="Adjust this component."
        ),
        "alice",
    )
    events = []

    async def capture(kind, payload):
        events.append((kind, payload))

    prompt = f"[[dashboard-annotation:annotation-dashboard:{created.id}]] [修改组件]"
    tools = make_dashboard_planner_tools(
        {},
        connector,
        "demo",
        "alice",
        prompt,
        "offline",
        capture,
        planner_service=DashboardPlannerService(dashboards),
    )
    return (
        make_dashboard_tool_pack(tools, prompt),
        {
            "dashboard_id": "annotation-dashboard",
            "annotation_id": created.id,
            "summary": "Adjust this component.",
        },
        events,
    )


def test_registered_proposal_arguments_are_generated_from_service_fields(
    annotation_services,
):
    pack, _, _ = _proposal(annotation_services)
    tool = next(
        item for item in pack.sub_resources if item.name == "propose_dashboard_change"
    )
    model = DashboardProposalToolInput.model_json_schema()
    assert set(tool.args) == set(model["properties"])
    service_properties = DashboardChangeProposalRequest.model_json_schema()[
        "properties"
    ]
    for name, parameter in tool.args.items():
        assert parameter.type == model["properties"][name]["type"]
        assert parameter.required == (name in model["required"])
        if name in service_properties:
            assert model["properties"][name] == service_properties[name]
    assert tool.args["operations"].type == "array"
    assert tool.args["before"].required is False
    prompt = describe_registered_tools(pack)
    assert "DashboardProposalToolInput =" in prompt
    assert "operations!: array<DashboardStablePatchOperation>" in prompt
    assert "DashboardPatchOp =" in prompt
    for operation in DashboardPatchOp:
        assert json.dumps(operation.value) in prompt
    assert "Required for add and replace" in prompt
    assert "DashboardQueryDraftRequest =" not in prompt
    assert "DashboardPlan =" not in prompt


@pytest.mark.asyncio
@pytest.mark.parametrize("transport", ["array", "json_array", "legacy_wrapper"])
@pytest.mark.parametrize(
    "operation",
    [
        {
            "op": "add",
            "path": "/widgets/by-id/value-card/style/custom_note",
            "value": "Added",
        },
        {
            "op": "replace",
            "path": "/widgets/by-id/value-card/title",
            "value": "Renamed",
        },
        {"op": "remove", "path": "/widgets/by-id/value-card/presentation/precision"},
    ],
)
async def test_all_actual_operations_reach_proposal_without_saving(
    annotation_services, transport, operation
):
    pack, arguments, events = _proposal(annotation_services)
    value = [operation]
    if transport == "json_array":
        value = json.dumps(value)
    elif transport == "legacy_wrapper":
        value = {"operations": value}
    outcome = await run_tool(
        "propose_dashboard_change", {**arguments, "operations": value}, pack
    )
    payload = json.loads(outcome.content)
    assert "__dashboard_change_proposal__" in payload, payload
    proposal = payload["__dashboard_change_proposal__"]["proposal"]
    assert proposal["stable_operations"][0]["op"] == operation["op"]
    saved = annotation_services[1].get_dashboard("annotation-dashboard", "alice")
    assert (
        saved.current_revision == 1
        and saved.schema_payload.widgets[0].title == "Original value"
    )
    assert any(kind == "dashboard.change.proposed" for kind, _ in events)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "value,detail",
    [
        ("remove", "operations: expected a JSON array"),
        ("replace", "operations: expected a JSON array"),
        ("delete", "operations: expected a JSON array"),
        (
            {"op": "remove", "path": "/widgets/by-id/value-card/title"},
            "operations: expected a JSON array",
        ),
        (
            {"operations": [], "ignored": "private-value"},
            "operations: expected a JSON array",
        ),
        ([], "operations: List should have at least 1 item"),
        (
            [{"op": "delete", "path": "/widgets/by-id/value-card/title"}],
            "operations.0.op",
        ),
        (
            [{"op": "replace", "path": "/widgets/by-id/value-card/title"}],
            "value is required",
        ),
        (
            [{"op": "add", "path": "/widgets/by-id/value-card/title"}],
            "value is required",
        ),
        (
            [
                {
                    "op": "replace",
                    "path": "/widgets/by-id/value-card/title",
                    "value": "New",
                    "ignored": "private-value",
                }
            ],
            "operations.0.ignored",
        ),
    ],
)
async def test_malformed_operations_report_the_actual_parameter(
    annotation_services, value, detail
):
    pack, arguments, events = _proposal(annotation_services)
    outcome = await run_tool(
        "propose_dashboard_change", {**arguments, "operations": value}, pack
    )
    payload = json.loads(outcome.content)
    error = payload["__dashboard_tool_error__"]
    assert error["tool"] == "propose_dashboard_change"
    assert detail in error["reason"], error
    assert "private-value" not in outcome.content
    assert "__dashboard_change_proposal__" not in payload
    assert not events
    assert (
        annotation_services[1]
        .get_dashboard("annotation-dashboard", "alice")
        .current_revision
        == 1
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "name,value,detail",
    [
        ("before", "not JSON", "before: expected a JSON array"),
        ("after", [{"text": "not a string"}], "after.0"),
    ],
)
async def test_explanation_errors_are_not_misattributed_to_operations(
    annotation_services, name, value, detail
):
    pack, arguments, _ = _proposal(annotation_services)
    arguments.update(
        {
            "operations": [
                {
                    "op": "replace",
                    "path": "/widgets/by-id/value-card/title",
                    "value": "Updated",
                }
            ],
            name: value,
        }
    )
    outcome = await run_tool("propose_dashboard_change", arguments, pack)
    error = json.loads(outcome.content)["__dashboard_tool_error__"]
    assert detail in error["reason"]


@pytest.mark.asyncio
async def test_misplaced_annotation_operations_are_not_silently_filtered(
    annotation_services,
):
    pack, arguments, events = _proposal(annotation_services)
    outcome = await run_tool(
        "propose_dashboard_change",
        {**arguments, "op": "remove", "path": "/widgets/by-id/value-card/title"},
        pack,
    )
    assert outcome.is_exe_success is False
    assert "Unknown top-level" in outcome.content
    assert "op" in outcome.content and "path" in outcome.content
    assert not events
