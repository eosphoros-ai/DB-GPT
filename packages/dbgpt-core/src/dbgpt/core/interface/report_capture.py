"""Agent-loop-neutral capture context for report execution artifacts."""

from __future__ import annotations

import base64
import contextvars
import hashlib
import json
import logging
import math
import mimetypes
import os
import re
import shutil
import tempfile
import threading
import uuid
from collections.abc import Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import date, datetime, time, timezone
from decimal import Decimal
from enum import Enum
from pathlib import Path
from time import perf_counter
from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    Iterator,
    List,
    Literal,
    Optional,
    Protocol,
    Sequence,
    Tuple,
    cast,
    runtime_checkable,
)
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import TypeAdapter

from .report import (
    MAX_ARTIFACT_ID_LENGTH,
    MAX_CONV_UID_LENGTH,
    MAX_MESSAGE_ID_LENGTH,
    MAX_RUN_ID_LENGTH,
    MAX_STEP_ID_LENGTH,
    MAX_TASK_ID_LENGTH,
    Artifact,
    ArtifactContent,
    ArtifactTiming,
    ChartArtifact,
    ExecutionReference,
    PythonArtifact,
    ReferenceArtifact,
    SQLArtifact,
)

_ARTIFACT_ADAPTER = TypeAdapter(Artifact)
MAX_REFERENCE_EXCERPT_CHARS = 4_000
logger = logging.getLogger(__name__)
_SENSITIVE_QUERY_NAMES = {
    "access_token",
    "api_key",
    "apikey",
    "auth",
    "authorization",
    "code",
    "credential",
    "key",
    "password",
    "passwd",
    "secret",
    "session",
    "signature",
    "sig",
    "token",
    "x-amz-credential",
    "x-amz-signature",
    "x-amz-security-token",
    "x-goog-credential",
    "x-goog-signature",
}

_SENSITIVE_QUERY_PARTS = {
    "credential",
    "key",
    "password",
    "passwd",
    "secret",
    "signature",
    "token",
}
_SENSITIVE_COMPACT_QUERY_NAMES = {
    "apikey",
    "accesskey",
    "accesskeyid",
    "awsaccesskeyid",
    "clientsecret",
    "idtoken",
    "privatekey",
    "refreshtoken",
    "secretkey",
}


def _uuid_token() -> str:
    return uuid.uuid4().hex


def _require_text(name: str, value: str, max_length: Optional[int] = None) -> str:
    if not value.strip():
        raise ValueError(f"{name} must not be blank")
    if max_length is not None and len(value) > max_length:
        raise ValueError(f"{name} exceeds {max_length} characters")
    return value


def _validate_optional_text(name: str, value: Optional[str], max_length: int) -> None:
    if value is not None:
        _require_text(name, value, max_length)


def _validate_artifact_persistence_coordinates(artifact: Artifact) -> None:
    _require_text("artifact_id", artifact.artifact_id, MAX_ARTIFACT_ID_LENGTH)
    for input_id in artifact.input_artifact_ids:
        _require_text("input_artifact_id", input_id, MAX_ARTIFACT_ID_LENGTH)

    execution = artifact.execution
    _require_text("execution.conv_uid", execution.conv_uid, MAX_CONV_UID_LENGTH)
    _require_text("execution.step_id", execution.step_id, MAX_STEP_ID_LENGTH)
    _validate_optional_text(
        "execution.message_id", execution.message_id, MAX_MESSAGE_ID_LENGTH
    )
    _validate_optional_text("execution.task_id", execution.task_id, MAX_TASK_ID_LENGTH)
    _validate_optional_text("execution.run_id", execution.run_id, MAX_RUN_ID_LENGTH)


@dataclass(frozen=True)
class ArtifactCaptureContext:
    """Correlation metadata and identifier generation for one capture run."""

    conv_uid: str
    run_id: Optional[str] = None
    message_id: Optional[str] = None
    task_id: Optional[str] = None
    id_factory: Callable[[], str] = field(
        default=_uuid_token,
        repr=False,
        compare=False,
    )
    _id_lock: threading.Lock = field(
        default_factory=threading.Lock,
        init=False,
        repr=False,
        compare=False,
    )

    def __post_init__(self) -> None:
        _require_text("conv_uid", self.conv_uid, MAX_CONV_UID_LENGTH)
        _validate_optional_text("run_id", self.run_id, MAX_RUN_ID_LENGTH)
        _validate_optional_text("message_id", self.message_id, MAX_MESSAGE_ID_LENGTH)
        _validate_optional_text("task_id", self.task_id, MAX_TASK_ID_LENGTH)

    def _next_token(self) -> str:
        with self._id_lock:
            token = str(self.id_factory())
        return _require_text("generated id", token)

    def new_artifact_id(self, artifact_type: str) -> str:
        """Return an opaque ID with a human-readable artifact type prefix."""
        prefix = _require_text("artifact_type", artifact_type).strip()
        return _require_text(
            "artifact_id",
            f"{prefix}-{self._next_token()}",
            MAX_ARTIFACT_ID_LENGTH,
        )

    def execution_reference(
        self,
        *,
        action: str,
        step_id: Optional[str] = None,
    ) -> ExecutionReference:
        """Create a reference for one real action invocation."""
        action = _require_text("action", action)
        resolved_step_id = _require_text(
            "step_id",
            step_id or f"{action}-{self._next_token()}",
            MAX_STEP_ID_LENGTH,
        )
        return ExecutionReference(
            conv_uid=self.conv_uid,
            step_id=resolved_step_id,
            message_id=self.message_id,
            task_id=self.task_id,
            run_id=self.run_id,
            action=action,
        )


@runtime_checkable
class ArtifactSink(Protocol):
    """Minimal producer contract for recording typed execution artifacts."""

    @property
    def context(self) -> ArtifactCaptureContext:
        """Return correlation metadata for this sink."""

    def record(self, artifact: Artifact) -> None:
        """Record one artifact owned by this capture context."""

    def snapshot(self) -> List[Artifact]:
        """Return an immutable-by-ownership snapshot of recorded artifacts."""


