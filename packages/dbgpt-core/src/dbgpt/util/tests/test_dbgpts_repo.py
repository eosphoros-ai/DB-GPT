from pathlib import Path

import pytest

from dbgpt.util.dbgpts import repo as repo_module


@pytest.fixture
def package_path(tmp_path):
    """A source package directory, as copied from a dbgpts repo."""
    src = tmp_path / "src" / "hello_world"
    src.mkdir(parents=True)
    (src / "pyproject.toml").write_text("[project]\nname = 'hello-world'\n")
    return src


@pytest.fixture
def install_root(tmp_path, monkeypatch):
    """Point the installer at a temporary DBGPTS_HOME."""
    root = tmp_path / "packages"
    root.mkdir()
    monkeypatch.setattr(repo_module, "INSTALL_DIR", root)
    return root


def test_inner_copy_and_install_raises_when_build_fails(
    package_path, install_root, monkeypatch
):
    """A failed build must abort the install, not be reported as success.

    _build_package returns (ok, error); assigning the whole tuple made the
    guard test a non-empty tuple, which is always truthy.
    """
    monkeypatch.setattr(
        repo_module, "_build_package", lambda *a, **kw: (False, "build blew up")
    )

    with pytest.raises(ValueError, match="build blew up"):
        repo_module.inner_copy_and_install(
            "eosphoros/dbgpts", "hello_world", package_path
        )

    assert not (install_root / "hello_world" / "install_metadata.toml").exists()


def test_inner_copy_and_install_raises_when_wheel_install_fails(
    package_path, install_root, monkeypatch
):
    """Same for a failed wheel install."""

    def fake_build(install_path: Path, *a, **kw):
        dist = install_path / "dist"
        dist.mkdir(parents=True, exist_ok=True)
        (dist / "hello_world-0.1.0-py3-none-any.whl").write_bytes(b"")
        return True, ""

    monkeypatch.setattr(repo_module, "_build_package", fake_build)
    monkeypatch.setattr(
        repo_module, "_install_wheel", lambda *a, **kw: (False, "not a zip file")
    )

    with pytest.raises(ValueError, match="not a zip file"):
        repo_module.inner_copy_and_install(
            "eosphoros/dbgpts", "hello_world", package_path
        )

    assert not (install_root / "hello_world" / "install_metadata.toml").exists()
