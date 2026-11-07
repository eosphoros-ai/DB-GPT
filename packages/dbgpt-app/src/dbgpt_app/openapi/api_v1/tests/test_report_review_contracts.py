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


@pytest.mark.asyncio
@pytest.mark.parametrize("old_sections", [None, "", {}])
async def test_empty_malformed_legacy_sections_recover_through_public_tool(
    tmp_path, monkeypatch, old_sections
):
    monkeypatch.setattr(report_repair, "PILOT_PATH", str(tmp_path))
    sink = InMemoryArtifactSink(ArtifactCaptureContext(conv_uid="legacy-sections"))
    artifact = source(sink)
    state = {"conv_id": "legacy-sections", "_report_artifact_sink": sink}
    renderer = make_html_interpreter(state, str(ROOT / "skills"))
    spec = {
        "title": "Preserved title",
        "scope": "Preserved scope",
        "kpis": [
            {"label": "Revenue", "ref": {"artifact_id": artifact, "field": "revenue"}}
        ],
        "sections": old_sections,
    }
    await renderer(template_path=TEMPLATE, data={"REPORT_SPEC": spec})
    assert state.get("_report_html_error")
    before = deepcopy(state["_report_saved_arguments"]["data"]["REPORT_SPEC"])
    _, _, patch = make_report_object_tools(
        state, renderer, TEMPLATE, {"mode": "spec", "fields": []}
    )
    agent = ToolCallingReActAgent()
    agent.agent_context = AgentContext(
        conv_id="legacy-sections", enable_native_function_calling=True
    )
    agent.resource = ToolPack([patch._tool])
    for action in agent.actions:
        action.init_resource(agent.resource)
    call = "Action: patch_report\nAction Input: " + json.dumps(
        {
            "append_sections": [
                {"heading": "Recovered", "intro": [["Recovered conclusion."]]}
            ]
        }
    )
    out = await agent.act(
        AgentMessage(content=call), sender=agent, parser=agent.parser, tool_calls=None
    )
    assert out.is_exe_success, out
    assert not state.get("_report_html_error")
    after = state["_report_saved_arguments"]["data"]["REPORT_SPEC"]
    for key in ("title", "scope", "kpis"):
        assert after[key] == before[key]
    assert "Recovered conclusion." in state["_report_presentation"]["content"]


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid", [None, "old invalid section", 7, []])
@pytest.mark.parametrize("operation", ["replace", "remove"])
async def test_invalid_section_element_restores_without_losing_valid_content(
    tmp_path, monkeypatch, invalid, operation
):
    monkeypatch.setattr(report_repair, "PILOT_PATH", str(tmp_path))
    sink = InMemoryArtifactSink(ArtifactCaptureContext(conv_uid="invalid-element"))
    artifact = source(sink)
    state = {"conv_id": "invalid-element", "_report_artifact_sink": sink}
    renderer = make_html_interpreter(state, str(ROOT / "skills"))
    spec = {
        "title": "Preserved title",
        "kpis": [
            {"label": "Revenue", "ref": {"artifact_id": artifact, "field": "revenue"}}
        ],
        "sections": [
            {
                "heading": "Keep section",
                "intro": [["Keep conclusion."]],
                "recommendations": [
                    {"title": "Follow up", "lines": [{"parts": ["Keep action."]}]}
                ],
            },
            invalid,
        ],
    }
    await renderer(template_path=TEMPLATE, data={"REPORT_SPEC": spec})
    assert state.get("_report_html_error")
    before = deepcopy(state["_report_saved_arguments"]["data"]["REPORT_SPEC"])
    restored = {"conv_id": "invalid-element", "_report_artifact_sink": sink}
    assert report_repair.restore_report_checkpoint("invalid-element", restored)
    renderer = make_html_interpreter(restored, str(ROOT / "skills"))
    _, _, edit = make_report_object_tools(
        restored, renderer, TEMPLATE, {"mode": "spec", "fields": []}
    )
    rejected = json.loads(await edit(section_index=0, remove_invalid_section=True))
    assert rejected["status"] == "invalid_selection"
    assert restored["_report_saved_arguments"]["data"]["REPORT_SPEC"] == before
    args = {"section_index": 1}
    args.update(
        {"remove_invalid_section": True}
        if operation == "remove"
        else {"section": {"heading": "Repaired", "intro": [["Recovered conclusion."]]}}
    )
    agent = ToolCallingReActAgent()
    agent.agent_context = AgentContext(
        conv_id="invalid-element", enable_native_function_calling=True
    )
    agent.resource = ToolPack([edit._tool])
    for action in agent.actions:
        action.init_resource(agent.resource)
    call = "Action: patch_report\nAction Input: " + json.dumps(args)
    out = await agent.act(
        AgentMessage(content=call), sender=agent, parser=agent.parser, tool_calls=None
    )
    assert out.is_exe_success, out
    assert not restored.get("_report_html_error")
    after = restored["_report_saved_arguments"]["data"]["REPORT_SPEC"]
    assert after["title"] == before["title"]
    assert after["kpis"] == before["kpis"]
    assert after["sections"][0] == before["sections"][0]
    assert len(after["sections"]) == (1 if operation == "remove" else 2)
    assert "Keep action." in restored["_report_presentation"]["content"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "args",
    [
        {"section_index": 0, "remove_invalid_section": True},
        {
            "section_index": 1,
            "remove_invalid_section": True,
            "section": {"heading": "Conflict"},
        },
        {"section_index": True, "section": {"heading": "Invalid index"}},
        {"section_index": 99, "remove_section_fields": ["obsolete"]},
        {
            "section_index": 0,
            "section": {"heading": "Conflict"},
            "remove_section_fields": ["heading"],
        },
        {"remove_fields": ["sections"]},
    ],
)
async def test_rejected_repair_matrix_preserves_saved_document(args):
    state = {
        "_report_saved_arguments": {
            "template_path": TEMPLATE,
            "data": {
                "REPORT_SPEC": {
                    "title": "Keep title",
                    "sections": [
                        {"heading": "Keep heading", "intro": [["Keep conclusion."]]},
                        None,
                    ],
                }
            },
        }
    }
    before = deepcopy(state["_report_saved_arguments"])

    async def forbidden(**kwargs):
        raise AssertionError("Invalid edit must not render")

    _, _, edit = make_report_object_tools(
        state, forbidden, TEMPLATE, {"mode": "spec", "fields": []}
    )
    result = json.loads(await edit(**args))
    assert result["status"] == "invalid_selection"
    assert state["_report_saved_arguments"] == before


