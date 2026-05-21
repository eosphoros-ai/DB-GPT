"""Tests for the skill manager."""

import json
from pathlib import Path

import pytest

from dbgpt.agent.skill.manage import SkillManager
from dbgpt.configs import model_config


def _write_marker_script(skill_dir: Path) -> None:
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: test-skill\ndescription: Test skill\n---\n",
        encoding="utf-8",
    )
    scripts_dir = skill_dir / "scripts"
    scripts_dir.mkdir(parents=True)
    (scripts_dir / "touch_marker.py").write_text(
        "\n".join(
            [
                "import json",
                "import sys",
                "from pathlib import Path",
                "",
                "args = json.loads(sys.argv[1])",
                "Path(args['marker']).write_text('executed', encoding='utf-8')",
                "print('executed')",
            ]
        ),
        encoding="utf-8",
    )


def test_personal_skill_path_detection_normalizes_case(tmp_path, monkeypatch):
    skills_dir = tmp_path / "skills"
    user_skill_dir = skills_dir / "user" / "uploaded-skill"
    user_skill_dir.mkdir(parents=True)

    monkeypatch.setattr(model_config, "SKILLS_DIR", str(skills_dir))
    monkeypatch.setattr("os.path.normcase", lambda path: str(path).lower())

    assert SkillManager._is_personal_skill_path(
        str(skills_dir / "User" / "uploaded-skill")
    )


@pytest.mark.asyncio
async def test_execute_skill_script_file_allows_uploaded_personal_skill_by_default(
    tmp_path, monkeypatch
):
    skills_dir = tmp_path / "skills"
    skill_dir = skills_dir / "user" / "uploaded-skill"
    _write_marker_script(skill_dir)
    marker = tmp_path / "marker.txt"

    monkeypatch.setattr(model_config, "SKILLS_DIR", str(skills_dir))
    monkeypatch.delenv("DBGPT_DISABLE_PERSONAL_SKILL_SCRIPT_EXECUTION", raising=False)

    result = await SkillManager(None).execute_skill_script_file(
        "uploaded-skill",
        "touch_marker.py",
        {"marker": str(marker)},
    )

    result_text = json.dumps(json.loads(result), ensure_ascii=False)
    assert "executed" in result_text
    assert marker.read_text(encoding="utf-8") == "executed"


@pytest.mark.asyncio
async def test_execute_script_rejects_uploaded_personal_skill_when_disabled(
    tmp_path, monkeypatch
):
    skills_dir = tmp_path / "skills"
    skill_dir = skills_dir / "user" / "uploaded-skill"
    _write_marker_script(skill_dir)
    marker = tmp_path / "marker.txt"

    monkeypatch.setattr(model_config, "SKILLS_DIR", str(skills_dir))
    monkeypatch.setenv("DBGPT_DISABLE_PERSONAL_SKILL_SCRIPT_EXECUTION", "true")

    result = await SkillManager(None).execute_script(
        "uploaded-skill",
        "touch_marker.py",
        {"marker": str(marker)},
    )

    result_text = json.dumps(json.loads(result), ensure_ascii=False)
    assert "personal" in result_text.lower()
    assert not marker.exists()


@pytest.mark.asyncio
async def test_get_skill_resource_rejects_uploaded_personal_skill_scripts_when_disabled(
    tmp_path, monkeypatch
):
    skills_dir = tmp_path / "skills"
    skill_dir = skills_dir / "user" / "uploaded-skill"
    _write_marker_script(skill_dir)
    marker = tmp_path / "marker.txt"

    monkeypatch.setattr(model_config, "SKILLS_DIR", str(skills_dir))
    monkeypatch.setenv("DBGPT_DISABLE_PERSONAL_SKILL_SCRIPT_EXECUTION", "true")

    result = await SkillManager(None).get_skill_resource(
        "uploaded-skill",
        "scripts/touch_marker.py",
        {"marker": str(marker)},
    )

    result_text = json.dumps(json.loads(result), ensure_ascii=False)
    assert "personal" in result_text.lower()
    assert not marker.exists()


@pytest.mark.asyncio
async def test_execute_skill_script_file_rejects_uploaded_personal_skill_when_disabled(
    tmp_path, monkeypatch
):
    skills_dir = tmp_path / "skills"
    skill_dir = skills_dir / "user" / "uploaded-skill"
    _write_marker_script(skill_dir)
    marker = tmp_path / "marker.txt"

    monkeypatch.setattr(model_config, "SKILLS_DIR", str(skills_dir))
    monkeypatch.setenv("DBGPT_DISABLE_PERSONAL_SKILL_SCRIPT_EXECUTION", "true")

    result = await SkillManager(None).execute_skill_script_file(
        "uploaded-skill",
        "touch_marker.py",
        {"marker": str(marker)},
    )

    result_text = json.dumps(json.loads(result), ensure_ascii=False)
    assert "disabled" in result_text.lower()
    assert not marker.exists()


@pytest.mark.asyncio
async def test_execute_skill_script_file_allows_builtin_skill(tmp_path, monkeypatch):
    skills_dir = tmp_path / "skills"
    skill_dir = skills_dir / "builtin-skill"
    _write_marker_script(skill_dir)
    marker = tmp_path / "marker.txt"

    monkeypatch.setattr(model_config, "SKILLS_DIR", str(skills_dir))

    result = await SkillManager(None).execute_skill_script_file(
        "builtin-skill",
        "touch_marker.py",
        {"marker": str(marker)},
    )

    result_text = json.dumps(json.loads(result), ensure_ascii=False)
    assert "executed" in result_text
    assert marker.read_text(encoding="utf-8") == "executed"
