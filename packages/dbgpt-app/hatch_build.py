"""Hatch build hook for dbgpt-app.

Dynamically resolves force-include paths for wheel builds based on the build
mode. This is necessary because source paths differ between editable installs
(where files live at the repository root) and standard builds from sdist
(where files have been copied into the sdist archive).

Problem solved:
  - editable (uv sync): root = packages/dbgpt-app/, files at ../../skills/
  - standard (from sdist): root = /tmp/extracted-sdist/, files at skills/
  Static pyproject.toml force-include cannot handle both cases.
"""

from __future__ import annotations

import os
from pathlib import Path

from hatchling.builders.hooks.plugin.interface import BuildHookInterface

# ---------------------------------------------------------------------------
# Source paths (relative to REPO ROOT) -> wheel target paths
# Used in editable mode where we can reach repo root via ../../
# ---------------------------------------------------------------------------

_SKILL_SRC = "skills"
_SKILL_DST = "dbgpt_app/_builtin_skills"

_SKILLS_MAP = {
    f"{_SKILL_SRC}/{name}": f"{_SKILL_DST}/{name}"
    for name in [
        "csv-data-analysis",
        "skill-creator",
        "financial-report-analyzer",
        "walmart-sales-analyzer",
        "agent-browser",
        "dashboard-builder",
        "antv-g2-chart",
        "brutal-viz-design",
        "datapulse-viz-design",
        "learnhub-viz-design",
        "nexusai-viz-design",
        "pawspa-viz-design",
        "serenityspa-viz-design",
    ]
}

_EXAMPLE_DST = "dbgpt_app/_builtin_examples"

# fmt: off
_EXAMPLES_MAP = {
    "docker/examples/excel/Walmart_Sales.csv": (
        f"{_EXAMPLE_DST}/excel/Walmart_Sales.csv"
    ),
    (
        "docker/examples/fin_report/pdf/"
        "2020-01-23__浙江海翔药业股份有限公司__002099__"
        "海翔药业__2019年__年度报告.pdf"
    ): (
        f"{_EXAMPLE_DST}/fin_report/pdf/"
        "2020-01-23__浙江海翔药业股份有限公司__002099__"
        "海翔药业__2019年__年度报告.pdf"
    ),
}
# fmt: on

_TPL = "dbgpt_app/pilot_template"

# fmt: off
_PILOT_TPL_MAP = {
    "pilot/meta_data/alembic.ini": (
        f"{_TPL}/meta_data/alembic.ini"
    ),
    "pilot/meta_data/alembic/README": (
        f"{_TPL}/meta_data/alembic/README"
    ),
    "pilot/meta_data/alembic/env.py": (
        f"{_TPL}/meta_data/alembic/env.py"
    ),
    "pilot/meta_data/alembic/script.py.mako": (
        f"{_TPL}/meta_data/alembic/script.py.mako"
    ),
    "pilot/meta_data/alembic/versions": (
        f"{_TPL}/meta_data/alembic/versions"
    ),
    (
        "pilot/benchmark_meta_data/"
        "2025_07_27_public_500_standard_benchmark"
        "_question_list.xlsx"
    ): (
        f"{_TPL}/benchmark_meta_data/"
        "2025_07_27_public_500_standard_benchmark"
        "_question_list.xlsx"
    ),
    "pilot/examples/Walmart_Sales.db": (
        f"{_TPL}/examples/Walmart_Sales.db"
    ),
}
# fmt: on

# sdist force-include remaps these paths:
#   ../../skills/X           -> skills/X
#   ../../docker/examples/X  -> examples/X
#   ../../pilot/X            -> pilot_tpl/X
_SDIST_REMAP = {
    "skills/": "skills/",  # no change
    "docker/examples/": "examples/",  # strip "docker/"
    "pilot/": "pilot_tpl/",  # pilot -> pilot_tpl
}


class CustomBuildHook(BuildHookInterface):
    """Dynamically set force-include paths for editable and standard builds."""

    def initialize(self, version, build_data):
        """Called by hatchling before building.

        Args:
            version: "editable" for ``uv sync`` / ``pip install -e .``
                     "standard" for ``uv build`` / ``pip wheel``
            build_data: mutable dict; set ``force_include`` to inject
                        path mappings
        """
        pkg_root = Path(self.root)  # packages/dbgpt-app/
        all_mappings = {
            **_SKILLS_MAP,
            **_EXAMPLES_MAP,
            **_PILOT_TPL_MAP,
        }
        force_include: dict[str, str] = {}

        in_checkout = (
            pkg_root.parent.name == "packages"
            and (pkg_root.parent.parent / "pilot").is_dir()
            and (pkg_root.parent.parent / "skills").is_dir()
        )
        if version == "editable" or in_checkout:
            # Direct wheel builds from a checkout need the same bundled assets
            # as editable builds. Only extracted sdists use remapped paths.
            repo_root = pkg_root.parent.parent
            for repo_rel, wheel_target in all_mappings.items():
                source = str(repo_root / repo_rel)
                if os.path.exists(source):
                    force_include[source] = wheel_target
        else:
            # Standard build from sdist: files sit at sdist-relative
            # paths set by pyproject.toml [tool.hatch.build.targets.sdist]
            for repo_rel, wheel_target in all_mappings.items():
                sdist_path = repo_rel
                for prefix, replacement in _SDIST_REMAP.items():
                    if repo_rel.startswith(prefix):
                        sdist_path = replacement + repo_rel[len(prefix) :]
                        break
                source = str(pkg_root / sdist_path)
                if os.path.exists(source):
                    force_include[source] = wheel_target

        build_data["force_include"] = force_include
