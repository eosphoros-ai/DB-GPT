"""Tests for chat file input normalization."""

import pytest

from dbgpt_serve.session_file.domain import (
    FileInputError,
    FileInputSpec,
    parse_file_input,
)


def test_parse_file_input_returns_empty_spec_without_file_fields():
    ext_info = {"skill_name": "sql-analyzer", "connector_ids": ["connector-a"]}

    result = parse_file_input(ext_info)

    assert result == FileInputSpec.empty()
    assert ext_info == {
        "skill_name": "sql-analyzer",
        "connector_ids": ["connector-a"],
    }


def test_parse_file_input_preserves_order_and_deduplicates_ids():
    result = parse_file_input({"file_ids": ["sf_b", "sf_a", "sf_b"]})

    assert result.file_ids == ("sf_b", "sf_a")
    assert result.file_path is None


@pytest.mark.parametrize(
    "file_ids",
    [[], "sf_a", {"sf_a"}, ["sf_a", 1], ["sf_a", ""], ["sf_a", "   "]],
)
def test_parse_file_input_rejects_invalid_file_ids(file_ids):
    with pytest.raises(FileInputError, match="INVALID_FILE_IDS"):
        parse_file_input({"file_ids": file_ids})


def test_parse_file_input_rejects_too_many_unique_ids():
    with pytest.raises(FileInputError, match="TOO_MANY_FILES"):
        parse_file_input({"file_ids": ["sf_a", "sf_b", "sf_c"]}, max_files=2)


@pytest.mark.parametrize(
    "file_path", [None, "", "   ", 1, ["/legacy/a.csv"], "/legacy/a.csv"]
)
def test_parse_file_input_rejects_new_and_legacy_fields_together(file_path):
    with pytest.raises(FileInputError, match="CONFLICTING_FILE_INPUTS"):
        parse_file_input({"file_ids": ["sf_a"], "file_path": file_path})


def test_parse_file_input_retains_legacy_path():
    result = parse_file_input({"file_path": "/legacy/a.csv"})

    assert result.file_ids == ()
    assert result.file_path == "/legacy/a.csv"


@pytest.mark.parametrize("file_path", [None, "", "   ", 1, ["/legacy/a.csv"]])
def test_parse_file_input_rejects_invalid_legacy_path(file_path):
    with pytest.raises(FileInputError, match="INVALID_FILE_PATH"):
        parse_file_input({"file_path": file_path})


def test_file_input_spec_is_immutable():
    spec = parse_file_input({"file_ids": ["sf_a"]})

    with pytest.raises((AttributeError, TypeError)):
        spec.file_ids = ("sf_b",)


def test_file_input_error_supports_traceback_assignment_with_read_only_code():
    error = FileInputError("INVALID_FILE_IDS")
    try:
        raise RuntimeError("source")
    except RuntimeError as source:
        traceback = source.__traceback__

    assert error.with_traceback(traceback) is error
    error.__traceback__ = None
    assert error.code == "INVALID_FILE_IDS"
    assert str(error) == "INVALID_FILE_IDS"
    with pytest.raises(AttributeError):
        error.code = "CHANGED"


def test_file_input_spec_defensively_converts_file_ids_to_tuple():
    file_ids = ["sf_a", "sf_b"]

    spec = FileInputSpec(file_ids=file_ids)
    file_ids.append("sf_c")

    assert spec.file_ids == ("sf_a", "sf_b")
    assert hash(spec) == hash(FileInputSpec(file_ids=("sf_a", "sf_b")))


def test_file_input_spec_rejects_string_as_file_ids_iterable():
    with pytest.raises(FileInputError, match="INVALID_FILE_IDS"):
        FileInputSpec(file_ids="sf_a")


@pytest.mark.parametrize(
    "file_ids", [(), [], ("sf_a", ""), ("sf_a", "   "), ("sf_a", 1)]
)
def test_file_input_spec_rejects_invalid_file_ids(file_ids):
    with pytest.raises(FileInputError, match="INVALID_FILE_IDS"):
        FileInputSpec(file_ids=file_ids)


@pytest.mark.parametrize("file_path", [None, "", "   ", 1, ["/legacy/a.csv"]])
def test_file_input_spec_rejects_invalid_legacy_path(file_path):
    with pytest.raises(FileInputError, match="INVALID_FILE_PATH"):
        FileInputSpec(file_path=file_path)


@pytest.mark.parametrize("file_path", [None, "", "   ", 1, "/legacy/a.csv"])
def test_file_input_spec_rejects_conflict_before_field_validation(file_path):
    with pytest.raises(FileInputError, match="CONFLICTING_FILE_INPUTS"):
        FileInputSpec(file_ids=("sf_a",), file_path=file_path)


def test_file_input_spec_allows_canonical_empty_new_and_legacy_inputs():
    assert FileInputSpec.empty() == FileInputSpec.empty()
    assert FileInputSpec(file_ids=("sf_a",)).file_ids == ("sf_a",)
    assert FileInputSpec(file_path=" /legacy/a.csv ").file_path == " /legacy/a.csv "
