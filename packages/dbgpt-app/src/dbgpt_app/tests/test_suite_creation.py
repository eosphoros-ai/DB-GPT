"""Suite creation tools and prompt contracts are shared by both engines."""

import json
from types import SimpleNamespace

from dbgpt.agent.resource.tool.pack import ToolPack
from dbgpt_app.agent_harness.pi import tool_bridge
from dbgpt_app.openapi.api_v1.harness_pi_stream import (
    _build_pi_prompt,
    _embedded_artifact_outputs,
)
from dbgpt_app.openapi.api_v1.suite_binder import resolve_binding_for_turn
from dbgpt_app.openapi.api_v1.tools.suite_creation import (
    creation_tool_allowed,
    creator_instructions,
    creator_read_step,
    make_suite_creation_tools,
)


def test_shared_tools_build_typed_artifact(monkeypatch, tmp_path):
    from dbgpt_serve.plugins.tests.test_creation import package_files

    monkeypatch.setenv("DBGPT_SUITE_CREATION_DIR", str(tmp_path))
    functions = make_suite_creation_tools("creation-conversation")
    tools = {fn.__name__: fn for fn in functions}
    manifest = [resource.name for resource in ToolPack(functions).sub_resources]
    assert set(manifest) == {
        "suite_draft_create",
        "suite_draft_read",
        "suite_draft_write",
        "suite_draft_validate",
        "suite_package_build",
    }
    assert not any("install" in name for name in manifest)
    draft = json.loads(tools["suite_draft_create"]("weekly report"))["data"]
    written = json.loads(
        tools["suite_draft_write"](
            draft["draft_id"], draft["revision"], json.dumps(package_files())
        )
    )["data"]
    validated = json.loads(
        tools["suite_draft_validate"](draft["draft_id"], written["revision"])
    )["data"]
    assert validated["status"] == "ready"
    result = tools["suite_package_build"](draft["draft_id"], written["revision"])
    parsed = json.loads(result)
    assert parsed["chunks"][0]["output_type"] == "expert_suite"
    assert parsed["chunks"][0]["content"]["artifact_id"]
    embedded = _embedded_artifact_outputs(result)
    assert embedded[0]["output_type"] == "expert_suite"
    assert embedded[0]["content"]["package_digest"]


def test_pi_creation_prompt_and_actual_read_step(monkeypatch):
    monkeypatch.setattr(tool_bridge, "get_react_state", lambda _: {})
    dialogue = SimpleNamespace(
        user_input="创建周报专家套件",
        ext_info={"creation_mode": "expert_suite"},
        conv_uid="creation",
    )
    prompt = _build_pi_prompt(dialogue)
    assert creator_instructions() in prompt
    assert "suite_package_build" in prompt
    step = creator_read_step()
    assert step["action"] == "load_skill"
    assert step["outputs"][1]["content"].endswith(creator_instructions())
    assert resolve_binding_for_turn(dialogue) is None


def test_creation_cannot_route_to_dashboard():
    from dbgpt_app.openapi.api_v1.agentic_data_api import _is_dashboard_workflow_request

    assert not _is_dashboard_workflow_request(
        "创建生成 dashboard 的专家套件", "expert_suite"
    )


def test_creation_exposes_controlled_writes_and_material_reads_only():
    for name in ("suite_draft_write", "suite_package_build", "read", "kb_cat"):
        assert creation_tool_allowed(name)
    for name in ("write", "edit", "bash", "code", "execute_skill_script_file"):
        assert not creation_tool_allowed(name)


def test_pi_creation_filters_late_registered_skill_execution(monkeypatch):
    from dbgpt.agent.resource.tool.base import tool
    from dbgpt_app.openapi.api_v1.subagent import react_tools

    @tool(description="Read a skill")
    def load_skill(skill_name: str) -> str:
        return skill_name

    @tool(description="Execute a skill script")
    def execute_skill_script_file(path: str) -> str:
        return path

    monkeypatch.setattr(react_tools, "make_react_tools", lambda *a, **kw: {})
    monkeypatch.setattr(
        tool_bridge,
        "_skill_tools",
        lambda *a: [load_skill, execute_skill_script_file],
    )
    conv_id = "pi-creation-filter-test"
    try:
        manifest = tool_bridge.register_conv_tools(
            conv_id, {"creation_mode": "expert_suite"}, SimpleNamespace()
        )
        names = {entry["name"] for entry in manifest}
        assert {"load_skill", "suite_draft_write", "suite_package_build"} <= names
        assert "execute_skill_script_file" not in names
    finally:
        tool_bridge._REGISTRY.pop(conv_id, None)
