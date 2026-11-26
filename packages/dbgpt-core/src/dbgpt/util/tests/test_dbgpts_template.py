from pathlib import Path

import pytest

from dbgpt.util.dbgpts import template as template_module

COMBOS = [
    ("flow", "json", "definition/flow_definition.json"),
    ("flow", "python", "__init__.py"),
    ("operator", "python", "__init__.py"),
    ("agent", "python", "__init__.py"),
    ("resource", "python", "__init__.py"),
]


def _fake_project(layout):
    """Stand in for `uv init` (src layout) or the manual fallback (flat)."""

    def create(working_directory, name, description=None):
        project_dir = Path(working_directory) / name
        mod_name = name.replace("-", "_")
        package_dir = project_dir / mod_name
        if layout == "src":
            package_dir = project_dir / "src" / mod_name
        package_dir.mkdir(parents=True)
        (package_dir / "__init__.py").write_text("def main() -> None: ...\n")
        (project_dir / "pyproject.toml").write_text("[project]\nname = 'my-demo'\n")
        return True

    return create


@pytest.mark.parametrize("layout", ["src", "flat"])
@pytest.mark.parametrize("dbgpts_type,definition_type,written", COMBOS)
def test_create_template_writes_into_the_shipped_package(
    tmp_path, monkeypatch, layout, dbgpts_type, definition_type, written
):
    monkeypatch.setattr(
        template_module, "_create_project_structure", _fake_project(layout)
    )
    package_root = tmp_path / template_module.TYPE_TO_PACKAGE[dbgpts_type]
    package_root.mkdir()

    template_module.create_template(
        "my-demo", "My Demo", "demo", dbgpts_type, definition_type, str(tmp_path)
    )

    project_dir = package_root / "my-demo"
    shipped = project_dir / ("src" if layout == "src" else "") / "my_demo"
    assert (shipped / written).is_file()
    if written == "__init__.py":
        assert "def main()" not in (shipped / written).read_text()
    if layout == "src":
        assert not (project_dir / "my_demo").exists()


@pytest.mark.parametrize("layout", ["src", "flat"])
def test_manifest_includes_the_definition_where_it_is_written(
    tmp_path, monkeypatch, layout
):
    monkeypatch.setattr(
        template_module, "_create_project_structure", _fake_project(layout)
    )
    package_root = tmp_path / template_module.TYPE_TO_PACKAGE["flow"]
    package_root.mkdir()

    template_module.create_template(
        "my-demo", "My Demo", "demo", "flow", "json", str(tmp_path)
    )

    project_dir = package_root / "my-demo"
    manifest = (project_dir / "MANIFEST.in").read_text().splitlines()
    patterns = [line.split(" ", 1)[1] for line in manifest if "definition" in line]
    assert patterns
    for pattern in patterns:
        assert list(project_dir.glob(pattern)), pattern


@pytest.mark.parametrize("name", ["My-Demo", "my.demo"])
def test_create_template_follows_the_module_name_uv_creates(
    tmp_path, monkeypatch, name
):
    def uv_init(working_directory, name, description=None):
        # `uv init` lowercases the name and turns `-`/`.` into `_`.
        package_dir = Path(working_directory) / name / "src" / "my_demo"
        package_dir.mkdir(parents=True)
        (package_dir / "__init__.py").write_text("def main() -> None: ...\n")
        return True

    monkeypatch.setattr(template_module, "_create_project_structure", uv_init)
    package_root = tmp_path / template_module.TYPE_TO_PACKAGE["operator"]
    package_root.mkdir()

    template_module.create_template(
        name, "My Demo", "demo", "operator", "python", str(tmp_path)
    )

    project_dir = package_root / name
    assert "Operator" in (project_dir / "src/my_demo/__init__.py").read_text()
    assert [p.name for p in project_dir.iterdir() if p.is_dir()] == ["src"]
    assert 'name = "my_demo"' in (project_dir / "dbgpts.toml").read_text()
