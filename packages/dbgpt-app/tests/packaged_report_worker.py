"""Exercise installed-wheel provisioning and report generation in a fresh child.

Only the model replies and message memory are deterministic test substitutes;
the agent builder, tool loop, template loader, renderer and capture are real.
"""

import asyncio
import json
import sys
from pathlib import Path
from unittest.mock import patch


async def main():
    installed, workspace, repository = map(Path, sys.argv[1:4])
    for package in sorted((repository / "packages").iterdir()):
        if package.name != "dbgpt-app" and (package / "src").is_dir():
            sys.path.insert(0, str(package / "src"))
    sys.path.insert(0, str(installed))

    import dbgpt_app
    from dbgpt.agent.core.memory.gpts.default_gpts_memory import (
        DefaultGptsMessageMemory,
    )
    from dbgpt.configs import model_config
    from dbgpt.core import LLMClient, ModelMetadata, ModelOutput
    from dbgpt.core.interface.report_capture import (
        ArtifactCaptureContext,
        InMemoryArtifactSink,
        capture_sql_execution,
    )
    from dbgpt_app.initialization.skills_provisioning import ensure_builtin_skills
    from dbgpt_app.openapi.api_v1.subagent import report_agent
    from dbgpt_app.openapi.api_v1.tools import report_repair

    assert Path(dbgpt_app.__file__).resolve().is_relative_to(installed.resolve())
    assert Path(report_agent.__file__).resolve().is_relative_to(installed.resolve())
    skills = workspace / "deployed_skills"
    ensure_builtin_skills(str(skills))
    expected = {
        "business-report",
        "csv-data-analysis",
        "skill-creator",
        "financial-report-analyzer",
        "walmart-sales-analyzer",
        "agent-browser",
    }
    assert expected.issubset({p.name for p in skills.iterdir()})
    for skill in expected:
        assert (skills / skill / "SKILL.md").is_file(), skill
    model_config.PILOT_PATH = str(workspace)
    report_repair.PILOT_PATH = str(workspace)
    sink = InMemoryArtifactSink(
        ArtifactCaptureContext(conv_uid="wheel-default-report", run_id="packaged-run")
    )
    artifact_id = capture_sql_execution(
        sql="SELECT 30 AS sales",
        database="fixture",
        duration_ms=1,
        columns=["sales"],
        rows=[{"sales": 30}],
        artifact_sink=sink,
    )
    spec = {
        "title": "Wheel default report",
        "sections": [
            {
                "heading": "Sales analysis",
                "intro": [
                    [
                        "Total sales: ",
                        {"artifact_id": artifact_id, "path": ["rows", 0, "sales"]},
                    ]
                ],
            }
        ],
    }

    class ScriptedClient(LLMClient):
        def __init__(self):
            self.tool_turns = 0

        async def models(self):
            return [
                ModelMetadata(
                    model="package-test", context_length=32768, function_calling=True
                )
            ]

        async def count_token(self, model, prompt):
            return len(str(prompt)) // 4

        async def generate(self, request, message_converter=None):
            if not request.tools:
                return ModelOutput(error_code=0, text="Report rendering succeeded.")
            self.tool_turns += 1
            if self.tool_turns == 1:
                name = "html_interpreter"
                arguments = {
                    "template_path": report_agent.REPORT_TEMPLATE_PATH,
                    "title": spec["title"],
                    "data": {"REPORT_SPEC": spec},
                }
            else:
                name = "terminate"
                arguments = {
                    "output": "The report was rendered with captured sales evidence."
                }
            return ModelOutput(
                error_code=0,
                text="",
                tool_calls=[
                    {
                        "id": f"call-{self.tool_turns}",
                        "type": "function",
                        "function": {"name": name, "arguments": json.dumps(arguments)},
                    }
                ],
            )

        async def generate_stream(self, request, message_converter=None):
            yield await self.generate(request, message_converter)

    state = {"conv_id": "wheel-default-report", "_report_artifact_sink": sink}
    client = ScriptedClient()
    # No selected template, injected saved spec or pre-rendered HTML is provided.
    assert (
        report_agent.select_report_template(state, str(skills))
        == report_agent.REPORT_TEMPLATE_PATH
    )
    with patch(
        "dbgpt_serve.agent.agents.db_gpts_memory.MetaDbGptsMessageMemory",
        DefaultGptsMessageMemory,
    ):
        agent = await report_agent.build_report_agent(
            react_state=state,
            llm_client=client,
            skills_dir=str(skills),
            model_name="package-test",
        )
        assert agent is not None
        generate = report_agent.make_generate_report_tool(
            react_state=state,
            llm_client=client,
            skills_dir=str(skills),
            model_name="package-test",
        )
        response = json.loads(
            await generate("Generate a report from the captured sales result.")
        )
    assert response["status"] == "completed", response
    html = state["_report_presentation"]["content"]
    assert "Sales analysis" in html and "30" in html
    assert artifact_id in html
    assert not state.get("_report_html_error"), state.get("_report_html_error")
    (workspace / "generated-report.html").write_text(html, encoding="utf-8")
    # Provisioning must retain user edits on a subsequent application startup.
    skill_file = skills / "business-report/SKILL.md"
    skill_file.write_text("user-edited-skill", encoding="utf-8")
    ensure_builtin_skills(str(skills))
    assert skill_file.read_text(encoding="utf-8") == "user-edited-skill"
    print(
        json.dumps(
            {
                "imported_app": dbgpt_app.__file__,
                "template": state["_report_template_path"],
                "provisioned_skills": sorted(expected),
                "agent_built": True,
                "status": response["status"],
                "model_tool_turns": client.tool_turns,
                "html": str(workspace / "generated-report.html"),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
