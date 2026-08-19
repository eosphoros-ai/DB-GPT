"""Server-owned limits for session file upload, preview and download."""

from dataclasses import dataclass, field
from typing import List

from dbgpt_serve.core import BaseServeConfig

APP_NAME = "session_file"
SERVE_APP_NAME = "dbgpt_serve_session_file"
SERVE_APP_NAME_HUMP = "dbgpt_serve_SessionFile"
SERVE_CONFIG_KEY_PREFIX = "dbgpt.serve.session_file."
SERVE_SERVICE_COMPONENT_NAME = f"{SERVE_APP_NAME}_service"

_DEFAULT_SUPPORTED_EXTENSIONS = (
    ".csv,.tsv,.xls,.xlsx,.json,.jsonl,.parquet,.pdf,.doc,.docx,.pptx,.md,.txt"
)

_LIMIT_FIELDS = (
    "max_files_per_upload",
    "max_file_bytes",
    "max_upload_bytes",
    "max_owner_bytes",
    "upload_request_timeout_seconds",
    "upload_concurrency_advice",
    "upload_chunk_bytes",
    "upload_spool_bytes",
    "download_chunk_bytes",
    "max_file_name_bytes",
)


@dataclass
class ServeConfig(BaseServeConfig):
    """Limits advertised through the capabilities endpoint.

    The true parser allowlist is enforced by
    :class:`~dbgpt_serve.session_file.inspector.SessionFileInspector`;
    ``supported_extensions`` only mirrors it for client ``accept`` hints.
    """

    __type__ = APP_NAME
    SERVE_APP_NAME = APP_NAME
    SERVE_APP_NAME_HUMP = "SessionFile"

    max_files_per_upload: int = field(
        default=20,
        metadata={"help": "Maximum number of files accepted per upload request"},
    )
    max_file_bytes: int = field(
        default=100 * 1024 * 1024,
        metadata={"help": "Maximum byte size of a single uploaded file"},
    )
    max_upload_bytes: int = field(
        default=500 * 1024 * 1024,
        metadata={"help": "Maximum aggregate byte size of one upload request"},
    )
    max_owner_bytes: int = field(
        default=-1,
        metadata={
            "help": (
                "Total storage quota in bytes per owner; -1 (or any negative "
                "value) disables the per-owner quota (unlimited). Set a "
                "positive integer to enforce the limit."
            )
        },
    )
    upload_request_timeout_seconds: int = field(
        default=180,
        metadata={
            "help": (
                "Advertised per-request upload timeout in seconds. Surfaced "
                "through /capabilities so the client applies it as the upload "
                "timeout; override per deployment as needed."
            )
        },
    )
    upload_concurrency_advice: int = field(
        default=3,
        metadata={"help": "Advised client-side upload concurrency"},
    )
    upload_chunk_bytes: int = field(
        default=1024 * 1024,
        metadata={"help": "Chunk size for streaming uploads"},
    )
    upload_spool_bytes: int = field(
        default=8 * 1024 * 1024,
        metadata={"help": "In-memory spool threshold before disk rollover"},
    )
    download_chunk_bytes: int = field(
        default=1024 * 1024,
        metadata={"help": "Chunk size for streaming downloads"},
    )
    max_file_name_bytes: int = field(
        default=255,
        metadata={"help": "Maximum UTF-8 byte length of a display name"},
    )
    supported_extensions: str = field(
        default=_DEFAULT_SUPPORTED_EXTENSIONS,
        metadata={"help": "Comma separated extension allowlist mirror"},
    )

    def __post_init__(self) -> None:
        for name in _LIMIT_FIELDS:
            value = getattr(self, name)
            if name == "max_owner_bytes":
                # A negative value disables the per-owner quota (unlimited).
                # Zero is rejected to avoid the "zero-byte quota" ambiguity.
                if value == 0:
                    raise ValueError(f"{name} must be positive or -1 (unlimited)")
                continue
            if value <= 0:
                raise ValueError(f"{name} must be positive")

    @property
    def supported_extension_list(self) -> List[str]:
        """Return the extension allowlist parsed from the config string."""
        extensions = []
        for raw in self.supported_extensions.split(","):
            extension = raw.strip()
            if extension:
                extensions.append(extension)
        return extensions
