"""Opt-in distribution regression: sdist -> wheel -> installed default report.

Run with DBGPT_TEST_APP_PACKAGE=1 and the project's development dependencies.
DBGPT_APP_DIST_TEST_DIR optionally retains build logs, archives and runtime HTML.
"""

import hashlib
import json
import os
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    os.getenv("DBGPT_TEST_APP_PACKAGE") != "1",
    reason="Opt-in: builds and installs distributions into a temporary target",
)
SKILLS = (
    "business-report",
    "csv-data-analysis",
    "skill-creator",
    "financial-report-analyzer",
    "walmart-sales-analyzer",
    "agent-browser",
    "dashboard-builder",
)
INTERNAL_DASHBOARD_SKILLS = {
    "dashboard-design",
    "dashboard-collaboration",
    "dashboard-chart-configuration",
    "dashboard-filter-configuration",
    "antv-g2-chart",
    "brutal-viz-design",
    "serenityspa-viz-design",
}
OLIST_SOURCE = "examples/olist/olist-analytics-metric-governance.md"
OLIST_SDIST = "examples/knowledge/olist-analytics-metric-governance.md"
OLIST_WHEEL = (
    "dbgpt_app/_builtin_examples/knowledge/olist-analytics-metric-governance.md"
)


@pytest.fixture(scope="module")
def distributions(tmp_path_factory):
    package = Path(__file__).resolve().parents[1]
    repository = package.parent.parent
    root = (
        Path(os.environ["DBGPT_APP_DIST_TEST_DIR"])
        if os.getenv("DBGPT_APP_DIST_TEST_DIR")
        else tmp_path_factory.mktemp("report-distribution")
    )
    root.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}

    def run(name, command, cwd):
        print(f"Distribution check: {name}", flush=True)
        result = subprocess.run(
            command,
            cwd=cwd,
            env=env,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=600,
        )
        (root / f"{name}.log").write_text(
            f"CWD: {cwd}\nCommand: {subprocess.list2cmdline(command)}\n\n"
            + result.stdout
            + f"\nExit code: {result.returncode}\n",
            encoding="utf-8",
        )
        assert result.returncode == 0, result.stdout

    sdist_dir = root / "sdist"
    run(
        "01_build_sdist",
        [
            sys.executable,
            "-m",
            "build",
            "--sdist",
            "--outdir",
            str(sdist_dir),
            str(package),
        ],
        repository,
    )
    sdist = next(sdist_dir.glob("*.tar.gz"))
    extracted = root / "extracted"
    extracted.mkdir(exist_ok=True)
    with tarfile.open(sdist) as archive:
        archive.extractall(extracted, filter="data")
    source = next(p for p in extracted.iterdir() if p.is_dir())
    wheel_dir = root / "wheel_from_sdist"
    # Build with cwd outside the repository, using only the extracted sdist.
    run(
        "02_build_wheel_from_sdist",
        [
            sys.executable,
            "-m",
            "build",
            "--wheel",
            "--outdir",
            str(wheel_dir),
            str(source),
        ],
        root,
    )
    wheel = next(wheel_dir.glob("*.whl"))
    direct_dir = root / "wheel_direct"
    run(
        "03_build_wheel_direct",
        [
            sys.executable,
            "-m",
            "build",
            "--wheel",
            "--outdir",
            str(direct_dir),
            str(package),
        ],
        repository,
    )
    direct_wheel = next(direct_dir.glob("*.whl"))
    installed = root / "installed"
    run(
        "04_install_wheel",
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--no-deps",
            "--target",
            str(installed),
            str(wheel),
        ],
        root,
    )
    manifest = {}
    for name, path in [
        ("sdist", sdist),
        ("wheel_from_sdist", wheel),
        ("wheel_direct", direct_wheel),
    ]:
        manifest[name] = {
            "file": str(path),
            "bytes": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
    (root / "artifacts.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    return dict(
        root=root,
        repository=repository,
        sdist=sdist,
        wheel=wheel,
        direct_wheel=direct_wheel,
        installed=installed,
        run=run,
    )


def test_sdist_contains_all_builtin_skills_and_default_template(distributions):
    with tarfile.open(distributions["sdist"]) as archive:
        names = archive.getnames()
        prefix = names[0].split("/")[0]
        for name in SKILLS:
            assert f"{prefix}/skills/{name}/SKILL.md" in names
        path = "skills/business-report/templates/business_report.html"
        expected = (distributions["repository"] / path).read_bytes()
        assert archive.extractfile(f"{prefix}/{path}").read() == expected
        assert (
            archive.extractfile(f"{prefix}/{OLIST_SDIST}").read()
            == (distributions["repository"] / OLIST_SOURCE).read_bytes()
        )


@pytest.mark.parametrize("artifact", ["wheel", "direct_wheel"])
def test_wheels_contain_all_builtin_skills_and_default_template(
    distributions, artifact
):
    with zipfile.ZipFile(distributions[artifact]) as archive:
        for name in SKILLS:
            assert f"dbgpt_app/_builtin_skills/{name}/SKILL.md" in archive.namelist()
        source = (
            distributions["repository"]
            / "skills/business-report/templates/business_report.html"
        )
        assert (
            archive.read(
                "dbgpt_app/_builtin_skills/business-report/templates/business_report.html"
            )
            == source.read_bytes()
        )
        assert (
            archive.read(OLIST_WHEEL)
            == (distributions["repository"] / OLIST_SOURCE).read_bytes()
        )


def test_installed_wheel_builds_agent_and_generates_default_report(distributions):
    root = distributions["root"]
    worker = Path(__file__).with_name("packaged_report_worker.py")
    distributions["run"](
        "05_installed_report_generation",
        [
            sys.executable,
            "-I",
            str(worker),
            str(distributions["installed"]),
            str(root / "runtime"),
            str(distributions["repository"]),
        ],
        root,
    )
    assert (root / "runtime/generated-report.html").is_file()


@pytest.mark.parametrize("artifact", ["sdist", "wheel", "direct_wheel"])
def test_dashboard_resources_are_bundled_under_one_skill(distributions, artifact):
    source = distributions["repository"] / "skills/dashboard-builder"
    reference_names = {
        "index.md",
        "design-brutal-viz-design.md",
        "design-serenityspa-viz-design.md",
        "catalog-voice-observatory.md",
        "catalog-store-marketing.md",
        "catalog-national-command.md",
        "catalog-brand-revenue.md",
        "catalog-northwind-revenue.md",
        "catalog-retail-overview.md",
    }
    assert {
        p.name for p in (source / "internal/dashboard-design/references").iterdir()
    } == reference_names
    assert {p.parent.name for p in source.glob("internal/*/SKILL.md")} == (
        INTERNAL_DASHBOARD_SKILLS
    )
    resources = {
        p.relative_to(source).as_posix(): p.read_bytes()
        for p in source.rglob("*")
        if p.is_file()
    }
    if artifact == "sdist":
        with tarfile.open(distributions[artifact]) as archive:
            prefix = archive.getnames()[0].split("/")[0] + "/skills/"
            bundled = {
                p.name.removeprefix(prefix): archive.extractfile(p).read()
                for p in archive.getmembers()
                if p.isfile() and p.name.startswith(prefix)
            }
    else:
        with zipfile.ZipFile(distributions[artifact]) as archive:
            prefix = "dbgpt_app/_builtin_skills/"
            bundled = {
                name.removeprefix(prefix): archive.read(name)
                for name in archive.namelist()
                if name.startswith(prefix) and not name.endswith("/")
            }
    assert {name.split("/")[0] for name in bundled if "/" in name} == set(SKILLS)
    assert {
        name.removeprefix("dashboard-builder/"): content
        for name, content in bundled.items()
        if name.startswith("dashboard-builder/")
    } == resources


def test_installed_dashboard_skill_resources_and_visibility(distributions):
    root = distributions["root"]
    distributions["run"](
        "06_installed_dashboard_skills",
        [
            sys.executable,
            "-I",
            str(Path(__file__).with_name("packaged_dashboard_worker.py")),
            str(distributions["installed"]),
            str(root / "dashboard-runtime"),
            str(distributions["repository"]),
        ],
        root,
    )