@pytest.mark.parametrize(
    "damage",
    [
        "{broken",
        "[]",
        '{"arguments":[]}',
        '{"conv_uid":"corrupt","run_id":"test","artifacts":[{}],"arguments":{}}',
    ],
)
def test_corrupt_checkpoint_preserves_bytes_and_existing_state(
    tmp_path, monkeypatch, damage
):
    monkeypatch.setattr(report_repair, "PILOT_PATH", str(tmp_path))
    path = report_repair._checkpoint_path("corrupt")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(damage, encoding="utf-8")
    state = {
        "conv_id": "corrupt",
        "_report_saved_arguments": {"title": "Keep existing"},
    }
    before = deepcopy(state)
    assert report_repair.restore_report_checkpoint("corrupt", state) is None
    assert state["_report_saved_arguments"] == before["_report_saved_arguments"]
    assert (
        Path(state["_report_corrupt_checkpoint_path"]).read_bytes() == path.read_bytes()
    )
    assert "REPORT_CHECKPOINT_INVALID" in state["_report_checkpoint_error"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "invalid", [{"heading": "legacy object"}, "unparseable text", 42]
)
async def test_explicit_replace_invalid_sections_preserves_root(
    tmp_path, monkeypatch, invalid
):
    monkeypatch.setattr(report_repair, "PILOT_PATH", str(tmp_path))
    sink = InMemoryArtifactSink(ArtifactCaptureContext(conv_uid="replace-root"))
    artifact = source(sink)
    state = {"conv_id": "replace-root", "_report_artifact_sink": sink}
    renderer = make_html_interpreter(state, str(ROOT / "skills"))
    spec = {
        "title": "Keep title",
        "scope": "Keep scope",
        "kpis": [
            {"label": "Revenue", "ref": {"artifact_id": artifact, "field": "revenue"}}
        ],
        "sections": invalid,
    }
    await renderer(template_path=TEMPLATE, data={"REPORT_SPEC": spec})
    assert state.get("_report_html_error")
    _, _, edit = make_report_object_tools(
        state, renderer, TEMPLATE, {"mode": "spec", "fields": []}
    )
    result = json.loads(
        await edit(
            replace_invalid_sections=[
                {"heading": "Recovered", "intro": [["Recovered conclusion."]]}
            ]
        )
    )
    assert result["status"] == "completed", result
    saved = state["_report_saved_arguments"]["data"]["REPORT_SPEC"]
    for key in ("title", "scope", "kpis"):
        assert saved[key] == spec[key]
    rejected = json.loads(await edit(replace_invalid_sections=[]))
    assert rejected["status"] == "invalid_selection"


