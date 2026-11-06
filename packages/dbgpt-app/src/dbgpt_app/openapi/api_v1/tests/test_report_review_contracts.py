"""Cross-boundary invariants for report editing, rejection and localization."""

import json
from copy import deepcopy
from functools import partial
from pathlib import Path

import pytest

from dbgpt.agent import AgentContext, AgentMessage
from dbgpt.agent.expand.tool_calling_agent import ToolCallingReActAgent
from dbgpt.agent.resource.tool.pack import ToolPack
from dbgpt.core.interface.report_capture import (
    ArtifactCaptureContext,
    InMemoryArtifactSink,
    capture_python_execution,
)
from dbgpt_app.openapi.api_v1.tools import report_repair
from dbgpt_app.openapi.api_v1.tools.html_interpreter import make_html_interpreter
from dbgpt_app.openapi.api_v1.tools.report_objects import make_report_object_tools

ROOT = Path(__file__).resolve().parents[7]
TEMPLATE = "business-report/templates/business_report.html"


@pytest.mark.asyncio
@pytest.mark.parametrize("field", ["obsolete", "chart"])
async def test_remove_section_field_preserves_other_content(
    tmp_path, monkeypatch, field
):
    monkeypatch.setattr(report_repair, "PILOT_PATH", str(tmp_path))
    sink = InMemoryArtifactSink(ArtifactCaptureContext(conv_uid="section-delete"))
    artifact = source(sink)
    state = {"conv_id": "section-delete", "_report_artifact_sink": sink}
    renderer = make_html_interpreter(state, str(ROOT / "skills"))
    spec = {
        "title": "Business report",
        "kpis": [
            {"label": "Revenue", "ref": {"artifact_id": artifact, "field": "revenue"}}
        ],
        "sections": [
            {
                "heading": "Existing",
                "intro": [["Keep the conclusion."]],
                "recommendations": [
                    {"title": "Follow up", "lines": [{"parts": ["Keep the action."]}]}
                ],
                field: "invalid old value",
            },
            {"heading": "Untouched", "intro": [["Keep this section."]]},
        ],
    }
    await renderer(template_path=TEMPLATE, data={"REPORT_SPEC": spec})
    assert state.get("_report_html_error")
    before = deepcopy(state["_report_saved_arguments"]["data"]["REPORT_SPEC"])
    _, _, patch = make_report_object_tools(
        state, renderer, TEMPLATE, {"mode": "spec", "fields": []}
    )
    rejected = json.loads(await patch(section_index=99, remove_section_fields=[field]))
    assert rejected["status"] == "invalid_selection"
    assert state["_report_saved_arguments"]["data"]["REPORT_SPEC"] == before
    result = json.loads(await patch(section_index=0, remove_section_fields=[field]))
    assert result.get("status") == "completed", result
    expected = deepcopy(before)
    del expected["sections"][0][field]
    assert state["_report_saved_arguments"]["data"]["REPORT_SPEC"] == expected
    assert "Keep the action." in state["_report_presentation"]["content"]


