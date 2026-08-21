"""Bridge session-file ``file_ids`` chat input to the ReAct agent runtime.

Responsibilities:

- normalize ``ConversationVo.ext_info`` file input through the
  :class:`~dbgpt_serve.session_file.domain.FileInputSpec` domain contract —
  conflicting/malformed/too-many inputs map to deterministic 400 errors
  before any agent or tool is constructed;
- resolve ``file_ids`` against the session file registry strictly for the
  authenticated owner and ``dialogue.conv_uid`` — missing, foreign-owned,
  wrong-session, failed and deleted files all raise the same
  indistinguishable, non-enumerating 404-style error; only ``ready`` and
  ``preview_failed`` files are accepted, in request order;
- build the prompt manifest block (file ids + public metadata + the
  per-turn materialized path — never storage URIs, bodies or hashes);
- materialize resolved files under the registry work root and keep the
  materialization context open until the turn ends. Materialized local
  paths are per-turn temporary copies: they may reach prompts and tool
  observations so the model can analyze files with ``code_interpreter``,
  and they are scrubbed at the share boundary (see
  :func:`scrub_react_history_for_share`). Storage URIs and hashes remain
  internal everywhere; ``files_json_path`` stays an internal child-process
  handoff detail.
"""

import contextlib
import io
import json
import logging
import os
import stat
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple

from starlette.concurrency import run_in_threadpool

from dbgpt_serve.session_file.domain import (
    FileInputError,
    FileInputSpec,
    FileScope,
    SessionFileManifest,
    SessionFilePrivateRecord,
    SessionFileStatus,
    parse_file_input,
)

logger = logging.getLogger(__name__)

MAX_CHAT_FILES = 20

FILE_NOT_FOUND_CODE = "SESSION_FILE_NOT_FOUND"
FILE_NOT_FOUND_MESSAGE = "File not found."

_ACCEPTED_STATUSES = (
    SessionFileStatus.READY,
    SessionFileStatus.PREVIEW_FAILED,
)

_FILE_INPUT_MESSAGES = {
    "CONFLICTING_FILE_INPUTS": "file_ids and file_path cannot be used together.",
    "INVALID_FILE_IDS": "The file_ids input is invalid.",
    "INVALID_FILE_PATH": "The file_path input is invalid.",
    "TOO_MANY_FILES": "Too many files requested.",
}


class AttachmentInputError(Exception):
    """Deterministic chat attachment error carrying an HTTP-style mapping."""

    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


def _not_found() -> AttachmentInputError:
    """Return one generic error for every unresolvable file reference.

    Missing, foreign-owned, wrong-session, failed and deleted files all map
    to the same status/code/message so callers cannot enumerate which
    file_ids exist.
    """
    return AttachmentInputError(404, FILE_NOT_FOUND_CODE, FILE_NOT_FOUND_MESSAGE)


def _invalid_file_path() -> AttachmentInputError:
    """Return the deterministic 400 for malformed legacy file_path input."""
    return AttachmentInputError(
        400, "INVALID_FILE_PATH", _FILE_INPUT_MESSAGES["INVALID_FILE_PATH"]
    )


def _owner_roots(base_dir: str, owner_id: Optional[str]) -> Tuple[Path, Path]:
    """Return the ``(resolved, lexical)`` owner upload roots, failing closed.

    A blank or separator-carrying owner id can never establish a trustworthy
    root, so it is rejected with the same generic 404 as any other ownership
    failure. A symlinked owner root resolving outside ``python_uploads`` is
    rejected as well.
    """
    owner = (owner_id or "").strip()
    if (
        not owner
        or owner in (".", "..")
        or "\x00" in owner
        or "/" in owner
        or "\\" in owner
    ):
        raise _not_found()
    lexical_root = Path(base_dir, "python_uploads") / owner
    uploads_root = lexical_root.parent.resolve()
    owner_root = lexical_root.resolve()
    try:
        owner_root.relative_to(uploads_root)
    except ValueError:
        raise _not_found() from None
    if owner_root == uploads_root or os.path.islink(lexical_root):
        raise _not_found()
    return owner_root, lexical_root