_EVIDENCE_FIELDS = (
    "type",
    "status",
    "error",
    "result",
    "sql",
    "database",
    "code",
    "exit_code",
    "spec",
    "chart_type",
    "output",
    "reference_type",
    "source_id",
    "source_name",
    "uri",
    "locator",
    "excerpt",
    "score",
    "input_artifact_ids",
)


def _evidence_signature(artifact: Any) -> Dict[str, Any]:
    """Identify captured evidence without capture-time metadata.

    ``created_at``, ``duration_ms``, ``timing`` and ``execution`` describe when
    and by which step the same evidence was captured, so they must not turn an
    idempotent re-read into a conflicting duplicate.
    """
    dumped = artifact.model_dump(mode="json")
    return {key: value for key, value in dumped.items() if key in _EVIDENCE_FIELDS}


class InMemoryArtifactSink:
    """Thread-safe run-level artifact collector used before report assembly."""

    def __init__(self, context: ArtifactCaptureContext):
        self._context = context
        self._artifacts: List[Artifact] = []
        self._artifact_ids: set[str] = set()
        self._lock = threading.Lock()

    @property
    def context(self) -> ArtifactCaptureContext:
        """Return correlation metadata for this sink."""
        return self._context

    @property
    def artifact_count(self) -> int:
        """Return the current count without copying artifact payloads."""
        with self._lock:
            return len(self._artifacts)

    def record(self, artifact: Artifact) -> None:
        """Record a defensive copy after ownership and uniqueness checks."""
        payload = artifact.model_dump(mode="python", warnings="none")
        created_at = payload.pop("created_at")
        _validate_json_value(payload, set())
        payload["created_at"] = (
            created_at.isoformat() if isinstance(created_at, datetime) else created_at
        )
        validated = _ARTIFACT_ADAPTER.validate_json(
            json.dumps(
                payload,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            )
        )

        _validate_artifact_persistence_coordinates(validated)
        if validated.status is None or validated.duration_ms is None:
            raise ValueError("captured artifact requires status and duration")
        if validated.execution.conv_uid != self.context.conv_uid:
            raise ValueError(
                f"artifact {validated.artifact_id} belongs to conversation "
                f"{validated.execution.conv_uid}, expected {self.context.conv_uid}"
            )
        if validated.execution.run_id != self.context.run_id:
            raise ValueError(
                f"artifact {validated.artifact_id} belongs to run "
                f"{validated.execution.run_id}, expected {self.context.run_id}"
            )
        with self._lock:
            if validated.artifact_id in validated.input_artifact_ids:
                raise ValueError(
                    f"artifact {validated.artifact_id} cannot depend on itself"
                )
            if validated.artifact_id in self._artifact_ids:
                existing = next(
                    artifact
                    for artifact in self._artifacts
                    if artifact.artifact_id == validated.artifact_id
                )
                if _evidence_signature(existing) == _evidence_signature(validated):
                    # Tools capture deterministic ids, so re-reading one slice
                    # (for example to bind it after a report resume) must not
                    # be fatal; conflicting evidence still raises.
                    return
                raise ValueError(f"duplicate artifact id: {validated.artifact_id}")
            for input_id in validated.input_artifact_ids:
                if input_id not in self._artifact_ids:
                    raise ValueError(f"unknown input artifact {input_id}")
            self._artifacts.append(validated)
            self._artifact_ids.add(validated.artifact_id)

    def snapshot(self) -> List[Artifact]:
        """Return deep copies so consumers cannot mutate captured evidence."""
        with self._lock:
            return [artifact.model_copy(deep=True) for artifact in self._artifacts]


_current_artifact_sink: contextvars.ContextVar[Optional[ArtifactSink]] = (
    contextvars.ContextVar("dbgpt_report_artifact_sink", default=None)
)


@contextmanager
def bind_artifact_sink(sink: ArtifactSink) -> Iterator[ArtifactSink]:
    """Bind a sink to the current context and restore nested bindings safely."""
    token = _current_artifact_sink.set(sink)
    try:
        yield sink
    finally:
        _current_artifact_sink.reset(token)


def get_current_artifact_sink() -> Optional[ArtifactSink]:
    """Return the sink bound to the current execution context, if any."""
    return _current_artifact_sink.get()


def sanitize_reference_uri(value: str) -> str:
    """Remove credentials from persisted HTTP(S) reference URLs."""
    try:
        parsed = urlsplit(value)
        if parsed.scheme.lower() not in {"http", "https"}:
            return value
        hostname = parsed.hostname or ""
        host = f"[{hostname}]" if ":" in hostname else hostname
        netloc = f"{host}:{parsed.port}" if parsed.port is not None else host
        query = urlencode(
            [
                (name, "[REDACTED]" if _is_sensitive_query_name(name) else item)
                for name, item in parse_qsl(parsed.query, keep_blank_values=True)
            ],
            doseq=True,
        )
        return urlunsplit((parsed.scheme, netloc, parsed.path, query, ""))
    except Exception:
        logger.warning("Unable to sanitize reference URI; omitting it", exc_info=True)
        return ""


def _is_sensitive_query_name(name: str) -> bool:
    normalized = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", name).lower()
    if normalized in _SENSITIVE_QUERY_NAMES:
        return True
    parts = {part for part in re.split(r"[^a-z0-9]+", normalized) if part}
    compact = re.sub(r"[^a-z0-9]", "", normalized)
    return bool(parts & _SENSITIVE_QUERY_PARTS) or compact in (
        _SENSITIVE_COMPACT_QUERY_NAMES
    )


