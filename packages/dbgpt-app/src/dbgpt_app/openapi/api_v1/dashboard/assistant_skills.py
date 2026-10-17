"""Project-owned collaboration guidance shared by planning and execution."""

from functools import lru_cache
from pathlib import Path

from dbgpt.configs.model_config import SKILLS_DIR
from dbgpt_app.initialization.package_resources import bundled_resource_dir


def _skill_text(name: str) -> str:
    packaged = bundled_resource_dir("_builtin_skills")
    root = (
        packaged
        if packaged is not None and (packaged / name / "SKILL.md").is_file()
        else Path(SKILLS_DIR)
    )
    return (
        (root / name / "SKILL.md")
        .read_text(encoding="utf-8")
        .split("---", 2)[-1]
        .strip()
    )


@lru_cache(maxsize=1)
def dashboard_collaboration_skill() -> str:
    return _skill_text("dashboard-collaboration")


@lru_cache(maxsize=3)
def dashboard_configuration_skill(target_kind: str) -> str:
    names = (
        ["dashboard-filter-configuration"]
        if target_kind == "filter"
        else ["dashboard-chart-configuration", "dashboard-filter-configuration"]
    )
    return "\n\n".join(_skill_text(name) for name in names)