def resolve_legacy_chat_file_path(
    *, file_path: Any, owner_id: Optional[str], base_dir: str
) -> str:
    """Validate a legacy ``ext_info.file_path`` against the owner root.

    The returned path is a resolved regular file strictly inside
    ``<base_dir>/python_uploads/<owner>``. Ownership failures (cross-owner
    paths, arbitrary absolute paths outside the root, ``..`` traversal,
    symlinks, missing or non-regular files) all raise the same generic,
    non-enumerating 404; malformed input (blank, non-string, NUL bytes or
    Windows separators) raises a deterministic 400.
    """
    if (
        not isinstance(file_path, str)
        or not file_path.strip()
        or "\x00" in file_path
        or "\\" in file_path
    ):
        raise _invalid_file_path()
    owner_root, lexical_root = _owner_roots(base_dir, owner_id)

    candidate = Path(file_path)
    if not candidate.is_absolute():
        candidate = lexical_root / candidate
    # Lexical traversal is rejected outright — never normalize it away.
    if ".." in candidate.parts:
        raise _not_found()

    # Walk the owner-relative lexical components before resolve() so a
    # symlinked parent directory (or final symlink) is rejected instead of
    # silently followed. Only components under the owner root are probed, so
    # platform-level symlinks above the root (e.g. /var -> /private/var) do
    # not cause false rejections.
    try:
        relative = candidate.relative_to(lexical_root)
    except ValueError:
        relative = None
    if relative is not None and relative.parts:
        probe = lexical_root
        for part in relative.parts:
            probe = probe / part
            if os.path.islink(probe):
                raise _not_found()

    try:
        resolved = candidate.resolve()
    except OSError:
        raise _not_found() from None
    try:
        resolved.relative_to(owner_root)
    except ValueError:
        raise _not_found() from None
    if resolved == owner_root:
        raise _not_found()
    try:
        mode = os.lstat(resolved).st_mode
    except OSError:
        raise _not_found() from None
    if stat.S_ISLNK(mode) or not stat.S_ISREG(mode):
        raise _not_found()
    return str(resolved)


def parse_chat_file_input(
    ext_info: Optional[Mapping[str, Any]], max_files: int = MAX_CHAT_FILES
) -> FileInputSpec:
    """Normalize chat file input through the FileInputSpec domain contract.

    Raises:
        AttachmentInputError: 400 with the deterministic domain code for
            conflicting/malformed/too-many file input.
    """
    try:
        return parse_file_input(ext_info, max_files=max_files)
    except FileInputError as error:
        raise AttachmentInputError(
            400, error.code, _FILE_INPUT_MESSAGES.get(error.code, error.code)
        ) from error