def capture_reference_artifact(
    *,
    reference_type: Literal["knowledge", "memory", "web", "model"],
    source_id: object,
    action: str,
    duration_ms: int,
    status: Literal["succeeded", "failed"] = "succeeded",
    error: Optional[str] = None,
    source_name: Optional[object] = None,
    uri: Optional[object] = None,
    locator: Optional[Dict[str, Any]] = None,
    excerpt: Optional[str] = None,
    excerpt_parts: Optional[Iterable[str]] = None,
    excerpt_separator: str = "",
    score: Optional[float] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    """Record a knowledge, memory, web, or model reference if capture is active."""
    sink = get_current_artifact_sink()
    if sink is None:
        return None
    try:
        if excerpt is not None and excerpt_parts is not None:
            raise ValueError("provide excerpt or excerpt_parts, not both")
        excerpt_digest = hashlib.sha256()
        preview_parts: List[str] = []
        preview_chars = 0
        excerpt_chars = 0
        if excerpt_parts is not None:
            for index, part in enumerate(excerpt_parts):
                if index:
                    _update_text_digest(excerpt_digest, excerpt_separator)
                    excerpt_chars += len(excerpt_separator)
                    remaining = MAX_REFERENCE_EXCERPT_CHARS - preview_chars
                    if remaining > 0:
                        preview_separator = excerpt_separator[:remaining]
                        preview_parts.append(preview_separator)
                        preview_chars += len(preview_separator)
                text_part = str(part)
                _update_text_digest(excerpt_digest, text_part)
                excerpt_chars += len(text_part)
                remaining = MAX_REFERENCE_EXCERPT_CHARS - preview_chars
                if remaining > 0:
                    preview_part = text_part[:remaining]
                    preview_parts.append(preview_part)
                    preview_chars += len(preview_part)
            preview = "".join(preview_parts)
        else:
            complete_excerpt = excerpt or ""
            _update_text_digest(excerpt_digest, complete_excerpt)
            excerpt_chars = len(complete_excerpt)
            preview = complete_excerpt[:MAX_REFERENCE_EXCERPT_CHARS]
        summary = {
            "excerpt_chars": excerpt_chars,
            "excerpt_sha256": excerpt_digest.hexdigest(),
            "excerpt_truncated": excerpt_chars > MAX_REFERENCE_EXCERPT_CHARS,
        }
        normalized_locator = cast(
            Dict[str, Any], normalize_artifact_value(locator or {})
        )
        for key, value in normalized_locator.items():
            if isinstance(value, str) and (key == "url" or key.endswith("_url")):
                normalized_locator[key] = sanitize_reference_uri(value)
        normalized_metadata = cast(
            Dict[str, Any], normalize_artifact_value(metadata or {})
        )
        normalized_metadata["content_summary"] = summary
        resolved_score = (
            float(score)
            if isinstance(score, (int, float))
            and math.isfinite(float(score))
            and score >= 0
            else None
        )
        resolved_source_name = (
            sanitize_reference_uri(str(source_name))
            if source_name is not None
            else None
        )
        resolved_uri = sanitize_reference_uri(str(uri)) if uri is not None else None
        artifact = ReferenceArtifact(
            artifact_id=sink.context.new_artifact_id("reference"),
            execution=sink.context.execution_reference(action=action),
            created_at=datetime.now(timezone.utc),
            status=status,
            duration_ms=max(0, duration_ms),
            timing=ArtifactTiming(server_execution_ms=max(0, duration_ms)),
            error=error[:MAX_REFERENCE_EXCERPT_CHARS] if error is not None else None,
            reference_type=reference_type,
            source_id=str(source_id) if source_id is not None else "",
            source_name=resolved_source_name,
            uri=resolved_uri or None,
            locator=normalized_locator,
            excerpt=preview or None,
            score=resolved_score,
            metadata=normalized_metadata,
        )
        sink.record(artifact)
        return artifact.artifact_id
    except Exception:
        logger.warning("Unable to capture reference report artifact", exc_info=True)
        return None


def sha256_bytes(value: bytes) -> str:
    """Hash exact bytes using lowercase SHA-256 hex encoding."""
    return hashlib.sha256(value).hexdigest()


def _update_text_digest(digest: Any, value: str) -> None:
    for offset in range(0, len(value), 64 * 1024):
        digest.update(value[offset : offset + 64 * 1024].encode("utf-8"))


def sha256_text(value: str) -> str:
    """Hash UTF-8 text without platform-dependent newline conversion."""
    digest = hashlib.sha256()
    _update_text_digest(digest, value)
    return digest.hexdigest()


def normalize_artifact_value(value: Any) -> Any:
    """Normalize common execution values without ambiguous ``default=str``."""
    if value is None or isinstance(value, (str, bool, int)):
        return value
    value_type = type(value)
    if value_type.__module__.startswith("pandas.") and value_type.__name__ in {
        "NAType",
        "NaTType",
    }:
        return None
    if isinstance(value, float):
        if math.isfinite(value):
            return value
        if math.isnan(value):
            return {"$number": "NaN"}
        return {"$number": "Infinity" if value > 0 else "-Infinity"}
    if isinstance(value, Decimal):
        return {"$decimal": str(value)}
    if isinstance(value, datetime):
        return {"$datetime": value.isoformat()}
    if isinstance(value, date):
        return {"$date": value.isoformat()}
    if isinstance(value, time):
        return {"$time": value.isoformat()}
    if isinstance(value, uuid.UUID):
        return {"$uuid": str(value)}
    if isinstance(value, (bytes, bytearray, memoryview)):
        return {"$bytes_base64": base64.b64encode(bytes(value)).decode("ascii")}
    if isinstance(value, Enum):
        return normalize_artifact_value(value.value)
    # SQLAlchemy Result rows are neither tuples nor dictionaries, but expose
    # their stable column/value view through ``_mapping``.  Treating the Row
    # object itself as unsupported discarded otherwise successful SQL evidence.
    row_mapping = getattr(value, "_mapping", None)
    if isinstance(row_mapping, Mapping):
        if not all(isinstance(key, str) for key in row_mapping):
            raise ValueError("artifact mappings require string keys")
        return {
            key: normalize_artifact_value(item) for key, item in row_mapping.items()
        }
    if isinstance(value, (list, tuple)):
        return [normalize_artifact_value(item) for item in value]
    if isinstance(value, dict):
        if not all(isinstance(key, str) for key in value):
            raise ValueError("artifact mappings require string keys")
        return {key: normalize_artifact_value(item) for key, item in value.items()}
    item_method = getattr(value, "item", None)
    if callable(item_method):
        item = item_method()
        if item is not value:
            return normalize_artifact_value(item)
    raise ValueError(f"unsupported artifact value: {type(value).__name__}")


def summarize_tabular_artifact(
    columns: Sequence[str],
    rows: Iterable[Any],
    *,
    max_preview_rows: int,
    max_preview_bytes: int,
    write_chunk: Optional[Callable[[bytes], Any]] = None,
) -> Tuple[Dict[str, Any], str, int, bool]:
    """Hash normalized rows incrementally and retain a bounded inline preview."""
    normalized_columns = [str(column) for column in columns]

    def canonical_bytes(item: Any) -> bytes:
        return json.dumps(
            item,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")

    digest = hashlib.sha256()

    def emit(chunk: bytes) -> None:
        digest.update(chunk)
        if write_chunk is not None:
            write_chunk(chunk)

    emit(b'{"columns":')
    emit(canonical_bytes(normalized_columns))
    emit(b',"rows":[')
    preview_rows: List[Any] = []
    preview_bytes = len(canonical_bytes({"columns": normalized_columns, "rows": []}))
    row_count = 0
    for row in rows:
        normalized_row = normalize_artifact_value(row)
        encoded_row = canonical_bytes(normalized_row)
        if row_count:
            emit(b",")
        emit(encoded_row)
        if (
            len(preview_rows) < max_preview_rows
            and preview_bytes + len(encoded_row) + 1 <= max_preview_bytes
        ):
            preview_rows.append(normalized_row)
            preview_bytes += len(encoded_row) + 1
        row_count += 1
    emit(b"]}")
    truncated = len(preview_rows) < row_count
    preview: Dict[str, Any] = {"columns": normalized_columns, "rows": preview_rows}
    if truncated:
        preview.update({"complete_row_count": row_count, "truncated": True})
    return preview, digest.hexdigest(), row_count, truncated


def _validate_json_value(value: object, active_containers: set) -> None:
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        if math.isfinite(value):
            return
        raise ValueError("value must be strict JSON-compatible data")
    if isinstance(value, (list, dict)):
        identity = id(value)
        if identity in active_containers:
            raise ValueError("value must be strict JSON-compatible data")
        active_containers.add(identity)
        try:
            if isinstance(value, list):
                for item in value:
                    _validate_json_value(item, active_containers)
            else:
                for key, item in value.items():
                    if not isinstance(key, str):
                        raise ValueError("value must be strict JSON-compatible data")
                    _validate_json_value(item, active_containers)
        finally:
            active_containers.remove(identity)
        return
    raise ValueError("value must be strict JSON-compatible data")


def sha256_json(value: object) -> str:
    """Hash strict canonical JSON, rejecting lossy or non-finite values."""
    _validate_json_value(value, set())
    try:
        payload = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as error:
        raise ValueError("value must be strict JSON-compatible data") from error
    return sha256_text(payload)


MAX_CAPTURE_STREAM_CHARS = 50_000
MAX_CAPTURE_ERROR_CHARS = 8_000
MAX_SQL_PREVIEW_BYTES = 256 * 1024
MAX_SQL_PREVIEW_ROWS = 100
IMAGE_EXTENSIONS = frozenset({".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"})


def artifact_storage_root() -> Path:
    """One durable content store for files, results and renderer observations."""
    from dbgpt.configs.model_config import PILOT_PATH

    root = Path(PILOT_PATH) / "data" / "report-artifacts"
    root.mkdir(parents=True, exist_ok=True)
    return root.resolve()


def store_artifact_file(path: str | Path) -> ArtifactContent:
    source = Path(path)
    before = source.stat()
    root = artifact_storage_root()
    with tempfile.NamedTemporaryFile(dir=root, delete=False) as target:
        temporary = Path(target.name)
        try:
            with source.open("rb") as stream:
                shutil.copyfileobj(stream, target)
        except BaseException:
            target.close()
            temporary.unlink(missing_ok=True)
            raise
    try:
        after = source.stat()
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise ValueError("FILE_CHANGED_DURING_CAPTURE: retry the file snapshot")
        digest, size = _sha256_file(str(temporary))
        suffix = source.suffix.lower()
        if not re.fullmatch(r"\.[a-z0-9]{1,12}", suffix):
            suffix = ".bin"
        name = digest + suffix
        os.replace(temporary, root / name)
        return ArtifactContent(
            uri="artifact://" + name,
            media_type=mimetypes.guess_type(source.name)[0]
            or "application/octet-stream",
            sha256=digest,
            size=size,
        )
    finally:
        temporary.unlink(missing_ok=True)


def artifact_content_path(uri: str) -> Path:
    """Resolve only stored, content-addressed blobs, never arbitrary paths."""
    name = uri.removeprefix("artifact://")
    if not uri.startswith("artifact://") or not re.fullmatch(
        r"[a-f0-9]{64}\.[a-z0-9]{1,12}", name
    ):
        raise ValueError("ARTIFACT_URI_INVALID")
    path = artifact_storage_root() / name
    if not path.is_file():
        raise ValueError("ARTIFACT_CONTENT_MISSING")
    if _sha256_file(str(path))[0] != name.split(".", 1)[0]:
        raise ValueError("ARTIFACT_CONTENT_CHANGED")
    return path


def store_artifact_json(value: Any) -> ArtifactContent:
    payload = json.dumps(
        normalize_artifact_value(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    digest = sha256_bytes(payload)
    path = artifact_storage_root() / (digest + ".json")
    if not path.exists():
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(payload)
        os.replace(temporary, path)
    return ArtifactContent(
        uri="artifact://" + path.name,
        media_type="application/json",
        sha256=digest,
        size=len(payload),
    )


def read_artifact_result(artifact: Any) -> Any:
    result = getattr(artifact, "result", None)
    if result is None:
        raise ValueError("ARTIFACT_RESULT_REQUIRED")
    uri = getattr(result, "uri", None)
    if uri and uri.startswith("artifact://"):
        return json.loads(artifact_content_path(uri).read_text(encoding="utf-8"))
    return result.inline


def select_artifact_result(artifact: Any, selector: dict) -> Any:
    """The same field/path resolver is used by capture and report assembly."""
    if selector.get("kind") == "sql":
        quote = selector.get("quote")
        if (
            getattr(artifact, "type", None) != "sql"
            or not isinstance(quote, str)
            or not quote.strip()
            or quote not in artifact.sql
            or "field" in selector
            or "path" in selector
        ):
            raise ValueError(
                "SQL_SELECTOR_INVALID: expected an exact captured SQL quote"
            )
        return quote
    return select_result_value(
        read_artifact_result(artifact),
        normalize_artifact_result_selector(artifact, selector),
    )


def normalize_artifact_result_selector(artifact: Any, selector: dict) -> dict:
    """Record a sole payload field when a shorthand path resolves inside it.

    Direct paths and explicit fields retain their meaning. Missing or ambiguous
    paths remain errors; this never searches other artifacts or guesses a metric.
    """
    if "field" in selector or "path" not in selector or selector.get("kind") == "sql":
        return selector
    result = read_artifact_result(artifact)
    try:
        select_result_value(result, selector)
        return selector
    except (ValueError, TypeError):
        pass
    if isinstance(result, dict) and len(result) == 1:
        candidate = {**selector, "field": next(iter(result))}
        try:
            select_result_value(result, candidate)
            return candidate
        except (ValueError, TypeError):
            pass
    return selector


def sql_predicate_quotes(artifact: Any) -> list[tuple[str, str, str]]:
    """Read literal comparisons from executed SQL, excluding LIMIT/CASE constants."""
    if getattr(artifact, "type", None) != "sql":
        return []
    import sqlparse
    from sqlparse.sql import Comparison, Identifier, TokenList
    from sqlparse.tokens import Literal, Operator

    predicates = []

    def visit(group):
        if isinstance(group, Comparison):
            tokens = [token for token in group.tokens if not token.is_whitespace]
            if (
                len(tokens) == 3
                and isinstance(tokens[0], Identifier)
                and tokens[1].ttype in Operator.Comparison
                and tokens[2].ttype in Literal.Number
            ):
                predicates.append((tokens[1].value, tokens[2].value, group.value))
        for token in group.tokens:
            if isinstance(token, TokenList):
                visit(token)

    for statement in sqlparse.parse(artifact.sql):
        visit(statement)
    return list(dict.fromkeys(predicates))


def select_result_value(value: Any, selector: dict) -> Any:
    """Resolve a captured value using the report's shared selector semantics."""
    from .report import normalize_result_selector

    selector = normalize_result_selector(selector)
    field = selector.get("field")
    if field is not None:
        if (
            not isinstance(field, str)
            or not isinstance(value, dict)
            or field not in value
        ):
            raise ValueError("RESULT_SELECTOR_INVALID: field does not exist")
        value = value[field]
    path = selector.get("path", [])
    if path and isinstance(value, str):
        value = json.loads(value)
    for index, key in enumerate(path):
        if isinstance(value, dict) and isinstance(key, str) and key in value:
            value = value[key]
        elif isinstance(value, list) and isinstance(key, int) and 0 <= key < len(value):
            value = value[key]
        else:
            raise ValueError(
                f"RESULT_SELECTOR_INVALID: path[{index}]={key!r} does not exist"
            )
    return value


def capture_file_artifact(
    path: str | Path,
    sink: ArtifactSink,
    *,
    action: str,
    input_artifact_ids: Sequence[str] = (),
) -> ReferenceArtifact:
    started = perf_counter()
    source = Path(path)
    content = store_artifact_file(source)
    existing = next(
        (
            item
            for item in sink.snapshot()
            if isinstance(item, ReferenceArtifact)
            and item.reference_type == "file"
            and item.uri == content.uri
            and item.locator.get("path") == str(source.resolve())
            and (
                not input_artifact_ids
                or item.input_artifact_ids == list(input_artifact_ids)
            )
        ),
        None,
    )
    if existing:
        return existing
    artifact = ReferenceArtifact(
        artifact_id=sink.context.new_artifact_id("reference"),
        execution=sink.context.execution_reference(action=action),
        input_artifact_ids=list(input_artifact_ids),
        created_at=datetime.now(timezone.utc),
        status="succeeded",
        duration_ms=max(0, int((perf_counter() - started) * 1000)),
        reference_type="file",
        source_id=content.sha256,
        source_name=source.name,
        uri=content.uri,
        locator={"path": str(source.resolve()), "sha256": content.sha256},
        metadata={"content": content.model_dump(exclude_none=True)},
    )
    sink.record(artifact)
    return artifact


def snapshot_execution_files(
    arguments: Any,
    sink: Optional[ArtifactSink],
    *,
    action: str,
) -> tuple[Any, List[str]]:
    """Freeze supplied input files and link exact snapshots to their consumers."""
    if sink is None:
        return arguments, []
    ids: List[str] = []
    execution_inputs = None
    prepared = {}

    def visit(value: Any, key: str = "") -> Any:
        nonlocal execution_inputs
        if isinstance(value, dict):
            return {name: visit(item, name) for name, item in value.items()}
        if isinstance(value, list):
            return [visit(item, key) for item in value]
        if not isinstance(value, str) or key.startswith(("output", "plot", "save")):
            return value
        try:
            source = Path(value)
            if not source.is_file():
                return value
        except OSError:
            return value
        artifact = capture_file_artifact(source, sink, action=action)
        ids.append(artifact.artifact_id)
        if artifact.artifact_id not in prepared:
            # The process may write to its input. Keep archived bytes immutable
            # while preserving the original filename for existing skill code.
            if execution_inputs is None:
                execution_inputs = Path(
                    tempfile.mkdtemp(
                        prefix="execution-inputs-", dir=artifact_storage_root()
                    )
                )
            target = execution_inputs / artifact.artifact_id / source.name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(artifact_content_path(cast(str, artifact.uri)), target)
            prepared[artifact.artifact_id] = str(target)
        return prepared[artifact.artifact_id]

    return visit(arguments), list(dict.fromkeys(ids))


def execution_output_files(directory: str, *, images: bool = False) -> List[str]:
    controls = {
        "_run.py",
        "_report_sql_results.json",
        "_sql_inputs.json",
        "_sql_inputs.pending",
    }
    return [
        str(path)
        for path in Path(directory).rglob("*")
        if path.is_file()
        and path.name not in controls
        and (path.suffix.lower() in IMAGE_EXTENSIONS) == images
    ]


def resolve_argument_dependencies(
    arguments: Any, sink: Optional[ArtifactSink], explicit_ids: Sequence[str] = ()
) -> List[str]:
    """Resolve whole structured inputs by exact content; reject ambiguous origins."""
    if sink is None:
        return list(explicit_ids)
    index: Dict[str, set[str]] = {}
    for artifact in sink.snapshot():
        if artifact.status != "succeeded" or not isinstance(
            artifact, (SQLArtifact, PythonArtifact)
        ):
            continue
        value = read_artifact_result(artifact) if artifact.result else None
        for candidate in [value, *(value.values() if isinstance(value, dict) else [])]:
            if isinstance(candidate, str):
                try:
                    candidate = json.loads(candidate)
                except ValueError:
                    continue
            if isinstance(candidate, (dict, list)) and candidate:
                index.setdefault(
                    sha256_json(normalize_artifact_value(candidate)), set()
                ).add(artifact.artifact_id)
    found = set(explicit_ids)

    def visit(value):
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except ValueError:
                return
        if not isinstance(value, (dict, list)) or not value:
            return
        candidates = index.get(sha256_json(normalize_artifact_value(value)), set())
        if len(candidates) > 1 and not candidates.intersection(explicit_ids):
            raise ValueError(
                "INPUT_LINEAGE_AMBIGUOUS: provide the actual input_artifact_ids"
            )
        if len(candidates) == 1:
            found.update(candidates)
            return
        if not candidates:
            for item in value.values() if isinstance(value, dict) else value:
                visit(item)

    visit(arguments)
    return sorted(found)


class TrackedSQLResults(list):
    """Persist which datasets are accessed, including dynamic indexes."""

    def __init__(self, values: list, trace_path: str):
        super().__init__(values)
        self.trace_path = trace_path
        self.used: set[str] = set()
        self.loaded: dict[str, dict] = {}

    def _record(self, value):
        items = value if isinstance(value, list) else [value]
        loaded = []
        for item in items:
            if isinstance(item, dict) and isinstance(item.get("artifact_id"), str):
                self.used.add(item["artifact_id"])
                if item["artifact_id"] in self.loaded:
                    item = self.loaded[item["artifact_id"]]
                elif item.get("content_uri"):
                    data = json.loads(
                        artifact_content_path(item["content_uri"]).read_text(
                            encoding="utf-8"
                        )
                    )
                    item = {
                        **item,
                        **restore_artifact_value(data),
                        "truncated": False,
                        "row_count": len(data["rows"]),
                    }
                    self.loaded[item["artifact_id"]] = item
                elif item.get("truncated"):
                    raise ValueError(
                        "SQL_RESULT_INCOMPLETE: historical result has no full snapshot"
                    )
            loaded.append(item)
        trace = Path(self.trace_path)
        temporary = trace.with_suffix(".pending")
        temporary.write_text(json.dumps(sorted(self.used)), encoding="utf-8")
        os.replace(temporary, trace)
        return loaded if isinstance(value, list) else loaded[0]

    def __getitem__(self, index):
        return self._record(super().__getitem__(index))

    def __iter__(self):
        for item in super().__iter__():
            yield self._record(item)

    def copy(self):
        return list(self)

    def pop(self, index=-1):
        return self._record(super().pop(index))

    def __reversed__(self):
        for item in super().__reversed__():
            yield self._record(item)

    def __add__(self, other):
        return list(self) + other

    def __mul__(self, count):
        return list(self) * count

    __rmul__ = __mul__


def sql_execution_context(sink: Optional[ArtifactSink]) -> List[dict]:
    if sink is None:
        return []
    values = []
    for item in sink.snapshot():
        if not isinstance(item, SQLArtifact) or item.status != "succeeded":
            continue
        # Successful SQLArtifact validation requires a captured result.
        result = cast(ArtifactContent, item.result)
        values.append(
            {
                "artifact_id": item.artifact_id,
                "sql": item.sql,
                "content_uri": result.uri,
                "row_count": item.row_count,
                **(
                    result.inline
                    if isinstance(result.inline, dict)
                    else {"columns": item.columns, "rows": result.inline or []}
                ),
            }
        )
    return values


def restore_artifact_value(value: Any) -> Any:
    if isinstance(value, list):
        return [restore_artifact_value(item) for item in value]
    if not isinstance(value, dict):
        return value
    if len(value) == 1:
        if "$decimal" in value:
            return Decimal(value["$decimal"])
        if "$number" in value:
            return float(value["$number"])
        if "$datetime" in value:
            return datetime.fromisoformat(value["$datetime"])
        if "$date" in value:
            return date.fromisoformat(value["$date"])
        if "$time" in value:
            return time.fromisoformat(value["$time"])
        if "$bytes_base64" in value:
            return base64.b64decode(value["$bytes_base64"])
        if "$uuid" in value:
            return uuid.UUID(value["$uuid"])
    return {key: restore_artifact_value(item) for key, item in value.items()}


def _bounded_error(error: Optional[str]) -> Optional[str]:
    return error[:MAX_CAPTURE_ERROR_CHARS] if error is not None else None


def _error_summary(error: Optional[str]) -> dict:
    if error is None:
        return {}
    return {
        "error_chars": len(error),
        "error_sha256": sha256_text(error),
        "error_truncated": len(error) > MAX_CAPTURE_ERROR_CHARS,
    }


def _sha256_file(path: str) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with open(path, "rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def connector_database_name(
    database_connector: Any, artifact_sink: Optional[ArtifactSink] = None
) -> Optional[str]:
    """Return the current DB identity without exposing connector credentials."""
    if artifact_sink is None and get_current_artifact_sink() is None:
        return None
    try:
        name = getattr(database_connector, "_db_name", None)
        if name:
            return str(name)
        getter = getattr(database_connector, "get_current_db_name", None)
        if callable(getter):
            value = getter()
            return str(value) if value else None
    except Exception:
        logger.debug("Unable to resolve connector database name", exc_info=True)
    return None


def capture_sql_execution(
    *,
    sql: str,
    database: Optional[str],
    duration_ms: int,
    columns: Optional[Sequence[str]] = None,
    rows: Optional[Sequence[Any]] = None,
    error: Optional[str] = None,
    action: str = "sql_query",
    display_type: str = "response_table",
    artifact_sink: Optional[ArtifactSink] = None,
) -> Optional[str]:
    """Record one real SQL attempt and archive its complete result."""
    sink = artifact_sink or get_current_artifact_sink()
    if sink is None:
        return None

    try:
        artifact_id = sink.context.new_artifact_id("sql")
        normalized_columns = [str(column) for column in (columns or [])]
        failed = error is not None
        result = None
        complete_sha256 = None
        row_count = None
        preview_truncated = False
        if not failed:
            with tempfile.NamedTemporaryFile(
                dir=artifact_storage_root(), suffix=".json", delete=False
            ) as stream:
                temporary = Path(stream.name)
                try:
                    result_value, complete_sha256, row_count, preview_truncated = (
                        summarize_tabular_artifact(
                            normalized_columns,
                            rows if rows is not None else [],
                            max_preview_rows=MAX_SQL_PREVIEW_ROWS,
                            max_preview_bytes=MAX_SQL_PREVIEW_BYTES,
                            write_chunk=stream.write,
                        )
                    )
                except BaseException:
                    stream.close()
                    temporary.unlink(missing_ok=True)
                    raise
            try:
                result = store_artifact_file(temporary)
                result.inline = result_value
            finally:
                temporary.unlink(missing_ok=True)
        artifact = SQLArtifact(
            artifact_id=artifact_id,
            execution=sink.context.execution_reference(action=action),
            created_at=datetime.now(timezone.utc),
            status="failed" if failed else "succeeded",
            duration_ms=max(0, duration_ms),
            timing=ArtifactTiming(server_execution_ms=max(0, duration_ms)),
            error=_bounded_error(error),
            sql=sql,
            database=database,
            display_type=display_type,
            columns=normalized_columns,
            row_count=row_count,
            result=result,
            metadata={
                "input_summary": {
                    "sql_chars": len(sql),
                    "sql_sha256": sha256_text(sql),
                },
                "output_summary": {
                    "column_count": len(normalized_columns),
                    "row_count": row_count,
                    "complete_result_sha256": complete_sha256,
                    "preview_truncated": preview_truncated,
                    **_error_summary(error),
                },
            },
        )
        sink.record(artifact)
        return artifact_id
    except Exception as error:
        logger.warning("Unable to capture SQL report artifact", exc_info=True)
        raise ValueError(
            "ARTIFACT_CAPTURE_FAILED: SQL attempt completed but its snapshot "
            "could not be saved; do not rerun the query. " + str(error)
        ) from error


def capture_python_execution(
    *,
    code: str,
    duration_ms: int,
    status: str,
    exit_code: Optional[int],
    stdout: str,
    stderr: str,
    error: Optional[str] = None,
    image_urls: Optional[Sequence[str]] = None,
    result_inline: Optional[Any] = None,
    input_artifact_ids: Optional[Sequence[str]] = None,
    metadata: Optional[dict[str, Any]] = None,
    action: str = "code_interpreter",
    language: str = "python",
    images: Optional[Sequence[dict]] = None,
    output_files: Optional[Sequence[str]] = None,
    artifact_sink: Optional[ArtifactSink] = None,
) -> Optional[str]:
    """Record subprocess state before user-facing output is truncated."""
    sink = artifact_sink or get_current_artifact_sink()
    if sink is None:
        return None

    try:
        artifact_id = sink.context.new_artifact_id("python")
        urls = [*(image_urls or []), *(image["uri"] for image in (images or []))]
        if result_inline is None and status == "succeeded":
            try:
                result_inline = json.loads(stdout)
            except (ValueError, TypeError):
                pass
        if urls:
            result_inline = (
                {**result_inline, "images": urls}
                if isinstance(result_inline, dict)
                else {
                    "images": urls,
                    **({"value": result_inline} if result_inline is not None else {}),
                }
            )
        result = (
            store_artifact_json(result_inline) if result_inline is not None else None
        )
        if result is not None:
            result.inline = normalize_artifact_value(result_inline)
        artifact = PythonArtifact(
            artifact_id=artifact_id,
            execution=sink.context.execution_reference(action=action),
            input_artifact_ids=list(input_artifact_ids or []),
            created_at=datetime.now(timezone.utc),
            status=status,
            duration_ms=max(0, duration_ms),
            timing=ArtifactTiming(server_execution_ms=max(0, duration_ms)),
            error=_bounded_error(error),
            code=code,
            language=language,
            exit_code=exit_code,
            stdout=stdout[:MAX_CAPTURE_STREAM_CHARS],
            stderr=stderr[:MAX_CAPTURE_STREAM_CHARS],
            result=result,
            metadata={
                "streams": store_artifact_json(
                    {"stdout": stdout, "stderr": stderr}
                ).model_dump(exclude_none=True),
                "input_summary": {
                    "code_chars": len(code),
                    "code_sha256": sha256_text(code),
                },
                "output_summary": {
                    "stdout_chars": len(stdout),
                    "stdout_sha256": sha256_text(stdout),
                    "stdout_truncated": len(stdout) > MAX_CAPTURE_STREAM_CHARS,
                    "stderr_chars": len(stderr),
                    "stderr_sha256": sha256_text(stderr),
                    "stderr_truncated": len(stderr) > MAX_CAPTURE_STREAM_CHARS,
                    "image_count": len(urls),
                    **_error_summary(error),
                },
                **(metadata or {}),
            },
        )
        sink.record(artifact)
        if status == "succeeded":
            for image in images or []:
                capture_generated_chart(
                    source_artifact_id=artifact_id,
                    uri=image["uri"],
                    path=image["path"],
                    filename=image["filename"],
                    artifact_sink=sink,
                )
            for path in dict.fromkeys(output_files or []):
                capture_file_artifact(
                    path,
                    sink,
                    action=action + ".file",
                    input_artifact_ids=[artifact_id],
                )
        return artifact_id
    except Exception:
        logger.warning("Unable to capture Python report artifact", exc_info=True)
        raise


def publish_generated_images(paths: Sequence[str]) -> List[dict]:
    """Publish exact image bytes once; tools only adapt their output chunks."""
    from dbgpt.configs.model_config import STATIC_MESSAGE_IMG_PATH

    target_dir = Path(STATIC_MESSAGE_IMG_PATH)
    target_dir.mkdir(parents=True, exist_ok=True)
    images = []
    for path in dict.fromkeys(paths):
        source = Path(path)
        content = store_artifact_file(source)
        snapshot = artifact_content_path(cast(str, content.uri))
        name = f"{cast(str, content.sha256)[:16]}_{source.name}"
        shutil.copyfile(snapshot, target_dir / name)
        images.append(
            {
                "source_path": str(source),
                "uri": f"/images/{name}",
                "path": str(snapshot),
                "filename": source.name,
            }
        )
    return images


def capture_chart_execution(
    *,
    input_artifact_ids: Sequence[str],
    chart_type: str,
    spec: dict,
    action: str,
    duration_ms: int = 0,
    error: Optional[str] = None,
    output_inline: Any = None,
    output_uri: Optional[str] = None,
    output_path: Optional[str] = None,
    media_type: str = "application/json",
    name: Optional[str] = None,
    metadata: Optional[dict] = None,
    artifact_sink: Optional[ArtifactSink] = None,
) -> Optional[str]:
    sink = artifact_sink or get_current_artifact_sink()
    if sink is None:
        return None
    content = (
        store_artifact_file(output_path)
        if output_path
        else store_artifact_json(output_inline)
        if output_inline is not None
        else None
    )
    details = dict(metadata or {})
    if content and output_uri:
        details["content"] = content.model_dump(exclude_none=True)
        content = content.model_copy(update={"uri": output_uri})
    if content:
        content.media_type = media_type
        if (
            isinstance(output_inline, str)
            and len(output_inline) > MAX_CAPTURE_STREAM_CHARS
        ):
            content.inline = output_inline[:MAX_CAPTURE_STREAM_CHARS]
            details["output_preview_truncated"] = True
        else:
            content.inline = normalize_artifact_value(output_inline)
    artifact = ChartArtifact(
        artifact_id=sink.context.new_artifact_id("chart"),
        execution=sink.context.execution_reference(action=action),
        input_artifact_ids=list(dict.fromkeys(input_artifact_ids)),
        created_at=datetime.now(timezone.utc),
        status="failed" if error else "succeeded",
        duration_ms=max(0, duration_ms),
        error=_bounded_error(error),
        timing=ArtifactTiming(
            server_execution_ms=max(0, duration_ms),
            browser_render_state="not_measured",
            derivative_processing_state=(
                "included_in_source_execution" if output_path else "not_applicable"
            ),
        ),
        name=name,
        chart_type=chart_type,
        spec=normalize_artifact_value(spec),
        output=content,
        metadata=details,
    )
    sink.record(artifact)
    return artifact.artifact_id


def capture_generated_chart(
    *,
    source_artifact_id: str,
    uri: str,
    path: str,
    filename: str,
    artifact_sink: Optional[ArtifactSink] = None,
) -> Optional[str]:
    """Record one image emitted by a previously recorded Python execution."""
    return capture_chart_execution(
        input_artifact_ids=[source_artifact_id],
        chart_type="image",
        spec={"source": "code_interpreter", "filename": filename},
        action="code_interpreter.image",
        output_uri=uri,
        output_path=path,
        media_type=mimetypes.guess_type(filename)[0] or "application/octet-stream",
        name=filename,
        artifact_sink=artifact_sink,
    )


__all__ = [
    "ArtifactCaptureContext",
    "ArtifactSink",
    "MAX_REFERENCE_EXCERPT_CHARS",
    "InMemoryArtifactSink",
    "bind_artifact_sink",
    "capture_reference_artifact",
    "get_current_artifact_sink",
    "normalize_artifact_value",
    "sanitize_reference_uri",
    "sha256_bytes",
    "sha256_json",
    "sha256_text",
    "summarize_tabular_artifact",
    "artifact_content_path",
    "artifact_storage_root",
    "capture_chart_execution",
    "capture_file_artifact",
    "capture_generated_chart",
    "capture_python_execution",
    "capture_sql_execution",
    "connector_database_name",
    "execution_output_files",
    "IMAGE_EXTENSIONS",
    "publish_generated_images",
    "read_artifact_result",
    "resolve_argument_dependencies",
    "select_artifact_result",
    "select_result_value",
    "snapshot_execution_files",
    "sql_execution_context",
    "store_artifact_file",
    "store_artifact_json",
    "TrackedSQLResults",
]
