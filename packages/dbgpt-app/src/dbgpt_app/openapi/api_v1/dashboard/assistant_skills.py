"""Project-owned collaboration guidance shared by planning and execution."""

from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def dashboard_collaboration_skill() -> str:
    path = Path(__file__).parent / "skills/dashboard-collaboration/SKILL.md"
    return path.read_text(encoding="utf-8").split("---", 2)[-1].strip()


@lru_cache(maxsize=3)
def dashboard_configuration_skill(target_kind: str) -> str:
    names = (
        ["dashboard-filter-configuration"]
        if target_kind == "filter"
        else ["dashboard-chart-configuration", "dashboard-filter-configuration"]
    )
    return "\n\n".join(
        (Path(__file__).parent / "skills" / name / "SKILL.md")
        .read_text(encoding="utf-8")
        .split("---", 2)[-1]
        .strip()
        for name in names
    )