@pytest.mark.asyncio
@pytest.mark.parametrize("replacement", ["structured", "scalar", "delete"])
@pytest.mark.parametrize("legacy", [False, True])
async def test_scope_edit_replaces_generated_scope_after_restore(
    tmp_path, monkeypatch, replacement, legacy
):
    monkeypatch.setattr(report_repair, "PILOT_PATH", str(tmp_path))
    sink = InMemoryArtifactSink(ArtifactCaptureContext(conv_uid="scope-replace"))
    source(sink)
    state = {"conv_id": "scope-replace", "_report_artifact_sink": sink}
    renderer = make_html_interpreter(state, str(ROOT / "skills"))
    listing, compose, _ = make_report_object_tools(
        state, renderer, TEMPLATE, {"mode": "spec", "fields": []}
    )
    token = json.loads(listing(kind="value"))["objects"][0]["object_id"]
    initial = json.loads(
        await compose(
            {
                "title": "Business report",
                "scope": ["Old scope.", {"object_id": token}],
                "kpis": [{"label": "Revenue", "object_id": token}],
                "sections": [
                    {"heading": "数据范围", "intro": [["User scope section."]]}
                ],
            }
        )
    )
    assert initial.get("status") == "completed", initial
    before = deepcopy(state["_report_saved_arguments"]["data"]["REPORT_SPEC"])
    if legacy:
        old_spec = deepcopy(before)
        del old_spec["sections"][0]["source_field"]
        result = json.loads(
            await renderer(template_path=TEMPLATE, data={"REPORT_SPEC": old_spec})
        )
        assert result.get("status") == "completed", result
    restored = {"conv_id": "scope-replace", "_report_artifact_sink": sink}
    assert report_repair.restore_report_checkpoint(
        "scope-replace", restored, include_completed=True
    )
    renderer = make_html_interpreter(restored, str(ROOT / "skills"))
    _, _, patch = make_report_object_tools(
        restored, renderer, TEMPLATE, {"mode": "spec", "fields": []}
    )
    args = (
        {"remove_fields": ["scope"]}
        if replacement == "delete"
        else {
            "report": {
                "scope": ["New scope.", {"object_id": token}]
                if replacement == "structured"
                else "New scope."
            }
        }
    )
    if legacy:
        args["scope_section_index"] = 0
    for _ in range(2):
        result = json.loads(await patch(**args))
        args.pop("scope_section_index", None)
        assert result.get("status") == "completed", result
        html = restored["_report_presentation"]["content"]
        assert "Old scope." not in html
        assert "User scope section." in html
        assert ("New scope." in html) == (replacement != "delete")
        after = restored["_report_saved_arguments"]["data"]["REPORT_SPEC"]
        assert after["kpis"] == before["kpis"]
        user_sections = [
            s for s in after["sections"] if s.get("source_field") != "scope"
        ]
        assert user_sections == before["sections"][1:]
        generated = [s for s in after["sections"] if s.get("source_field") == "scope"]
        assert len(generated) == (1 if replacement == "structured" else 0)


