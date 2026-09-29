"""Tests for workspace_provisioning module."""

import os
from types import SimpleNamespace

from dbgpt_app.initialization import package_resources
from dbgpt_app.initialization.skills_provisioning import ensure_builtin_skills
from dbgpt_app.initialization.workspace_provisioning import _ensure_pilot_workspace


def test_ensure_pilot_workspace_copies_alembic_ini(tmp_path):
    """Test that alembic.ini is copied to dest_root/meta_data/alembic.ini"""
    _ensure_pilot_workspace(str(tmp_path))
    assert os.path.exists(tmp_path / "meta_data" / "alembic.ini")


def test_ensure_pilot_workspace_copies_alembic_env_py(tmp_path):
    """Test that alembic/env.py is copied"""
    _ensure_pilot_workspace(str(tmp_path))
    assert os.path.exists(tmp_path / "meta_data" / "alembic" / "env.py")


def test_ensure_pilot_workspace_copies_alembic_script_mako(tmp_path):
    """Test that alembic/script.py.mako is copied"""
    _ensure_pilot_workspace(str(tmp_path))
    assert os.path.exists(tmp_path / "meta_data" / "alembic" / "script.py.mako")


def test_ensure_pilot_workspace_copies_benchmark_xlsx(tmp_path):
    """Test that benchmark xlsx is copied"""
    _ensure_pilot_workspace(str(tmp_path))
    xlsx_files = list((tmp_path / "benchmark_meta_data").glob("*.xlsx"))
    assert len(xlsx_files) == 1


def test_ensure_pilot_workspace_idempotent_no_overwrite(tmp_path):
    """Test that calling twice does not overwrite existing files"""
    _ensure_pilot_workspace(str(tmp_path))
    ini_path = tmp_path / "meta_data" / "alembic.ini"
    # write custom content to simulate user modification
    ini_path.write_text("custom content")
    _ensure_pilot_workspace(str(tmp_path))  # call again
    assert ini_path.read_text() == "custom content"  # must not be overwritten


def test_ensure_pilot_workspace_creates_missing_directories(tmp_path):
    """Test that missing destination directories are created automatically"""
    dest = tmp_path / "deep" / "nested" / "pilot"
    _ensure_pilot_workspace(str(dest))
    assert os.path.exists(dest / "meta_data" / "alembic.ini")


def test_editable_install_provisions_shipped_migrations_and_skills(
    tmp_path, monkeypatch
):
    source = tmp_path / "source" / "dbgpt_app" / "initialization"
    site = tmp_path / "site-packages"
    monkeypatch.setattr(
        package_resources, "__file__", str(source / "package_resources.py")
    )
    monkeypatch.setattr(
        package_resources,
        "distribution",
        lambda name: SimpleNamespace(locate_file=lambda relative: site / relative),
    )
    migration = site / "dbgpt_app/pilot_template/meta_data/alembic/versions/kept.py"
    migration.parent.mkdir(parents=True)
    migration.write_text('revision = "kept"')
    skill = site / "dbgpt_app/_builtin_skills/dashboard-builder/SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("Dashboard workflow")

    dest = tmp_path / "runtime"
    _ensure_pilot_workspace(str(dest / "pilot"))
    ensure_builtin_skills(str(dest / "skills"))
    copied = dest / "pilot/meta_data/alembic/versions/kept.py"
    assert copied.read_text() == migration.read_text()
    assert (dest / "skills/dashboard-builder/SKILL.md").read_text() == skill.read_text()
    copied.write_text("user revision")
    _ensure_pilot_workspace(str(dest / "pilot"))
    assert copied.read_text() == "user revision"


def test_package_assets_take_precedence_over_editable_distribution(
    tmp_path, monkeypatch
):
    package = tmp_path / "dbgpt_app"
    template = package / "pilot_template"
    template.mkdir(parents=True)
    monkeypatch.setattr(
        package_resources,
        "__file__",
        str(package / "initialization/package_resources.py"),
    )

    def unexpected_distribution(name):
        raise AssertionError("A normal package already contains its resources")

    monkeypatch.setattr(package_resources, "distribution", unexpected_distribution)
    assert package_resources.bundled_resource_dir("pilot_template") == template
