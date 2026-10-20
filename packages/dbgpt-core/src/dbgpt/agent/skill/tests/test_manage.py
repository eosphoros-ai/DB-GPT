"""Tests for the skill manager."""

import json
import shutil
import zipfile
from pathlib import Path

import pytest

from dbgpt.agent.skill.manage import SkillManager
from dbgpt.configs import model_config


@pytest.mark.asyncio
async def test_skill_creator_cli_initializes_and_packages_skill(tmp_path, monkeypatch):
    """Exercise the actual bundled CLI scripts, including Windows path handling."""
    repository = next(
        parent
        for parent in Path(__file__).resolve().parents
        if (parent / "skills/skill-creator/scripts/init_skill.py").is_file()
    )
    skills_dir = tmp_path / "skills"
    shutil.copytree(repository / "skills/skill-creator", skills_dir / "skill-creator")
    monkeypatch.setattr(model_config, "SKILLS_DIR", str(skills_dir))
    monkeypatch.setenv("PYTHONUTF8", "1")
    manager = SkillManager(None)
    destination = tmp_path / "中文 skills with spaces"
    output_dir = tmp_path / "execution"

    failed = json.loads(
        await manager.execute_skill_script_file(
            "skill-creator",
            "init_skill.py",
            {"skill-name": "sql-data-analysis", "path": str(destination)},
            output_dir=str(output_dir),
        )
    )
    assert failed["success"] is False
    assert not destination.exists()
    assert "argv" in failed["chunks"][-1]["content"]

    argv = ["sql-data-analysis", "--path", str(destination)]
    initialized = json.loads(
        await manager.execute_skill_script_file(
            "skill-creator", "init_skill.py", argv=argv, output_dir=str(output_dir)
        )
    )
    assert initialized["success"] is True, initialized
    assert initialized["script_arguments"] == {"argv": argv}
    skill_dir = destination / "sql-data-analysis"
    assert (skill_dir / "SKILL.md").is_file()
    assert (skill_dir / "scripts/example.py").is_file()

    (skill_dir / "SKILL.md").write_text(
        "---\nname: sql-data-analysis\n"
        "description: Query SQL databases and visualize results.\n---\n"
        "# SQL data analysis\nConnect, query, and visualize SQL data.\n",
        encoding="utf-8",
    )
    packaged = json.loads(
        await manager.execute_skill_script_file(
            "skill-creator",
            "package_skill.py",
            argv=[str(skill_dir), str(tmp_path / "dist")],
            output_dir=str(output_dir),
        )
    )
    assert packaged["success"] is True, packaged
    with zipfile.ZipFile(tmp_path / "dist/sql-data-analysis.skill") as archive:
        assert "sql-data-analysis/SKILL.md" in archive.namelist()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "args,argv", [({"marker": "unused"}, ["x"]), (None, "x"), (None, [1])]
)
async def test_skill_cli_rejects_ambiguous_or_invalid_arguments(
    tmp_path, monkeypatch, args, argv
):
    skill_dir = tmp_path / "skills/test-skill"
    _write_marker_script(skill_dir)
    monkeypatch.setattr(model_config, "SKILLS_DIR", str(skill_dir.parent))
    with pytest.raises(ValueError, match="either args"):
        await SkillManager(None).execute_skill_script_file(
            "test-skill", "touch_marker.py", args, argv=argv
        )


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
async def test_execute_script_allows_uploaded_personal_skill_by_default(
    tmp_path, monkeypatch
):
    skills_dir = tmp_path / "skills"
    skill_dir = skills_dir / "user" / "uploaded-skill"
    _write_marker_script(skill_dir)
    marker = tmp_path / "marker.txt"

    class FakeCodeResult:
        output = b"executed"
        error_message = b""

    class FakeCodeServer:
        async def exec(self, code, language):
            marker.write_text("executed", encoding="utf-8")
            return FakeCodeResult()

    async def fake_get_code_server(system_app):
        return FakeCodeServer()

    monkeypatch.setattr(model_config, "SKILLS_DIR", str(skills_dir))
    monkeypatch.delenv("DBGPT_DISABLE_PERSONAL_SKILL_SCRIPT_EXECUTION", raising=False)
    monkeypatch.setattr("dbgpt.util.code.server.get_code_server", fake_get_code_server)

    result = await SkillManager(None).execute_script(
        "uploaded-skill",
        "touch_marker.py",
        {"marker": str(marker)},
    )

    result_text = json.dumps(json.loads(result), ensure_ascii=False)
    assert "executed" in result_text
    assert marker.read_text(encoding="utf-8") == "executed"


@pytest.mark.asyncio
async def test_get_skill_resource_allows_uploaded_personal_skill_scripts_by_default(
    tmp_path, monkeypatch
):
    skills_dir = tmp_path / "skills"
    skill_dir = skills_dir / "user" / "uploaded-skill"
    _write_marker_script(skill_dir)
    executed = {}

    async def fake_execute_script_from_path(self, script_path, args):
        executed["script_path"] = script_path
        executed["args"] = args
        return json.dumps({"chunks": [{"output_type": "text", "content": "ok"}]})

    monkeypatch.setattr(model_config, "SKILLS_DIR", str(skills_dir))
    monkeypatch.delenv("DBGPT_DISABLE_PERSONAL_SKILL_SCRIPT_EXECUTION", raising=False)
    monkeypatch.setattr(
        SkillManager,
        "_execute_script_from_path",
        fake_execute_script_from_path,
    )

    result = await SkillManager(None).get_skill_resource(
        "uploaded-skill",
        "scripts/touch_marker.py",
        {"marker": "value"},
    )

    result_text = json.dumps(json.loads(result), ensure_ascii=False)
    assert "ok" in result_text
    assert executed["script_path"].endswith("scripts/touch_marker.py")
    assert executed["args"] == {"marker": "value"}


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
