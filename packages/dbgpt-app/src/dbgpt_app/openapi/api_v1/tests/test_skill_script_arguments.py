"""CLI skill arguments must survive the tool and evidence-capture boundary."""

import json
import shutil
import zipfile
from pathlib import Path

import pytest

from dbgpt.agent.expand.tool_calling_agent import _build_openai_tools
from dbgpt.agent.resource.tool.pack import ToolPack
from dbgpt.agent.skill.manage import SkillManager
from dbgpt.configs import model_config
from dbgpt.core.interface.report_capture import (
    ArtifactCaptureContext,
    InMemoryArtifactSink,
)
from dbgpt_app.openapi.api_v1.tools.code_interpreter import make_code_interpreter
from dbgpt_app.openapi.api_v1.tools.skill_tools import make_execute_skill_script_file


@pytest.mark.asyncio
async def test_skill_creation_can_write_test_read_and_package_files(
    tmp_path, monkeypatch
):
    """Run the tools needed after initialization, rather than just a template."""
    repository = next(
        parent
        for parent in Path(__file__).resolve().parents
        if (parent / "skills/skill-creator").is_dir()
    )
    skills_dir = tmp_path / "skills"
    shutil.copytree(repository / "skills/skill-creator", skills_dir / "skill-creator")
    monkeypatch.setattr(model_config, "SKILLS_DIR", str(skills_dir))
    monkeypatch.setattr(model_config, "PILOT_PATH", str(tmp_path / "pilot"))
    monkeypatch.setenv("PYTHONUTF8", "1")
    manager = SkillManager(None)
    monkeypatch.setattr(
        "dbgpt.agent.skill.manage.get_skill_manager", lambda app: manager
    )
    state = {"conv_id": "skill-create-regression"}
    execute = make_execute_skill_script_file(state)
    destination = skills_dir / "user"
    initialized = json.loads(
        await execute(
            "skill-creator",
            "init_skill.py",
            argv=["sql-data-analysis", "--path", str(destination)],
        )
    )
    assert initialized.get("success") is not False, initialized
    skill_dir = destination / "sql-data-analysis"
    skill_md = (
        "---\nname: sql-data-analysis\n"
        "description: Query SQLite databases and visualize results.\n---\n"
        "# SQL analysis\nRun scripts/query.py to query a database.\n"
    )
    query = (
        "import json, sqlite3\n"
        "with sqlite3.connect(':memory:') as db:\n"
        "    rows = db.execute('SELECT 42 AS answer').fetchall()\n"
        "print(json.dumps(rows))\n"
    )
    written = json.loads(
        await make_code_interpreter(state)(
            "from pathlib import Path\n"
            f"root = Path({str(skill_dir)!r})\n"
            f"(root / 'SKILL.md').write_text({skill_md!r}, encoding='utf-8')\n"
            f"(root / 'scripts/query.py').write_text({query!r}, encoding='utf-8')\n"
            "print('skill files written')\n"
        )
    )
    assert written.get("success") is not False, written
    assert (skill_dir / "scripts/query.py").read_text(encoding="utf-8") == query

    # Reading script source must not silently execute it through Lyric.
    from dbgpt_app.openapi.api_v1.agentic_data_api import get_skill_resource

    source = json.loads(
        await get_skill_resource("sql-data-analysis", "scripts/query.py")
    )
    assert source["type"] == "file"
    assert source["content"] == query
    tested = json.loads(await execute("sql-data-analysis", "query.py", argv=[]))
    assert tested.get("success") is not False, tested
    assert any("42" in str(chunk) for chunk in tested["chunks"])
    packaged = json.loads(
        await execute(
            "skill-creator",
            "package_skill.py",
            argv=[str(skill_dir), str(tmp_path / "dist")],
        )
    )
    assert packaged.get("success") is not False, packaged
    with zipfile.ZipFile(tmp_path / "dist/sql-data-analysis.skill") as archive:
        assert (
            archive.read("sql-data-analysis/scripts/query.py")
            == (skill_dir / "scripts/query.py").read_bytes()
        )


@pytest.mark.asyncio
async def test_cli_skill_tool_preserves_arguments_and_records_execution(
    tmp_path, monkeypatch
):
    skill_dir = tmp_path / "skills/cli-skill"
    scripts_dir = skill_dir / "scripts"
    scripts_dir.mkdir(parents=True)
    (scripts_dir / "write.py").write_text(
        "import sys\nfrom pathlib import Path\n"
        "assert sys.argv[2] == '--value'\n"
        "Path(sys.argv[1]).write_text(sys.argv[3], encoding='utf-8')\n"
        "print('written')\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(model_config, "SKILLS_DIR", str(skill_dir.parent))
    monkeypatch.setattr(model_config, "PILOT_PATH", str(tmp_path / "pilot"))
    manager = SkillManager(None)
    monkeypatch.setattr(
        "dbgpt.agent.skill.manage.get_skill_manager", lambda app: manager
    )
    marker = tmp_path / "中文 path with spaces.txt"
    argv = [str(marker), "--value", "a value with spaces; $(literal)"]
    sink = InMemoryArtifactSink(ArtifactCaptureContext(conv_uid="test-cli"))
    execute = make_execute_skill_script_file(
        {"conv_id": "test-cli", "_report_artifact_sink": sink}
    )
    result = json.loads(await execute("cli-skill", "write.py", argv=argv))
    assert result.get("success") is not False, result
    assert marker.read_text(encoding="utf-8") == argv[-1]
    artifact = next(
        a for a in sink.snapshot() if a.artifact_id == result["artifact_id"]
    )
    assert artifact.status == "succeeded"
    assert artifact.metadata["arguments"] == {"argv": argv}

    # Verify the actual native function schema tells the model how to call it.
    schema = _build_openai_tools(ToolPack([execute._tool]))[0]["function"]
    assert {"type": "array", "items": {"type": "string"}} in schema["parameters"][
        "properties"
    ]["argv"]["anyOf"]

    rejected = json.loads(
        await execute("cli-skill", "write.py", args={"x": 1}, argv=argv)
    )
    assert rejected["success"] is False
    assert "not both" in rejected["chunks"][0]["content"]
