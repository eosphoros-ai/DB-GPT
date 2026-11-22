from pathlib import Path

import pytest

from dbgpt.configs import model_config
from dbgpt_app.openapi.api_v1.dashboard import assistant_skills, gallery_templates


@pytest.mark.parametrize("packaged_internal", [False, True])
def test_private_skills_resolve_nested_resources_without_using_legacy_copies(
    tmp_path, monkeypatch, packaged_internal
):
    local = tmp_path / "workspace"
    packaged = tmp_path / "installed"
    monkeypatch.setattr(model_config, "SKILLS_DIR", str(local))
    monkeypatch.setattr(assistant_skills, "bundled_resource_dir", lambda _: packaged)
    names = (
        "dashboard-collaboration",
        "dashboard-chart-configuration",
        "dashboard-filter-configuration",
        "dashboard-design",
    )
    for root in (local, packaged):
        for name in names:
            legacy = root / name / "SKILL.md"
            legacy.parent.mkdir(parents=True)
            legacy.write_text("stale top-level skill", encoding="utf-8")
            if root == packaged and not packaged_internal:
                continue
            nested = root / "dashboard-builder/internal" / name / "SKILL.md"
            nested.parent.mkdir(parents=True)
            nested.write_text(f"---\nname: {name}\n---\n{root.name}/{name}", "utf-8")

    selected = packaged if packaged_internal else local
    assistant_skills.dashboard_collaboration_skill.cache_clear()
    assistant_skills.dashboard_configuration_skill.cache_clear()
    try:
        assert assistant_skills.dashboard_collaboration_skill() == (
            f"{selected.name}/dashboard-collaboration"
        )
        assert assistant_skills.dashboard_configuration_skill("filter") == (
            f"{selected.name}/dashboard-filter-configuration"
        )
        assert assistant_skills.dashboard_configuration_skill("widget") == (
            f"{selected.name}/dashboard-chart-configuration\n\n"
            f"{selected.name}/dashboard-filter-configuration"
        )
        assert gallery_templates.design_skill_root() == (
            selected / "dashboard-builder/internal/dashboard-design"
        )
    finally:
        assistant_skills.dashboard_collaboration_skill.cache_clear()
        assistant_skills.dashboard_configuration_skill.cache_clear()


@pytest.mark.asyncio
@pytest.mark.parametrize("empty_legacy_directories", [False, True])
async def test_skill_list_keeps_generic_and_user_skills_but_hides_private_helpers(
    tmp_path, monkeypatch, empty_legacy_directories
):
    import shutil

    from dbgpt.agent.claude_skill import SkillRegistry
    from dbgpt_app.openapi.api_v1 import agentic_data_api

    repository = Path(__file__).resolve().parents[8]
    root = tmp_path / "skills"
    for name in ("dashboard-builder", "business-report", "csv-data-analysis"):
        shutil.copytree(repository / "skills" / name, root / name)
    private_names = {
        path.parent.name
        for path in (root / "dashboard-builder/internal").glob("*/SKILL.md")
    }
    assert private_names == {
        "antv-g2-chart",
        "brutal-viz-design",
        "dashboard-chart-configuration",
        "dashboard-collaboration",
        "dashboard-design",
        "dashboard-filter-configuration",
        "serenityspa-viz-design",
    }
    if empty_legacy_directories:
        for name in private_names:
            (root / name).mkdir()
    personal = root / "user/my-dashboard-helper/SKILL.md"
    personal.parent.mkdir(parents=True)
    personal.write_text(
        "---\nname: my-dashboard-helper\ndescription: User's own skill\n---\nHelp me.",
        encoding="utf-8",
    )
    registry = SkillRegistry()
    registry.load_from_directory(str(root))
    assert private_names.issubset({skill.name for skill in registry.list_skills()})
    monkeypatch.setattr(agentic_data_api, "DEFAULT_SKILLS_DIR", str(root))
    result = await agentic_data_api.list_skills(user_token=None)
    assert result.success, result.err_msg
    assert {skill["name"] for skill in result.data} == {
        "dashboard-builder",
        "business-report",
        "csv-data-analysis",
        "my-dashboard-helper",
    }
