"""Check internal evidence guidance is injected into the actual report agent."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from dbgpt.agent.core.memory.gpts.default_gpts_memory import DefaultGptsMessageMemory
from dbgpt.core import LLMClient, ModelMetadata
from dbgpt_app.openapi.api_v1.subagent import report_agent


class _Client(LLMClient):
    async def models(self):
        return [
            ModelMetadata(model="test", context_length=32768, function_calling=True)
        ]

    async def generate(self, request, message_converter=None):
        raise AssertionError("building the agent must not call the model")

    async def generate_stream(self, request, message_converter=None):
        raise AssertionError("building the agent must not call the model")
        yield

    async def count_token(self, model, prompt):
        return len(str(prompt)) // 4


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["spec", "placeholders"])
async def test_report_agent_receives_internal_skill_once(monkeypatch, tmp_path, mode):
    repo = next(p for p in Path(__file__).resolve().parents if (p / "skills").is_dir())
    original = report_agent.PromptTemplate
    prompts = []

    def capture(*args, **kwargs):
        prompts.append(kwargs["template"])
        return original(*args, **kwargs)

    monkeypatch.setattr(report_agent, "PromptTemplate", capture)
    skills_dir = repo / "skills"
    if mode == "placeholders":
        skills_dir = tmp_path
        (skills_dir / "custom.html").write_text(
            "<html><body>{{SUMMARY}}</body></html>", encoding="utf-8"
        )
        monkeypatch.setattr(
            report_agent, "select_report_template", lambda *_: "custom.html"
        )
    with patch(
        "dbgpt_serve.agent.agents.db_gpts_memory.MetaDbGptsMessageMemory",
        DefaultGptsMessageMemory,
    ):
        agent = await report_agent.build_report_agent(
            react_state={"conv_id": "internal-skill-test"},
            llm_client=_Client(),
            skills_dir=str(skills_dir),
            model_name="test",
        )
    native_tools = agent._build_native_tools()
    names = {item["function"]["name"] for item in native_tools}
    assert names == {
        "list_report_objects",
        "compose_report",
        "request_report_calculation",
        "terminate",
    } | ({"set_report_field"} if mode == "placeholders" else {"patch_report"})
    compose_schema = next(
        item["function"]["parameters"]
        for item in native_tools
        if item["function"]["name"] == "compose_report"
    )
    assert "object_id" in json.dumps(compose_schema)
    assert "artifact_id" not in json.dumps(compose_schema)
    assert ("data" in compose_schema["required"]) == (mode == "spec")
    if mode == "spec":
        repair_schema = next(
            item["function"]["parameters"]
            for item in native_tools
            if item["function"]["name"] == "patch_report"
        )
        assert "object_id" in json.dumps(repair_schema)
        assert "artifact_id" not in json.dumps(repair_schema)
    assert len(prompts) == 1
    assert prompts[0].count("# 报告证据核查") == 1
    assert "相关性不能当作因果关系" in prompts[0]
    internal = prompts[0].split("<!-- DB-GPT INTERNAL EVIDENCE BEGIN -->")[1]
    assert "note={" not in internal
    assert "section.note" not in internal
    if mode == "spec":
        assert '"label":"知识库口径"' in prompts[0]
    else:
        assert "本模板采用的知识库口径" in prompts[0]
        assert '"label":"知识库口径"' not in prompts[0]
    assert "report-evidence-internal" not in [
        p.name for p in (repo / "skills").iterdir()
    ]
