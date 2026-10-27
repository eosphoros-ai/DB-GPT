"""Exercise installed dashboard resources with no checkout skill fallback."""

import asyncio
import json
import sys
from pathlib import Path


async def main():
    installed, workspace, repository = map(Path, sys.argv[1:4])
    for package in sorted((repository / "packages").iterdir()):
        if package.name != "dbgpt-app" and (package / "src").is_dir():
            sys.path.insert(0, str(package / "src"))
    sys.path.insert(0, str(installed))

    import dbgpt_app
    from dbgpt.agent.claude_skill import SkillRegistry
    from dbgpt.configs import model_config
    from dbgpt_app.initialization.skills_provisioning import ensure_builtin_skills

    assert Path(dbgpt_app.__file__).resolve().is_relative_to(installed.resolve())
    # No checkout skill directory, and no previously provisioned skills.
    model_config.SKILLS_DIR = str(workspace / "absent-skills")
    from dbgpt_app.openapi.api_v1 import agentic_data_api
    from dbgpt_app.openapi.api_v1.dashboard import assistant_skills, gallery_templates

    assert "看板协作" in assistant_skills.dashboard_collaboration_skill()
    assert "IN (:category)" in assistant_skills.dashboard_configuration_skill("widget")
    root = gallery_templates.design_skill_root()
    assert root.resolve().is_relative_to(installed.resolve())
    references = sorted((root / "references").glob("*.md"))
    assert len(references) == 9  # Eight references plus their index.
    for path in references:
        if path.name == "index.md":
            continue
        kind, name = path.stem.split("-", 1)
        context = gallery_templates.gallery_plan_context(f"{kind}:{name}")
        assert context["widgets"] and context["instruction"]
    for selection in ("catalog:store-coverage", "design:pawspa-viz-design"):
        try:
            gallery_templates.load_gallery_reference(selection)
        except ValueError:
            pass
        else:
            raise AssertionError(f"Retired reference still bundled: {selection}")

    skills = workspace / "skills"
    ensure_builtin_skills(str(skills))
    expected = {
        "business-report",
        "csv-data-analysis",
        "skill-creator",
        "agent-browser",
        "financial-report-analyzer",
        "walmart-sales-analyzer",
        "dashboard-builder",
    }
    assert {p.name for p in skills.iterdir() if p.name != "user"} == expected
    registry = SkillRegistry()
    registry.load_from_directory(str(skills))
    registered = {skill.name for skill in registry.list_skills()}
    assert registered - expected == {
        "dashboard-design",
        "dashboard-collaboration",
        "dashboard-chart-configuration",
        "dashboard-filter-configuration",
        "antv-g2-chart",
        "brutal-viz-design",
        "serenityspa-viz-design",
    }
    agentic_data_api.DEFAULT_SKILLS_DIR = str(skills)
    result = await agentic_data_api.list_skills(user_token=None)
    assert result.success, result.err_msg
    assert {skill["name"] for skill in result.data} == expected
    # Empty legacy directories left by a checkout must not change visibility.
    for name in registered - expected:
        (skills / name).mkdir()
    repeated = await agentic_data_api.list_skills(user_token=None)
    assert repeated.success
    assert repeated.data == result.data
    print(
        json.dumps(
            {
                "imported_app": dbgpt_app.__file__,
                "visible_skills": sorted(expected),
                "loadable_internal_skills": sorted(registered - expected),
                "gallery_references_loaded": len(references) - 1,
                "empty_legacy_directories_ignored": True,
                "checkout_skills_used": False,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
