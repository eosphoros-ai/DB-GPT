"""Public API schemas for owner-aware session files."""

from enum import Enum
from typing import Any, Dict, List, Optional

from dbgpt._private.pydantic import BaseModel, Field

from ..config import ServeConfig
from ..domain import SessionFileManifest, SessionFilePrivateRecord


class SessionFileErrorCode(str, Enum):
    """Stable machine-readable error codes for session file APIs."""

    MISSING_AUTH_OWNER = "MISSING_AUTH_OWNER"
    SESSION_FILE_SERVICE_UNAVAILABLE = "SESSION_FILE_SERVICE_UNAVAILABLE"
    MISSING_SESSION_ID = "MISSING_SESSION_ID"
    INVALID_SESSION_ID = "INVALID_SESSION_ID"
    INVALID_FILE_NAME = "INVALID_FILE_NAME"
    FILE_NAME_TOO_LONG = "FILE_NAME_TOO_LONG"
    EMPTY_FILE_UPLOAD = "EMPTY_FILE_UPLOAD"
    EMPTY_FILE = "EMPTY_FILE"
    TOO_MANY_FILES = "TOO_MANY_FILES"
    FILE_TOO_LARGE = "FILE_TOO_LARGE"
    REQUEST_TOO_LARGE = "REQUEST_TOO_LARGE"
    SESSION_FILE_NOT_FOUND = "SESSION_FILE_NOT_FOUND"
    PREVIEW_NOT_READY = "PREVIEW_NOT_READY"
    SESSION_FILE_FAILED = "SESSION_FILE_FAILED"
    SESSION_FILE_INTERNAL = "SESSION_FILE_INTERNAL"


class SessionFileResponse(BaseModel):
    """Public file metadata; never carries server locations or hashes."""

    file_id: str = Field(..., description="Public session file identifier")
    name: str = Field(..., description="Original display name")
    size: int = Field(..., description="File size in bytes")
    media_type: str = Field(..., description="Inspected media type")
    kind: str = Field(..., description="Inspected file kind")
    status: str = Field(..., description="Lifecycle status")
    ordinal: int = Field(..., description="Upload order within the scope")
    error_code: Optional[str] = Field(
        default=None, description="Domain error code for failed or partial items"
    )

    @classmethod
    def from_manifest(cls, manifest: SessionFileManifest) -> "SessionFileResponse":
        """Map agent-safe metadata to the wire response."""
        return cls(
            file_id=manifest.file_id,
            name=manifest.name,
            size=manifest.size,
            media_type=manifest.media_type,
            kind=manifest.kind,
            status=manifest.status.value,
            ordinal=manifest.ordinal,
        )

    @classmethod
    def from_private_record(
        cls, record: SessionFilePrivateRecord
    ) -> "SessionFileResponse":
        """Whitelist public fields from a private record."""
        return cls(
            file_id=record.file_id,
            name=record.display_name,
            size=record.size_bytes,
            media_type=record.media_type,
            kind=record.file_kind,
            status=record.status.value,
            ordinal=record.ordinal,
            error_code=record.error_code,
        )


class SessionFilePreviewResponse(BaseModel):
    """Bounded preview data parsed by the inspection pipeline."""

    file_id: str = Field(..., description="Public session file identifier")
    name: str = Field(..., description="Original display name")
    media_type: str = Field(..., description="Inspected media type")
    kind: str = Field(..., description="Inspected file kind")
    status: str = Field(..., description="Lifecycle status")
    truncated: bool = Field(..., description="Whether the preview was capped")
    preview: Dict[str, Any] = Field(
        default_factory=dict, description="Bounded parsed preview data"
    )
    error_code: Optional[str] = Field(
        default=None, description="Domain error code when inspection failed"
    )


class SessionFileCapabilitiesResponse(BaseModel):
    """Server-owned upload limits and parser capabilities."""

    max_files_per_upload: int = Field(
        ..., description="Maximum files per upload request and per selection"
    )
    max_file_bytes: int = Field(..., description="Maximum bytes per file")
    max_upload_bytes: int = Field(
        ..., description="Maximum aggregate bytes per upload request"
    )
    max_owner_bytes: int = Field(..., description="Total storage quota per owner")
    upload_request_timeout_seconds: int = Field(
        ..., description="Advertised per-request upload timeout in seconds"
    )
    upload_concurrency: int = Field(
        ..., description="Advised client-side upload concurrency"
    )
    supported_extensions: List[str] = Field(
        ..., description="Extension allowlist accepted by the inspector"
    )

    @classmethod
    def from_config(cls, config: ServeConfig) -> "SessionFileCapabilitiesResponse":
        """Build the advertised capabilities from server configuration."""
        return cls(
            max_files_per_upload=config.max_files_per_upload,
            max_file_bytes=config.max_file_bytes,
            max_upload_bytes=config.max_upload_bytes,
            max_owner_bytes=config.max_owner_bytes,
            upload_request_timeout_seconds=config.upload_request_timeout_seconds,
            upload_concurrency=config.upload_concurrency_advice,
            supported_extensions=config.supported_extension_list,
        )
