import textwrap

import pytest

from dbgpt_serve.plugins.loader import load_suite_dir, scan_suites

MANIFEST = textwrap.dedent(
    """
    kind: scenario-suite
    name: demo-query
    display: 智能取数
    icon: 🔍
    version: 1.0.0
    scenario_id: query
    execution: react
    routing:
      keywords: [查, 统计]
    recommended_questions:
      - {text: 查询上月销售额, hint: 按 region 汇总}
    tools:
      allow: [semantic_search, nl2sql]
      deny: [ddl]
    approval_overrides:
      - match: {tool: sql_execute, est_scan_gb: ">100"}
        action: confirm
        reason: 高代价扫描
    skills:
      - name: semantic-linking
        path: skills/semantic-linking/SKILL.md
    """
)


def _write_suite(root, name="demo-query", manifest=MANIFEST, with_skill=True):
    pkg = root / name
    pkg.mkdir(parents=True, exist_ok=True)
    (pkg / "suite.yaml").write_text(manifest, encoding="utf-8")
    if with_skill:
        skill = pkg / "skills" / "semantic-linking"
        skill.mkdir(parents=True, exist_ok=True)
        (skill / "SKILL.md").write_text(
            "---\nname: semantic-linking\ndescription: demo\n---\n# demo\n",
            encoding="utf-8",
        )
    return pkg


def test_load_suite_dir_parses_manifest_and_skills(tmp_path):
    pkg_dir = _write_suite(tmp_path)
    pkg = load_suite_dir(pkg_dir)
    assert pkg is not None
    assert pkg.name == "demo-query"
    assert pkg.version == "1.0.0"
    assert pkg.skills == ["semantic-linking"]
    assert pkg.snapshot["scenario_id"] == "query"
    assert pkg.snapshot["execution"] == "react"
    assert pkg.snapshot["tools"]["deny"] == ["ddl"]
    assert pkg.snapshot["approval_overrides"][0]["action"] == "confirm"
    assert pkg.snapshot["recommended_questions"][0]["text"] == "查询上月销售额"
    # sop body must never leak into the snapshot (read from package at bind time)
    assert "sop" not in pkg.snapshot
    assert pkg.warnings == []
    assert len(pkg.digest) == 64


def test_digest_is_stable_and_content_sensitive(tmp_path):
    pkg_dir = _write_suite(tmp_path)
    first = load_suite_dir(pkg_dir)
    second = load_suite_dir(pkg_dir)
    assert first.digest == second.digest
    (pkg_dir / "suite.yaml").write_text(
        MANIFEST.replace("1.0.0", "1.0.1"), encoding="utf-8"
    )
    third = load_suite_dir(pkg_dir)
    assert third.digest != first.digest
    assert third.version == "1.0.1"


def test_missing_required_field_is_skipped(tmp_path):
    bad = MANIFEST.replace("version: 1.0.0\n", "")
    pkg_dir = _write_suite(tmp_path, manifest=bad)
    assert load_suite_dir(pkg_dir) is None


def test_unsupported_kind_is_skipped(tmp_path):
    bad = MANIFEST.replace("kind: scenario-suite", "kind: not-a-suite")
    pkg_dir = _write_suite(tmp_path, manifest=bad)
    assert load_suite_dir(pkg_dir) is None


def test_bad_typed_field_is_skipped_failsoft(tmp_path):
    bad = MANIFEST.replace("routing:\n  keywords: [查, 统计]", "routing: nope")
    pkg_dir = _write_suite(tmp_path, manifest=bad)
    pkg = load_suite_dir(pkg_dir)
    assert pkg is not None
    assert "routing" not in pkg.snapshot
    assert any("routing" in w for w in pkg.warnings)


def test_missing_skill_file_warns_but_keeps_skill(tmp_path):
    pkg_dir = _write_suite(tmp_path, with_skill=False)
    pkg = load_suite_dir(pkg_dir)
    assert pkg is not None
    assert pkg.skills == ["semantic-linking"]
    assert any("SKILL.md missing" in w for w in pkg.warnings)


def test_scan_suites_skips_dirs_without_manifest(tmp_path):
    _write_suite(tmp_path)
    (tmp_path / "not-a-suite").mkdir()
    packages, warnings = scan_suites(tmp_path)
    assert [p.name for p in packages] == ["demo-query"]
    assert warnings == []


def test_scan_suites_missing_root_is_failsoft():
    packages, warnings = scan_suites(None)
    assert packages == []
    assert len(warnings) == 1


def test_scan_real_official_suites():
    """The three official packages in the repo must parse cleanly."""
    from pathlib import Path

    root = Path(__file__).resolve().parents[6] / "assets" / "suites"
    if not root.is_dir():  # pragma: no cover - depends on checkout layout
        pytest.skip("assets/suites not found")
    packages, warnings = scan_suites(root)
    names = {p.name for p in packages}
    assert {"db-query", "db-analysis", "db-ops"} <= names
    for pkg in packages:
        assert pkg.snapshot["skills"], pkg.name
        assert pkg.warnings == [], (pkg.name, pkg.warnings)
