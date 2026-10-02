"""Tests for the benchmark result output path confinement.

``execute_benchmark_task`` takes user-supplied ``output_file_path`` and
``evaluate_code`` and turns them into the xlsx result path. Both used to
flow into ``mkdir(parents=True)`` + ``workbook.save`` unchecked, giving
an arbitrary directory writer. The full path must stay under the
benchmark result root.
"""

from pathlib import Path

import pytest

from ..service.benchmark.benchmark_service import generate_confined_output_path


@pytest.fixture
def root(tmp_path):
    return str(tmp_path / "result")


def test_plain_paths_stay_under_root(root):
    result = generate_confined_output_path(root, "eval_1", root=root)

    path = Path(result)
    assert path.parent.parent == Path(root)
    assert path.parent.name == "eval_1"
    assert path.name.endswith("_multi_round_benchmark_result.xlsx")


def test_subdirectory_of_root_is_allowed(root):
    base = str(Path(root) / "custom")
    result = generate_confined_output_path(base, "eval_1", root=root)
    assert Path(result).is_relative_to(Path(root))


def test_evaluate_code_cannot_escape_root(root):
    # slashes/dots must collapse to a single component under the root
    result = generate_confined_output_path(root, "a/../../evil", root=root)
    assert Path(result).is_relative_to(Path(root))

    with pytest.raises(ValueError):
        generate_confined_output_path(root, "..", root=root)
    with pytest.raises(ValueError):
        generate_confined_output_path(root, ".", root=root)
    with pytest.raises(ValueError):
        generate_confined_output_path(root, "/", root=root)


def test_output_base_outside_root_is_rejected(root, tmp_path):
    with pytest.raises(ValueError):
        generate_confined_output_path(str(tmp_path / "pwn"), "eval_1", root=root)

    with pytest.raises(ValueError):
        generate_confined_output_path("/tmp", "eval_1", root=root)

    # traversal payload that resolves outside the root
    with pytest.raises(ValueError):
        generate_confined_output_path(
            str(Path(root) / ".." / "escape"), "eval_1", root=root
        )


def test_absolute_evaluate_code_component_is_confined(root):
    # an absolute-path evaluate_code would otherwise reset the joined
    # path; basename() must neutralize it into a single component
    result = generate_confined_output_path(root, "/etc", root=root)
    assert Path(result).is_relative_to(Path(root))
    assert Path(result).parent.name == "etc"


def test_empty_arguments_are_rejected(root):
    with pytest.raises(ValueError):
        generate_confined_output_path("", "eval_1", root=root)
    with pytest.raises(ValueError):
        generate_confined_output_path(root, "", root=root)
    with pytest.raises(ValueError):
        generate_confined_output_path("   ", "eval_1", root=root)
    with pytest.raises(ValueError):
        generate_confined_output_path(root, "   ", root=root)