def test_checkpoint_salvages_valid_artifacts_and_archives_damaged_record(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(report_repair, "PILOT_PATH", str(tmp_path))
    sink = InMemoryArtifactSink(ArtifactCaptureContext(conv_uid="partial-corruption"))
    artifact = source(sink)
    state = {"conv_id": "partial-corruption", "_report_artifact_sink": sink}
    report_repair._save_checkpoint(state, {}, "pending")
    path = report_repair._checkpoint_path("partial-corruption")
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["artifacts"].append({"broken": "record"})
    path.write_text(json.dumps(payload), encoding="utf-8")
    before = path.read_bytes()
    restored = {}
    recovered = report_repair.restore_report_checkpoint("partial-corruption", restored)
    assert [item.artifact_id for item in recovered.snapshot()] == [artifact]
    assert Path(restored["_report_corrupt_checkpoint_path"]).read_bytes() == before
    assert "Skipped 1" in restored["_report_checkpoint_recovery_warnings"]


@pytest.mark.parametrize("invalid", ["damaged", ["damaged"], 1, False])
def test_checkpoint_rejects_invalid_calculation_before_restoring_state(
    tmp_path, monkeypatch, invalid
):
    monkeypatch.setattr(report_repair, "PILOT_PATH", str(tmp_path))
    sink = InMemoryArtifactSink(ArtifactCaptureContext(conv_uid="bad-calculation"))
    source(sink)
    report_repair._save_checkpoint(
        {"conv_id": "bad-calculation", "_report_artifact_sink": sink}, {}, "pending"
    )
    path = report_repair._checkpoint_path("bad-calculation")
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["missing_calculation"] = invalid
    path.write_text(json.dumps(payload), encoding="utf-8")
    state = {"_report_saved_arguments": {"title": "Keep existing"}}
    before = deepcopy(state)
    assert report_repair.restore_report_checkpoint("bad-calculation", state) is None
    assert state["_report_saved_arguments"] == before["_report_saved_arguments"]
    assert "_report_missing_calculation" not in state
    assert "REPORT_CHECKPOINT_INVALID" in state["_report_checkpoint_error"]


@pytest.mark.asyncio
async def test_checkpoint_null_text_can_render_and_save_again(tmp_path, monkeypatch):
    monkeypatch.setattr(report_repair, "PILOT_PATH", str(tmp_path))
    sink = InMemoryArtifactSink(ArtifactCaptureContext(conv_uid="null-text"))
    source(sink)
    report_repair._save_checkpoint(
        {"conv_id": "null-text", "_report_artifact_sink": sink}, {}, "pending"
    )
    path = report_repair._checkpoint_path("null-text")
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload.update(pending_html=None, last_attempt_html=None, title=None)
    path.write_text(json.dumps(payload), encoding="utf-8")
    state = {"conv_id": "null-text"}
    recovered = report_repair.restore_report_checkpoint("null-text", state)
    assert recovered is not None
    state["_report_artifact_sink"] = recovered
    assert await report_repair.render_saved_report(state, str(ROOT / "skills")) is False
    report_repair.save_execution_checkpoint(state, "pending")
    assert path.with_name("pending.html").read_text(encoding="utf-8") == ""
    assert path.with_name("last-attempt.html").read_text(encoding="utf-8") == ""
    assert json.loads(path.read_text(encoding="utf-8"))["title"] == "Report"


@pytest.mark.parametrize("salvage", [False, True])
@pytest.mark.parametrize("operation", ["read_bytes", "write_bytes"])
def test_checkpoint_backup_io_failure_does_not_block_recovery(
    tmp_path, monkeypatch, salvage, operation
):
    monkeypatch.setattr(report_repair, "PILOT_PATH", str(tmp_path))
    sink = InMemoryArtifactSink(ArtifactCaptureContext(conv_uid="backup-failure"))
    artifact = source(sink)
    report_repair._save_checkpoint(
        {"conv_id": "backup-failure", "_report_artifact_sink": sink}, {}, "pending"
    )
    path = report_repair._checkpoint_path("backup-failure")
    if salvage:
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["artifacts"].append({"broken": "record"})
        path.write_text(json.dumps(payload), encoding="utf-8")
    else:
        path.write_text("{broken", encoding="utf-8")
    original = path.read_bytes()

    def fail_io(*args, **kwargs):
        raise PermissionError("backup unavailable")

    state = {"_report_saved_arguments": {"title": "Keep existing"}}
    with monkeypatch.context() as backup_patch:
        backup_patch.setattr(Path, operation, fail_io)
        recovered = report_repair.restore_report_checkpoint("backup-failure", state)
    assert path.read_bytes() == original
    assert "REPORT_CHECKPOINT_BACKUP_FAILED" in state["_report_checkpoint_backup_error"]
    assert "_report_corrupt_checkpoint_path" not in state
    if salvage:
        assert [item.artifact_id for item in recovered.snapshot()] == [artifact]
        assert "Skipped 1" in state["_report_checkpoint_recovery_warnings"]
    else:
        assert recovered is None
        assert state["_report_saved_arguments"] == {"title": "Keep existing"}
        assert "REPORT_CHECKPOINT_INVALID" in state["_report_checkpoint_error"]


@pytest.mark.asyncio
async def test_unreadable_checkpoint_can_rebuild_from_available_evidence(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(report_repair, "PILOT_PATH", str(tmp_path))
    sink = InMemoryArtifactSink(ArtifactCaptureContext(conv_uid="rebuild-corrupt"))
    source(sink)
    state = {"conv_id": "rebuild-corrupt", "_report_artifact_sink": sink}
    path = report_repair._checkpoint_path("rebuild-corrupt")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"{truncated checkpoint")
    assert report_repair.restore_report_checkpoint("rebuild-corrupt", state) is None
    backup = Path(state["_report_corrupt_checkpoint_path"])
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
                "title": "Rebuilt report",
                "kpis": [{"label": "Revenue", "object_id": token}],
                "sections": [
                    {
                        "heading": "Recovered",
                        "intro": [["Rebuilt from available evidence."]],
                    }
                ],
            }
        )
    )
    assert result["status"] == "completed", result
    assert backup.read_bytes() == b"{truncated checkpoint"
    assert (
        "Rebuilt from available evidence." in state["_report_presentation"]["content"]
    )