def source(sink):
    return capture_python_execution(
        code="result",
        duration_ms=1,
        status="succeeded",
        exit_code=0,
        stdout="",
        stderr="",
        result_inline={"revenue": 100},
        artifact_sink=sink,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("remove", [False, True])
async def test_top_level_kpi_repair_preserves_sections_and_bindings(
    tmp_path, monkeypatch, remove
):
    monkeypatch.setattr(report_repair, "PILOT_PATH", str(tmp_path))
    sink = InMemoryArtifactSink(ArtifactCaptureContext(conv_uid="root-repair"))
    artifact = source(sink)
    state = {"conv_id": "root-repair", "_report_artifact_sink": sink}
    renderer = make_html_interpreter(state, str(ROOT / "skills"))
    spec = {
        "title": "Business report",
        "scope": "Original scope",
        "kpis": [
            {"label": "Revenue", "ref": {"artifact_id": artifact, "field": "reveneu"}}
        ],
        "sections": [
            {
                "heading": "Existing",
                "intro": [["Keep the original conclusion."]],
                "recommendations": [
                    {
                        "title": "Original action",
                        "lines": [{"parts": ["Keep the original action."]}],
                    }
                ],
            }
        ],
    }
    if remove:
        spec["obsolete"] = "Unsupported old root field"
    await renderer(template_path=TEMPLATE, data={"REPORT_SPEC": spec})
    assert state.get("_report_html_error")
    before = deepcopy(state["_report_saved_arguments"]["data"]["REPORT_SPEC"])
    listing, _, patch = make_report_object_tools(
        state, renderer, TEMPLATE, {"mode": "spec", "fields": []}
    )
    token = json.loads(listing(kind="value"))["objects"][0]["object_id"]
    result = json.loads(
        await patch(
            report={
                "title": "Corrected report",
                "kpis": [{"label": "Revenue", "object_id": token}],
            },
            remove_fields=["scope", "obsolete"] if remove else None,
        )
    )
    assert result.get("status") == "completed", result
    after = state["_report_saved_arguments"]["data"]["REPORT_SPEC"]
    assert after["sections"] == before["sections"]
    if remove:
        assert "scope" not in after and "obsolete" not in after
    else:
        assert after["scope"] == before["scope"]
    assert after["title"] == "Corrected report"
    assert after["kpis"][0]["ref"]["artifact_id"] == artifact
    assert "100" in state["_report_presentation"]["content"]
    assert "Keep the original action." in state["_report_presentation"]["content"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "tool_name", ["compose_report", "patch_report", "set_report_field"]
)
async def test_repeated_compiler_rejections_stop_before_rendering(
    tmp_path, monkeypatch, tool_name
):
    monkeypatch.setattr(report_repair, "PILOT_PATH", str(tmp_path))
    state = {
        "conv_id": tool_name,
        "_report_html_error": "REPORT_TEMPLATE_PREFLIGHT_INVALID: pending",
        "_report_saved_arguments": {
            "template_path": "report.html",
            "data": {"REPORT_SPEC": {"sections": [{"heading": "Existing"}]}},
        },
    }
    state["_report_invalid_call_handler"] = partial(
        report_repair.record_report_invocation_failure, state
    )

    async def forbidden(**kwargs):
        raise AssertionError("Rejected input must not render")

    spec_mode = tool_name == "patch_report"
    if not spec_mode:
        state["_report_saved_arguments"]["data"] = {"SUMMARY": "Original"}
    tools = make_report_object_tools(
        state,
        forbidden,
        "report.html",
        {
            "mode": "spec" if spec_mode else "placeholders",
            "fields": [] if spec_mode else ["SUMMARY"],
        },
    )
    ref = {"object_id": "value-" + "0" * 24}
    args = (
        {"data": {"SUMMARY": ref}}
        if tool_name == "compose_report"
        else {"section_index": 0, "section": {"intro": [[ref]]}}
        if spec_mode
        else {"field": "SUMMARY", "content": [ref]}
    )
    agent = ToolCallingReActAgent()
    agent.agent_context = AgentContext(
        conv_id=tool_name, enable_native_function_calling=True
    )
    agent.resource = ToolPack([tool._tool for tool in tools])
    for action in agent.actions:
        action.init_resource(agent.resource)
    object.__setattr__(agent, "_report_repair_state", state)
    call = f"Action: {tool_name}\nAction Input: " + json.dumps(args)
    for _ in range(2):
        out = await agent.act(
            AgentMessage(content=call),
            sender=agent,
            parser=agent.parser,
            tool_calls=None,
        )
        assert out.is_exe_success is False
    assert state["_report_preflight_attempts"] == 2
    assert state["_report_tool_call_count"] == 2
    assert state.get("_report_invocation_failures", 0) == 0  # No double counting.
    assert state["_report_retry_exhausted"]
    assert out.have_retry is False


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "language,prefix",
    [("en", "Proposed target (not observed): "), ("zh", "建议目标（非观测值）：")],
)
async def test_numeric_proposals_render_in_report_language(
    tmp_path, monkeypatch, language, prefix
):
    monkeypatch.setattr(report_repair, "PILOT_PATH", str(tmp_path))
    sink = InMemoryArtifactSink(ArtifactCaptureContext(conv_uid="proposal-" + language))
    source(sink)
    state = {
        "conv_id": "proposal-" + language,
        "_report_artifact_sink": sink,
        "_report_language": language,
    }
    listing, compose, _ = make_report_object_tools(
        state,
        make_html_interpreter(state, str(ROOT / "skills")),
        TEMPLATE,
        {"mode": "spec", "fields": []},
    )
    token = json.loads(listing(kind="value"))["objects"][0]["object_id"]
    result = json.loads(
        await compose(
            {
                "title": "Business review",
                "kpis": [{"label": "Baseline", "object_id": token}],
                "sections": [
                    {
                        "heading": "Recommendations",
                        "recommendations": [
                            {
                                "title": "Improve delivery",
                                "goal": "Reduce delays below 10%",
                            }
                        ],
                    }
                ],
            }
        )
    )
    assert result.get("status") == "completed", result
    html = state["_report_presentation"]["content"]
    assert prefix + "Reduce delays below 10%" in html
    if language == "en":
        assert "建议目标（非观测值）" not in html
    assert not state.get("_report_warnings")
