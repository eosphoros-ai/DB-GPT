from pathlib import Path

import pytest

from dbgpt.util.code_utils import execute_code


def test_execute_code_rejects_filename_outside_work_dir(tmp_path: Path):
    work_dir = tmp_path / "workspace"
    outside_file = tmp_path / "outside.py"

    with pytest.raises(ValueError, match="work_dir"):
        execute_code(
            "print('escaped')",
            filename="../outside.py",
            work_dir=str(work_dir),
            use_docker=False,
        )

    assert not outside_file.exists()


def test_execute_code_rejects_absolute_filename(tmp_path: Path):
    work_dir = tmp_path / "workspace"
    outside_file = tmp_path / "outside.py"

    with pytest.raises(ValueError, match="relative path"):
        execute_code(
            "print('escaped')",
            filename=str(outside_file),
            work_dir=str(work_dir),
            use_docker=False,
        )

    assert not outside_file.exists()


def test_execute_code_allows_nested_filename_inside_work_dir(tmp_path: Path):
    work_dir = tmp_path / "workspace"

    exitcode, logs, image = execute_code(
        "print('inside')",
        filename="nested/script.py",
        work_dir=str(work_dir),
        use_docker=False,
    )

    assert exitcode == 0
    assert logs == "inside\n"
    assert image is None
    assert (work_dir / "nested" / "script.py").exists()


def test_execute_code_rejects_symlink_escape_from_work_dir(tmp_path: Path):
    work_dir = tmp_path / "workspace"
    outside_dir = tmp_path / "outside"
    work_dir.mkdir()
    outside_dir.mkdir()

    try:
        (work_dir / "linked").symlink_to(outside_dir, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"symlinks are not available in this environment: {exc}")

    with pytest.raises(ValueError, match="work_dir"):
        execute_code(
            "print('escaped')",
            filename="linked/escaped.py",
            work_dir=str(work_dir),
            use_docker=False,
        )

    assert not (outside_dir / "escaped.py").exists()
