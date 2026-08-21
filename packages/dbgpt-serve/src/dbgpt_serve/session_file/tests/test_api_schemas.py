"""Contract tests for the session file API config and schemas."""

import json

import pytest

from dbgpt_serve.session_file.api.schemas import (
    SessionFileCapabilitiesResponse,
    SessionFileErrorCode,
    SessionFilePreviewResponse,
    SessionFileResponse,
)
from dbgpt_serve.session_file.config import ServeConfig
from dbgpt_serve.session_file.domain import (
    SessionFileManifest,
    SessionFilePrivateRecord,
    SessionFileStatus,
)

_PUBLIC_RESPONSE_KEYS = {
    "file_id",
    "name",
    "size",
    "media_type",
    "kind",
    "status",
    "ordinal",
    "error_code",
}

_PRIVATE_MARKERS = (
    "storage_uri",
    "storageUri",
    "sha256",
    "file_path",
    "filePath",
    "owner_id",
    "ownerId",
    "task_id",
    "session_id",
    "inspection_json",
    "source_file_id",
)


def _private_record(**overrides) -> SessionFilePrivateRecord:
    values = dict(
        file_id="sf_contract",
        owner_id="alice",
        session_id="conv-1",
        task_id=None,
        display_name="report.csv",
        storage_uri="file:///managed/sf_contract",
        media_type="text/csv",
        file_kind="table",
        size_bytes=42,
        sha256="a" * 64,
        ordinal=0,
        status=SessionFileStatus.READY,
        inspection_json='{"preview": {}, "truncated": false}',
        error_code=None,
        error_message="parser detail that must stay server-side",
        source_file_id="sf_source",
        created_at=None,
        updated_at=None,
    )
    values.update(overrides)
    return SessionFilePrivateRecord(**values)


def test_config_defaults_match_planned_limits():
    config = ServeConfig()

    assert config.max_files_per_upload == 20
    assert config.max_file_bytes == 100 * 1024 * 1024
    assert config.max_upload_bytes == 500 * 1024 * 1024
    assert config.max_owner_bytes == -1
    assert config.upload_request_timeout_seconds == 180
    assert config.upload_concurrency_advice == 3
    assert config.upload_chunk_bytes > 0
    assert config.upload_spool_bytes > 0
    assert config.download_chunk_bytes > 0
    assert config.max_file_name_bytes == 255


@pytest.mark.parametrize(
    "field_name",
    [
        "max_files_per_upload",
        "max_file_bytes",
        "max_upload_bytes",
        "max_owner_bytes",
        "upload_concurrency_advice",
        "upload_chunk_bytes",
        "upload_spool_bytes",
        "download_chunk_bytes",
        "max_file_name_bytes",
    ],
)
@pytest.mark.parametrize("value", [0, -1])
def test_config_rejects_non_positive_limits(field_name, value):
    # max_owner_bytes accepts negative values as "unlimited"; only 0 is
    # rejected for it. Every other limit field must be strictly positive.
    if field_name == "max_owner_bytes" and value < 0:
        pytest.skip("max_owner_bytes is unlimited when negative")
    with pytest.raises(ValueError, match="positive"):
        ServeConfig(**{field_name: value})


def test_config_allows_unlimited_owner_quota():
    # A negative max_owner_bytes disables the per-owner quota and must
    # construct successfully (the framework default is now -1).
    assert ServeConfig(max_owner_bytes=-1).max_owner_bytes == -1


def test_config_supported_extension_list_parsing():
    extensions = ServeConfig().supported_extension_list

    for expected in (".csv", ".xlsx", ".json", ".pdf", ".docx", ".md", ".txt"):
        assert expected in extensions
    assert all(extension.startswith(".") for extension in extensions)

    custom = ServeConfig(supported_extensions=" .csv ,, .txt ")
    assert custom.supported_extension_list == [".csv", ".txt"]


def test_error_codes_are_stable_and_explicit():
    expected = {
        "MISSING_AUTH_OWNER",
        "SESSION_FILE_SERVICE_UNAVAILABLE",
        "MISSING_SESSION_ID",
        "INVALID_SESSION_ID",
        "INVALID_FILE_NAME",
        "FILE_NAME_TOO_LONG",
        "EMPTY_FILE_UPLOAD",
        "EMPTY_FILE",
        "TOO_MANY_FILES",
        "FILE_TOO_LARGE",
        "REQUEST_TOO_LARGE",
        "SESSION_FILE_NOT_FOUND",
        "PREVIEW_NOT_READY",
        "SESSION_FILE_FAILED",
        "SESSION_FILE_INTERNAL",
    }
    assert {code.value for code in SessionFileErrorCode} == expected
    # Reuses the domain code shared with chat-side file input normalization.
    assert SessionFileErrorCode.TOO_MANY_FILES.value == "TOO_MANY_FILES"


def test_response_from_private_record_exposes_only_public_fields():
    response = SessionFileResponse.from_private_record(_private_record())

    payload = json.loads(response.model_dump_json())

    assert set(payload) == _PUBLIC_RESPONSE_KEYS
    assert payload["file_id"] == "sf_contract"
    assert payload["name"] == "report.csv"
    assert payload["size"] == 42
    assert payload["media_type"] == "text/csv"
    assert payload["kind"] == "table"
    assert payload["status"] == "ready"
    assert payload["ordinal"] == 0
    assert payload["error_code"] is None

    serialized = json.dumps(payload)
    for marker in _PRIVATE_MARKERS:
        assert marker not in serialized
    assert "file:///managed" not in serialized
    assert "a" * 64 not in serialized
    assert "parser detail" not in serialized


def test_response_from_manifest_has_no_error_code():
    manifest = SessionFileManifest(
        file_id="sf_m",
        name="m.csv",
        size=3,
        media_type="text/csv",
        kind="table",
        status=SessionFileStatus.READY,
        ordinal=4,
    )

    response = SessionFileResponse.from_manifest(manifest)

    assert response.file_id == "sf_m"
    assert response.ordinal == 4
    assert response.error_code is None


def test_response_passes_through_error_code_for_failed_records():
    record = _private_record(
        status=SessionFileStatus.PREVIEW_FAILED, error_code="UNSUPPORTED_TYPE"
    )

    response = SessionFileResponse.from_private_record(record)

    assert response.status == "preview_failed"
    assert response.error_code == "UNSUPPORTED_TYPE"


def test_preview_response_carries_bounded_preview_data():
    response = SessionFilePreviewResponse(
        file_id="sf_p",
        name="p.csv",
        media_type="text/csv",
        kind="table",
        status="ready",
        truncated=True,
        preview={"rows": [["a"], ["b"]]},
        error_code=None,
    )

    payload = json.loads(response.model_dump_json())

    assert payload["preview"] == {"rows": [["a"], ["b"]]}
    assert payload["truncated"] is True
    assert payload["error_code"] is None


def test_capabilities_response_mirrors_config():
    config = ServeConfig(
        max_files_per_upload=7,
        max_file_bytes=11,
        max_upload_bytes=101,
        max_owner_bytes=202,
        upload_request_timeout_seconds=99,
        upload_concurrency_advice=5,
        supported_extensions=".csv,.txt",
    )

    response = SessionFileCapabilitiesResponse.from_config(config)

    payload = json.loads(response.model_dump_json())
    assert payload == {
        "max_files_per_upload": 7,
        "max_file_bytes": 11,
        "max_upload_bytes": 101,
        "max_owner_bytes": 202,
        "upload_request_timeout_seconds": 99,
        "upload_concurrency": 5,
        "supported_extensions": [".csv", ".txt"],
    }
