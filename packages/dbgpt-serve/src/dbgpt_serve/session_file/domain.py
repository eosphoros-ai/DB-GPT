"""Immutable domain values for session files and chat file input."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Iterable, Mapping, Optional, Tuple


class SessionFileStatus(str, Enum):
    """Lifecycle state exposed for a session file."""

    UPLOADING = "uploading"
    INSPECTING = "inspecting"
    READY = "ready"
    PREVIEW_FAILED = "preview_failed"
    FAILED = "failed"
    DELETED = "deleted"


@dataclass(frozen=True)
class SessionFileManifest:
    """Public file metadata safe to expose to an agent."""

    file_id: str
    name: str
    size: int
    media_type: str
    kind: str
    status: SessionFileStatus
    ordinal: int


@dataclass(frozen=True)
class SessionFileSnapshot:
    """Public file metadata safe to persist in conversation history."""

    file_id: str
    name: str
    size: int
    media_type: str
    kind: str
    status: SessionFileStatus
    ordinal: int


@dataclass(frozen=True)
class SessionFilePrivateRecord:
    """Immutable private file metadata for internal runtime consumers."""

    file_id: str
    owner_id: str
    session_id: Optional[str]
    task_id: Optional[str]
    display_name: str
    storage_uri: str
    media_type: str
    file_kind: str
    size_bytes: int
    sha256: str
    ordinal: int
    status: SessionFileStatus
    inspection_json: Optional[str]
    error_code: Optional[str]
    error_message: Optional[str]
    source_file_id: Optional[str]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]


@dataclass(frozen=True)
class FileScope:
    """Owner-bound scope for either an interactive session or a task."""

    owner_id: str
    session_id: Optional[str] = None
    task_id: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.owner_id.strip():
            raise ValueError("owner_id must not be blank")
        if (self.session_id is None) == (self.task_id is None):
            raise ValueError("exactly one of session_id and task_id is required")
        selected_scope = (
            self.session_id if self.session_id is not None else self.task_id
        )
        if not selected_scope or not selected_scope.strip():
            raise ValueError("file scope must not be blank")


class FileInputError(ValueError):
    """Deterministic request error raised while normalizing file input."""

    def __init__(self, code: str):
        super().__init__(code)
        self._code = code

    @property
    def code(self) -> str:
        """Return the stable machine-readable error code."""
        return self._code


_UNSET = object()


def _normalize_file_ids(file_ids: Iterable[str]) -> Tuple[str, ...]:
    if isinstance(file_ids, str):
        raise FileInputError("INVALID_FILE_IDS")
    try:
        values = tuple(file_ids)
    except TypeError as error:
        raise FileInputError("INVALID_FILE_IDS") from error
    if not values or any(
        not isinstance(file_id, str) or not file_id.strip() for file_id in values
    ):
        raise FileInputError("INVALID_FILE_IDS")
    return tuple(dict.fromkeys(values))


def _validate_file_path(file_path: Any) -> str:
    if not isinstance(file_path, str) or not file_path.strip():
        raise FileInputError("INVALID_FILE_PATH")
    return file_path


@dataclass(frozen=True, init=False)
class FileInputSpec:
    """Normalized new or legacy chat file input."""

    file_ids: Tuple[str, ...]
    file_path: Optional[str]

    def __init__(self, file_ids: Any = _UNSET, file_path: Any = _UNSET):
        has_file_ids = file_ids is not _UNSET
        has_file_path = file_path is not _UNSET
        if has_file_ids and has_file_path:
            raise FileInputError("CONFLICTING_FILE_INPUTS")
        if has_file_ids:
            normalized_ids = _normalize_file_ids(file_ids)
            normalized_path = None
        elif has_file_path:
            normalized_ids = ()
            normalized_path = _validate_file_path(file_path)
        else:
            raise FileInputError("INVALID_FILE_IDS")
        object.__setattr__(self, "file_ids", normalized_ids)
        object.__setattr__(self, "file_path", normalized_path)

    @classmethod
    def empty(cls) -> "FileInputSpec":
        """Return the normalized representation of a pure text request."""
        spec = object.__new__(cls)
        object.__setattr__(spec, "file_ids", ())
        object.__setattr__(spec, "file_path", None)
        return spec


def parse_file_input(
    ext_info: Optional[Mapping[str, Any]], max_files: int = 20
) -> FileInputSpec:
    """Normalize file references without mutating unrelated extension fields."""
    if not ext_info:
        return FileInputSpec.empty()

    has_file_ids = "file_ids" in ext_info
    has_file_path = "file_path" in ext_info
    if has_file_ids and has_file_path:
        raise FileInputError("CONFLICTING_FILE_INPUTS")

    if has_file_ids:
        raw_file_ids = ext_info["file_ids"]
        if not isinstance(raw_file_ids, list):
            raise FileInputError("INVALID_FILE_IDS")
        spec = FileInputSpec(file_ids=raw_file_ids)
        if len(spec.file_ids) > max_files:
            raise FileInputError("TOO_MANY_FILES")
        return spec

    if has_file_path:
        return FileInputSpec(file_path=ext_info["file_path"])

    return FileInputSpec.empty()
