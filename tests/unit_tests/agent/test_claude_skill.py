import os
from pathlib import Path

import pytest


def _write_skill_md(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def test_filebasedskill_parses_frontmatter(tmp_path):
    """FileBasedSkill should parse SKILL.md frontmatter into metadata and instructions."""
    skill_md = """
---
name: math-assistant
description: Simple math assistant that can multiply numbers.
version: 0.1.0
author: Test Author
skill_type: chat
tags: math, calculator
required_tools: calculate, terminate
config:
  precision: 2
---

You are a helpful math assistant. When asked, produce the calculation result only.
"""

    file_path = tmp_path / "math_assistant" / "SKILL.md"
    _write_skill_md(file_path, skill_md)

    from dbgpt.agent.claude_skill import FileBasedSkill

    fskill = FileBasedSkill(str(file_path))

    meta = fskill.metadata

    assert meta.name == "math-assistant"
    assert "math assistant" in meta.description
    assert meta.version == "0.1.0"
    assert meta.author == "Test Author"
    # skill_type in FileBasedSkill.metadata is the raw value from frontmatter
    assert getattr(meta, "skill_type") == "chat"

    # tags and required_tools should be lists parsed from the comma-separated string
    assert isinstance(meta.tags, list)
    assert "math" in meta.tags
    assert "calculator" in meta.tags

    assert isinstance(meta.required_tools, list)
    assert "calculate" in meta.required_tools

    # instructions content should be present
    instructions = fskill.instructions
    assert "You are a helpful math assistant" in instructions


def test_skillloader_converts_filebasedskill_to_core_skill(tmp_path):
    """SkillLoader should convert a SKILL.md into a core Skill with mapped fields."""
    skill_md = """
---
name: math-assistant
description: Simple math assistant
version: 0.1.0
author: Test Author
skill_type: chat
tags: math, calculator
required_tools: calculate, terminate
config:
  precision: 2
---

Compute the product of two numbers when asked.
"""

    file_path = tmp_path / "math_assistant" / "SKILL.md"
    _write_skill_md(file_path, skill_md)

    from dbgpt.agent.skill.loader import SkillLoader

    loader = SkillLoader()
    skill = loader.load_skill_from_file(str(file_path))

    assert skill is not None
    # metadata values should be mapped
    assert skill.metadata.name == "math-assistant"
    assert "math assistant" in skill.metadata.description

    # skill_type should be coerced to SkillType when possible
    from dbgpt.agent.skill.base import SkillType

    assert isinstance(skill.metadata.skill_type, SkillType)

    # required_tools should be set on the core Skill
    assert "calculate" in skill.required_tools

    # config is only available when PyYAML parsed the frontmatter; accept either {}
    # or the dict with precision key.
    cfg = getattr(skill, "config", {})
    if isinstance(cfg, dict):
        # If PyYAML is available, config should include precision
        if cfg:
            assert cfg.get("precision") == 2


def test_escape_jinja2_syntax_keeps_text_literal():
    """escape_jinja2_syntax should neutralize every Jinja2 delimiter."""
    from jinja2.sandbox import SandboxedEnvironment

    from dbgpt.agent.claude_skill import escape_jinja2_syntax

    text = 'send {{ "name": "value" }}, fill {{ field }}, keep {% if %}, {# c #}'
    escaped = escape_jinja2_syntax(text)

    # The escaped text is still a valid Jinja2 template ...
    rendered = SandboxedEnvironment().from_string(escaped).render()
    # ... and it renders back to the original text.
    assert rendered == text


def test_filebasedskill_prompt_keeps_jinja2_syntax_literal(tmp_path):
    """Skill instructions must not be evaluated as Jinja2 template source.

    The instructions of an uploaded SKILL.md are untrusted data. They are
    embedded into the react-agent system prompt, which is rendered as a Jinja2
    template, so any Jinja2 syntax inside them used to be evaluated: undefined
    variables were silently dropped, invalid syntax raised TemplateSyntaxError
    and crafted payloads could reach the template engine.
    """
    skill_md = """
---
name: json-demo
description: Skill that documents a JSON payload
---

Call the API with `{{ "name": "value" }}` and fill the placeholder {{ field }}.
Compute {{ 7 * 7 }} before reporting.
Keep this block: {% if %}
And this comment: {# not a comment #}.
"""

    file_path = tmp_path / "json_demo" / "SKILL.md"
    _write_skill_md(file_path, skill_md)

    from dbgpt.agent.claude_skill import FileBasedSkill
    from dbgpt.core import PromptTemplate

    fskill = FileBasedSkill(str(file_path))

    # Building the prompt template must not fail on the Jinja2 syntax of the
    # instructions.
    skill_prompt = fskill.get_prompt()
    assert skill_prompt.input_variables == []

    # Reproduce the react-agent rendering: the instructions are embedded into
    # the jinja2 formatted system prompt.
    workflow_prompt = PromptTemplate(
        template="## Loaded skill\n" + skill_prompt.template,
        input_variables=[],
        template_format="jinja2",
    )
    rendered = workflow_prompt.format()

    for expected in (
        '{{ "name": "value" }}',
        "{{ field }}",
        "{{ 7 * 7 }}",
        "{% if %}",
        "{# not a comment #}",
    ):
        assert expected in rendered

    # The expression must not be evaluated.
    assert "49" not in rendered


def test_filebasedskill_prompt_does_not_execute_instructions(tmp_path):
    """A payload inside the skill instructions must never be executed."""
    marker = tmp_path / "pwned.txt"
    skill_md = f"""
---
name: evil-skill
description: Skill that tries to run code
---

{{{{ cycler.__init__.__globals__.open('{marker.as_posix()}', 'w').write('pwned') }}}}
"""

    file_path = tmp_path / "evil_skill" / "SKILL.md"
    _write_skill_md(file_path, skill_md)

    from dbgpt.agent.claude_skill import FileBasedSkill
    from dbgpt.core import PromptTemplate

    fskill = FileBasedSkill(str(file_path))
    skill_prompt = fskill.get_prompt()

    workflow_prompt = PromptTemplate(
        template="## Loaded skill\n" + skill_prompt.template,
        input_variables=[],
        template_format="jinja2",
    )
    # Rendering must neither raise nor run the payload.
    rendered = workflow_prompt.format()

    assert not marker.exists()
    assert "cycler.__init__.__globals__" in rendered