def _format_size(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    value = float(size)
    for unit in ("KB", "MB", "GB"):
        value /= 1024
        if value < 1024 or unit == "GB":
            text = f"{value:.1f}"
            if text.endswith(".0"):
                text = text[:-2]
            return f"{text} {unit}"
    return f"{size} B"


def _to_manifest(record: SessionFilePrivateRecord) -> SessionFileManifest:
    return SessionFileManifest(
        file_id=record.file_id,
        name=record.display_name,
        size=record.size_bytes,
        media_type=record.media_type,
        kind=record.file_kind,
        status=record.status,
        ordinal=record.ordinal,
    )


def build_manifest_prompt(
    manifests: Tuple[SessionFileManifest, ...],
    local_paths: Optional[Dict[str, str]] = None,
) -> str:
    """Build the numbered manifest block for the system prompt.

    Every line carries ``[file_id] name — kind, media_type, size, status``
    plus the per-turn materialized ``path`` when available. The path is a
    temporary local copy valid only for the current turn, exposed so the
    model can analyze the file with ``code_interpreter`` without guessing;
    storage URIs, file bodies and hashes never appear here.
    """
    paths = local_paths or {}
    lines = []
    for index, manifest in enumerate(manifests, start=1):
        line = (
            f"{index}. [{manifest.file_id}] {manifest.name} — {manifest.kind}, "
            f"{manifest.media_type}, {_format_size(manifest.size)}, "
            f"{manifest.status.value}"
        )
        path = paths.get(manifest.file_id)
        if path:
            line += f"\n   path: {path} (valid for this turn only)"
        lines.append(line)
    body = "\n".join(lines)
    return (
        "\n## User Attachments\n"
        f"{body}\n"
        "- Analyze these files if needed for the user's request. Use the "
        "shown path with code_interpreter for free-form analysis (valid for "
        "this turn only — re-run load_file in a new turn), or reference "
        "files by file_id.\n"
    )


def _public_inspection(record: SessionFilePrivateRecord) -> Dict[str, Any]:
    """Parse the persisted bounded inspection for prompt/tool summaries.

    The inspector itself guarantees the preview is bounded and free of
    paths, storage URIs, bodies and hashes; anything malformed degrades to
    an empty preview instead of failing the turn.
    """
    try:
        data = json.loads(record.inspection_json or "{}")
    except Exception:
        data = {}
    preview = data.get("preview")
    return {
        "preview": preview if isinstance(preview, dict) else {},
        "truncated": bool(data.get("truncated")),
    }


@dataclass
class SessionAttachmentContext:
    """Resolved attachment state for one chat turn.

    ``manifests``/``prompt``/``inspections`` are public and safe to render.
    ``local_paths``/``primary_local_path`` are per-turn temporary copies:
    they may reach prompts and tool observations so the model can analyze
    files with ``code_interpreter``; they are deleted on :meth:`close` and
    scrubbed at the share boundary (see
    :func:`scrub_react_history_for_share`). ``files_json_path`` remains
    internal (child-process handoff only). Storage URIs and hashes never
    leave the registry.
    """

    manifests: Tuple[SessionFileManifest, ...]
    prompt: str
    inspections: Dict[str, Dict[str, Any]]
    local_paths: Dict[str, str]
    primary_local_path: str
    files_json_path: str
    _stack: contextlib.ExitStack = field(repr=False)

    def close(self) -> None:
        """Drop the materialized run directories created for this turn."""
        self._stack.close()


def _resolve_records(
    registry: Any,
    *,
    owner_id: str,
    session_id: str,
    file_ids: Tuple[str, ...],
) -> List[SessionFilePrivateRecord]:
    """Resolve file_ids in request order with non-enumerating 404s."""
    records: List[SessionFilePrivateRecord] = []
    for file_id in file_ids:
        record = registry.get_file(
            owner_id=owner_id, session_id=session_id, file_id=file_id
        )
        if record is None or record.status not in _ACCEPTED_STATUSES:
            raise _not_found()
        records.append(record)
    return records


def open_session_attachments(
    registry: Any,
    *,
    owner_id: str,
    session_id: str,
    file_ids: Tuple[str, ...],
) -> SessionAttachmentContext:
    """Resolve and materialize file_ids for an owner-scoped conversation.

    The returned context keeps every materialized run directory (and the
    ``files_json`` mapping) alive until :meth:`SessionAttachmentContext.close`
    is called when the turn ends.
    """
    records = _resolve_records(
        registry, owner_id=owner_id, session_id=session_id, file_ids=file_ids
    )
    scope = FileScope(owner_id, session_id=session_id)
    stack = contextlib.ExitStack()
    try:
        local_paths: Dict[str, str] = {}
        for record in records:
            opened = registry.open_download(
                owner_id=owner_id, session_id=session_id, file_id=record.file_id
            )
            if opened is None:
                raise _not_found()
            stream, _record = opened
            suffix = Path(record.display_name).suffix
            local_path = stack.enter_context(
                registry.materialize_local_file(scope, stream, suffix)
            )
            local_paths[record.file_id] = str(local_path)
        files_json_payload = json.dumps(local_paths, ensure_ascii=False).encode("utf-8")
        files_json_path = stack.enter_context(
            registry.materialize_local_file(
                scope, io.BytesIO(files_json_payload), ".json"
            )
        )
    except Exception:
        stack.close()
        raise
    manifests = tuple(_to_manifest(record) for record in records)
    return SessionAttachmentContext(
        manifests=manifests,
        prompt=build_manifest_prompt(manifests, local_paths),
        inspections={record.file_id: _public_inspection(record) for record in records},
        local_paths=local_paths,
        primary_local_path=local_paths[records[0].file_id],
        files_json_path=str(files_json_path),
        _stack=stack,
    )


def _session_file_registry() -> Any:
    """Return the bound session file registry; fails closed when unbound."""
    from dbgpt_serve.session_file.api.endpoints import get_session_file_service

    return get_session_file_service()


async def prepare_react_attachments(
    dialogue: Any, *, owner_id: Optional[str], registry: Any = None
) -> Optional[SessionAttachmentContext]:
    """Validate and open a turn attachment context for a chat request.

    Returns ``None`` for pure-text or legacy ``file_path`` requests so those
    paths keep their existing behavior unchanged.
    """
    try:
        spec = dialogue.file_input_spec()
    except FileInputError as error:
        raise AttachmentInputError(
            400,
            error.code,
            _FILE_INPUT_MESSAGES.get(error.code, error.code),
        ) from error
    if not spec.file_ids:
        return None
    owner = (owner_id or "").strip()
    if not owner:
        raise AttachmentInputError(
            401, "MISSING_AUTH_OWNER", "An authenticated owner is required."
        )
    registry = registry if registry is not None else _session_file_registry()
    session_id = dialogue.conv_uid
    if not ((session_id or "").strip()):
        # A session-scoped FileScope rejects a blank id with a bare ValueError,
        # which would surface as an opaque 500; fail deterministically with 400.
        raise AttachmentInputError(
            400, "MISSING_SESSION_ID", "A valid conversation id is required."
        )
    return await run_in_threadpool(
        lambda: open_session_attachments(
            registry,
            owner_id=owner,
            session_id=session_id,
            file_ids=spec.file_ids,
        )
    )


def react_state_patch(ctx: SessionAttachmentContext) -> Dict[str, Any]:
    """Return the react_state entries for the ReAct runtime.

    ``session_files``/``session_file_inspections`` are public metadata.
    ``session_file_paths`` and ``file_path`` (legacy compatibility key) are
    the per-turn materialized paths tools may surface to the model for
    analysis; ``files_json_path`` stays internal (child-process handoff).
    """
    return {
        "session_files": list(ctx.manifests),
        "session_file_inspections": dict(ctx.inspections),
        "session_file_paths": dict(ctx.local_paths),
        "file_path": ctx.primary_local_path,
        "files_json_path": ctx.files_json_path,
    }


REACT_HISTORY_PAYLOAD_VERSION = 2

# Allowlist of snapshot fields that survive into public share payloads. The
# private ``file_id`` is intentionally excluded — it would be a usable key
# against the auth-protected preview/download endpoints.
_PUBLIC_SNAPSHOT_KEYS = (
    "name",
    "size",
    "media_type",
    "kind",
    "status",
    "ordinal",
)


def build_input_files_v2(manifests) -> List[Dict[str, Any]]:
    """Snapshot the current turn's input files for history payload v2.

    Each entry carries only public metadata (file_id, name, size, media_type,
    kind, status, ordinal) — never local paths, storage URIs, owner ids,
    hashes or inspection bodies. The snapshot covers only the current turn;
    later turns resolve files fresh from the registry instead of scanning old
    history messages.
    """
    return [
        {
            "file_id": manifest.file_id,
            "name": manifest.name,
            "size": manifest.size,
            "media_type": manifest.media_type,
            "kind": manifest.kind,
            "status": (
                manifest.status.value
                if hasattr(manifest.status, "value")
                else str(manifest.status)
            ),
            "ordinal": manifest.ordinal,
        }
        for manifest in manifests
    ]


_SHARE_PATH_PLACEHOLDER = "<server-path>"


def _share_path_prefixes() -> List[str]:
    """Absolute path prefixes scrubbed from public share payloads.

    Covers the three roots that legitimately appear in turns: the home
    directory (default work root and legacy upload roots), the configured
    registry work root (non-default deployments), and the pilot root
    (code_interpreter tracebacks). Missing config degrades gracefully.
    """
    prefixes: List[str] = []
    home = str(Path.home())
    if home and home != os.sep:
        prefixes.append(home)
    try:
        service = _session_file_registry()
        registry = getattr(service, "registry", None) or service
        work_root = getattr(registry, "work_root", None)
        if work_root:
            prefixes.append(str(work_root))
    except Exception:
        pass
    try:
        from dbgpt.configs.model_config import PILOT_PATH

        if PILOT_PATH:
            prefixes.append(str(PILOT_PATH))
    except Exception:
        pass
    return prefixes


def _scrub_server_paths(value: Any, prefixes: List[str]) -> Any:
    """Replace known server path prefixes in nested text with a placeholder.

    Only string values are touched; table/chart payloads keep their
    structure since their content rarely carries paths and replacements
    apply to any nested text uniformly.
    """
    if isinstance(value, str):
        for prefix in prefixes:
            needle = prefix + os.sep
            if needle in value:
                value = value.replace(needle, _SHARE_PATH_PLACEHOLDER + os.sep)
        return value
    if isinstance(value, list):
        return [_scrub_server_paths(item, prefixes) for item in value]
    if isinstance(value, dict):
        return {key: _scrub_server_paths(item, prefixes) for key, item in value.items()}
    return value


def scrub_react_history_for_share(context: str) -> str:
    """Return the share-safe form of a stored react history payload.

    v1 payloads, non-react payloads and non-JSON message contexts are
    returned unchanged so legacy messages stay readable. v2 payloads get
    their ``input_files`` rebuilt from a strict allowlist with the private
    ``file_id`` replaced by a non-resolvable ``display_key`` — public viewers
    must never receive a usable key for the auth-protected preview/download
    endpoints, nor any storage_uri/file_path/work_root internals.

    ``steps`` and ``final_content`` additionally get known server path
    prefixes (home directory, registry work root) replaced with
    ``<server-path>``: materialized paths legitimately surface in tool
    observations and tracebacks during a turn, and the share view is the
    trust boundary where they are masked. ``generated_images``,
    ``sub_agents`` and ``citations`` are passed through unchanged.
    """
    if not isinstance(context, str):
        return context
    try:
        payload = json.loads(context)
    except Exception:
        return context
    if not isinstance(payload, dict) or payload.get("type") != "react-agent":
        return context
    if payload.get("version") != REACT_HISTORY_PAYLOAD_VERSION:
        return context
    public_files: List[Dict[str, Any]] = []
    files = payload.get("input_files")
    if isinstance(files, list):
        for index, entry in enumerate(files, start=1):
            snapshot: Dict[str, Any] = {"display_key": f"file-{index}"}
            if isinstance(entry, dict):
                for key in _PUBLIC_SNAPSHOT_KEYS:
                    if key in entry:
                        snapshot[key] = entry[key]
            public_files.append(snapshot)
    payload["input_files"] = public_files
    prefixes = _share_path_prefixes()
    if prefixes:
        steps = payload.get("steps")
        if isinstance(steps, list):
            payload["steps"] = _scrub_server_paths(steps, prefixes)
        final_content = payload.get("final_content")
        if isinstance(final_content, str):
            payload["final_content"] = _scrub_server_paths(final_content, prefixes)
    return json.dumps(payload, ensure_ascii=False)


def build_file_context(
    ctx: Optional[SessionAttachmentContext], legacy_file_path: Optional[str]
) -> str:
    """Build the prompt file section.

    New ``file_ids`` requests use the public manifest block; legacy
    ``file_path`` requests keep their existing wording byte-for-byte; pure
    text requests stay empty.
    """
    if ctx is not None:
        return ctx.prompt
    if legacy_file_path:
        return f"""
## User Uploaded File
- File path: {legacy_file_path}
- Analyze this file if needed for the user's request.
"""
    return ""
