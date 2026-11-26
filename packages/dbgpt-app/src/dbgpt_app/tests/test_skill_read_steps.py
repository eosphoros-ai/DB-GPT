"""Skill reads remain observable without inventing an LLM tool invocation."""

from types import SimpleNamespace

from dbgpt_app.openapi.api_v1.skill_read_steps import (
    preloaded_skill_steps,
    skill_read_events,
)


def binding(**changes):
    return SimpleNamespace(
        **{
            "name": "db-analysis",
            "version": "1.1.0",
            "command_skill": "build-dashboard",
            "command_skill_text": "# Dashboard instructions",
            "command_error": "",
            "loaded_documents": [
                {"path": "skills/build-dashboard/SKILL.md", "status": "loaded"},
                {
                    "path": "skills/build-dashboard/references/evidence.md",
                    "status": "loaded",
                    "content": "# Real evidence checks",
                },
            ],
            **changes,
        }
    )


def test_suite_read_contains_actual_main_document_and_preloaded_references():
    step = preloaded_skill_steps(binding=binding())[0]
    assert step["action_input"] == {
        "skill_name": "build-dashboard",
        "file_path": "skills/build-dashboard/SKILL.md",
    }
    assert step["status"] == "done"
    assert "Expert suite: db-analysis@1.1.0" in step["detail"]
    assert "# Dashboard instructions" in step["outputs"][1]["content"]
    assert "# Real evidence checks" in step["outputs"][2]["content"]
    events = skill_read_events(step)
    assert events[0]["type"] == "step.start"
    assert events[1]["action_input"] == step["action_input"]
    assert [event for event in events if event["type"] == "step.chunk"] == [
        {"type": "step.chunk", "id": step["id"], **output} for output in step["outputs"]
    ]
    assert events[-1] == {
        "type": "step.done",
        "id": step["id"],
        "status": "done",
    }


def test_binding_failure_or_unread_document_never_claims_a_successful_skill_read():
    assert not preloaded_skill_steps(binding=binding(command_error="file missing"))
    assert not preloaded_skill_steps(binding=binding(command_skill_text=""))
    assert not preloaded_skill_steps(
        binding=binding(loaded_documents=[{"path": "SKILL.md", "status": "failed"}])
    )


def test_selected_skill_and_suite_have_distinct_persistent_step_ids():
    skill = SimpleNamespace(
        metadata=SimpleNamespace(
            name="dashboard-builder", file_path="/skills/SKILL.md"
        ),
        instructions="# Selected instructions",
    )
    steps = preloaded_skill_steps(binding=binding(), skill=skill)
    assert [step["id"] for step in steps] == [
        "skill-read-suite",
        "skill-read-selected",
    ]
    assert steps[1]["action_input"]["skill_name"] == "dashboard-builder"
    assert "# Selected instructions" in steps[1]["outputs"][1]["content"]


def test_pi_consumes_selected_skill_template_instead_of_prompt_object_repr(monkeypatch):
    from dbgpt_app.openapi.api_v1 import harness_pi_stream

    template = "# Selected skill\n\nUse real SQL."
    monkeypatch.setattr(
        harness_pi_stream.tool_bridge,
        "get_react_state",
        lambda _: {"skill_prompt": SimpleNamespace(template=template)},
    )
    dialogue = SimpleNamespace(
        user_input="执行查询",
        conv_uid="skill-prompt-test",
        ext_info={"skill_name": "sql-data-analysis"},
    )
    prompt = harness_pi_stream._build_pi_prompt(dialogue)
    assert template in prompt
    assert "namespace(template=" not in prompt
    assert "Available DB-GPT skills" not in prompt
