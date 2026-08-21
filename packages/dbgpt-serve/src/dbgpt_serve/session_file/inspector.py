"""Bounded, allowlisted preview inspection for session files."""

import asyncio
import csv
import importlib
import io
import json
import multiprocessing
import os
import queue
import re
import threading
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Mapping, Optional, Tuple
from xml.etree import ElementTree

from .domain import SessionFileStatus

ParserResult = Tuple[Dict[str, Any], bool]
Parser = Callable[[Path, "InspectionLimits"], ParserResult]
OptionalImport = Callable[[str], Optional[Any]]


class _FrozenDict(dict):
    """JSON-serializable immutable mapping used by public results."""

    def _immutable(self, *args: Any, **kwargs: Any) -> None:
        raise TypeError("inspection preview is immutable")

    __delitem__ = _immutable
    __ior__ = _immutable
    __setitem__ = _immutable
    clear = _immutable
    pop = _immutable
    popitem = _immutable
    setdefault = _immutable
    update = _immutable

    def __reduce__(self):
        return _FrozenDict, (dict(self),)


@dataclass(frozen=True)
class InspectionLimits:
    """Hard limits applied to parser work and serialized preview output."""

    # Data rows per table preview (header row is not counted).
    max_rows: int = 20
    max_columns: int = 20
    max_sheets: int = 3
    max_pages: int = 10
    max_text_bytes: int = 16_384
    max_preview_bytes: int = 65_536
    max_sniff_bytes: int = 8_192
    max_parse_bytes: int = 16 * 1024 * 1024
    max_archive_entries: int = 2_000
    max_archive_uncompressed_bytes: int = 32 * 1024 * 1024
    max_archive_entry_bytes: int = 16 * 1024 * 1024
    max_compression_ratio: float = 100.0
    max_xml_nodes: int = 100_000
    max_open_files: int = 64
    timeout_seconds: float = 10.0
    queue_timeout_seconds: float = 10.0
    max_concurrency: int = 4

    def __post_init__(self) -> None:
        for name, value in vars(self).items():
            if value <= 0:
                raise ValueError(f"{name} must be positive")


@dataclass(frozen=True)
class InspectionResult:
    """Safe inspection metadata suitable for persistence and API responses."""

    kind: str
    media_type: str
    status: SessionFileStatus
    preview: Mapping[str, Any]
    truncated: bool
    error_code: Optional[str] = None
    error_message: Optional[str] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "preview", _freeze(self.preview))


class _InspectionError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.safe_message = message


INSPECTION_BUSY_CODE = "INSPECTION_BUSY"


_TYPE_INFO = {
    ".csv": ("table", "text/csv", "text"),
    ".tsv": ("table", "text/tab-separated-values", "text"),
    ".xls": ("table", "application/vnd.ms-excel", "ole"),
    ".xlsx": (
        "table",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "zip",
    ),
    ".json": ("table", "application/json", "text"),
    ".jsonl": ("table", "application/x-ndjson", "text"),
    ".parquet": ("table", "application/vnd.apache.parquet", "parquet"),
    ".pdf": ("document", "application/pdf", "pdf"),
    ".doc": ("document", "application/msword", "ole"),
    ".docx": (
        "document",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "zip",
    ),
    ".pptx": (
        "document",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "zip",
    ),
    ".md": ("document", "text/markdown", "text"),
    ".txt": ("document", "text/plain", "text"),
}

_MEDIA_ALIASES = {
    ".csv": {"text/csv", "application/csv", "text/plain"},
    ".tsv": {"text/tab-separated-values", "text/tsv", "text/plain"},
    ".json": {"application/json", "text/json"},
    ".jsonl": {"application/x-ndjson", "application/jsonl", "text/plain"},
    ".md": {"text/markdown", "text/plain"},
    ".txt": {"text/plain"},
}


class SessionFileInspector:
    """Inspect allowlisted files without exposing paths or unbounded parser output."""

    def __init__(
        self,
        limits: Optional[InspectionLimits] = None,
        document_adapter: Optional[Parser] = None,
        parsers: Optional[Mapping[str, Parser]] = None,
        optional_import: OptionalImport = None,
    ) -> None:
        self.limits = limits or InspectionLimits()
        self._optional_import = optional_import or _optional_import
        self._document_adapter = document_adapter or self._parse_document
        self._parsers = dict(parsers or {})
        self._has_document_adapter = document_adapter is not None
        self._has_optional_import = optional_import is not None
        self._slots = threading.BoundedSemaphore(self.limits.max_concurrency)

    def inspect(
        self, path: Path, declared_media_type: Optional[str] = None
    ) -> InspectionResult:
        """Inspect a local file with a wall-clock timeout."""
        if not self._slots.acquire(timeout=self.limits.queue_timeout_seconds):
            return self._failure(*_result_type(Path(path)), INSPECTION_BUSY_CODE)
        return self._inspect_with_acquired_slot(Path(path), declared_media_type)

    def _inspect_with_acquired_slot(
        self, path: Path, declared_media_type: Optional[str]
    ) -> InspectionResult:
        kind, media_type = _result_type(path)
        if self._uses_trusted_extension(path.suffix.lower()):
            completed, result = _run_trusted_thread(
                self._inspect_core,
                (path, declared_media_type),
                self.limits.timeout_seconds,
                self._slots,
            )
        else:
            try:
                completed, result = _run_isolated(
                    _inspect_builtin,
                    (path, declared_media_type, self.limits),
                    self.limits.timeout_seconds,
                    self.limits,
                )
            finally:
                self._slots.release()
        if not completed:
            return self._failure(kind, media_type, "INSPECTION_TIMEOUT")
        return result

    def _uses_trusted_extension(self, suffix: str) -> bool:
        if suffix in self._parsers:
            return True
        if suffix in {".doc", ".docx", ".pptx"} and self._has_document_adapter:
            return True
        return self._has_optional_import and suffix in {
            ".xls",
            ".xlsx",
            ".parquet",
            ".pdf",
        }

    async def inspect_async(
        self, path: Path, declared_media_type: Optional[str] = None
    ) -> InspectionResult:
        """Inspect without blocking the event loop, with bounded concurrency."""
        acquired = await asyncio.to_thread(
            self._slots.acquire, True, self.limits.queue_timeout_seconds
        )
        if not acquired:
            return self._failure(*_result_type(Path(path)), INSPECTION_BUSY_CODE)
        return await asyncio.to_thread(
            self._inspect_with_acquired_slot, Path(path), declared_media_type
        )

    def _inspect_core(
        self, path: Path, declared_media_type: Optional[str]
    ) -> InspectionResult:
        suffix = path.suffix.lower()
        type_info = _TYPE_INFO.get(suffix)
        if type_info is None:
            return self._failure(
                "binary", "application/octet-stream", "UNSUPPORTED_TYPE"
            )
        kind, media_type, signature = type_info
        try:
            if path.is_symlink():
                raise _InspectionError(
                    "UNSAFE_FILE_REFERENCE",
                    "File references outside the managed store are not allowed.",
                )
            size = path.stat().st_size
            if size > self.limits.max_parse_bytes:
                raise _InspectionError(
                    "PREVIEW_TOO_LARGE", "File exceeds the bounded preview input limit."
                )
            sniff = _read_prefix(path, self.limits.max_sniff_bytes)
            self._validate_type(path, suffix, signature, sniff, declared_media_type)
            if signature == "zip":
                _validate_zip_bounds(path, self.limits)
            parser = self._parsers.get(suffix) or self._parser_for(suffix)
            preview, truncated = parser(path, self.limits)
            _validate_preview(preview)
            preview, output_truncated = _bound_preview(
                preview, self.limits.max_preview_bytes
            )
            return InspectionResult(
                kind=kind,
                media_type=media_type,
                status=SessionFileStatus.READY,
                preview=preview,
                truncated=truncated or output_truncated,
            )
        except _InspectionError as error:
            return InspectionResult(
                kind=kind,
                media_type=media_type,
                status=SessionFileStatus.PREVIEW_FAILED,
                preview={},
                truncated=False,
                error_code=error.code,
                error_message=error.safe_message,
            )
        except Exception:
            return self._failure(kind, media_type, "CORRUPT_FILE")

    def _validate_type(
        self,
        path: Path,
        suffix: str,
        signature: str,
        sniff: bytes,
        declared_media_type: Optional[str],
    ) -> None:
        if declared_media_type:
            declared = declared_media_type.split(";", 1)[0].strip().lower()
            expected = _MEDIA_ALIASES.get(suffix, {_TYPE_INFO[suffix][1]})
            if declared not in expected and declared != "application/octet-stream":
                raise _InspectionError(
                    "TYPE_MISMATCH", "File type metadata does not match."
                )

        matches = {
            "pdf": sniff.startswith(b"%PDF-"),
            "zip": sniff.startswith((b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08")),
            "ole": sniff.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"),
            "parquet": sniff.startswith(b"PAR1"),
            "text": _looks_like_text(sniff),
        }
        if not matches[signature]:
            raise _InspectionError("TYPE_MISMATCH", "File signature does not match.")
        if signature == "zip":
            _validate_ooxml_type(path, suffix)

    def _parser_for(self, suffix: str) -> Parser:
        if suffix in {".csv", ".tsv"}:
            return self._parse_delimited
        if suffix in {".json", ".jsonl"}:
            return self._parse_json
        if suffix == ".xlsx":
            return self._parse_xlsx
        if suffix == ".xls":
            return self._parse_xls
        if suffix == ".parquet":
            return self._parse_parquet
        if suffix == ".pdf":
            return self._parse_pdf
        if suffix in {".doc", ".docx", ".pptx"}:
            return self._document_adapter
        return self._parse_text

    def _parse_delimited(self, path: Path, limits: InspectionLimits) -> ParserResult:
        raw = _read_prefix(path, limits.max_parse_bytes)
        text, encoding = _decode_text(raw)
        default = "\t" if path.suffix.lower() == ".tsv" else ","
        try:
            delimiter = csv.Sniffer().sniff(text[: limits.max_sniff_bytes]).delimiter
        except csv.Error:
            delimiter = default
        rows = []
        truncated = len(raw) < path.stat().st_size
        reader = csv.reader(io.StringIO(text), delimiter=delimiter)
        for index, row in enumerate(reader):
            # The header row rides for free: max_rows counts data rows only.
            if index > limits.max_rows:
                truncated = True
                break
            if len(row) > limits.max_columns:
                truncated = True
            rows.append(row[: limits.max_columns])
        return {"encoding": encoding, "delimiter": delimiter, "rows": rows}, truncated

    def _parse_json(self, path: Path, limits: InspectionLimits) -> ParserResult:
        raw = _read_prefix(path, limits.max_parse_bytes)
        text, encoding = _decode_text(raw)
        if len(raw) < path.stat().st_size:
            raise _InspectionError("PREVIEW_TOO_LARGE", "JSON exceeds the input limit.")
        if path.suffix.lower() == ".jsonl":
            values = []
            truncated = False
            for index, line in enumerate(text.splitlines()):
                if not line.strip():
                    continue
                if index >= limits.max_rows:
                    truncated = True
                    break
                values.append(json.loads(line))
        else:
            value = json.loads(text)
            values = value if isinstance(value, list) else [value]
            truncated = len(values) > limits.max_rows
            values = values[: limits.max_rows]
        columns = []
        for value in values:
            if isinstance(value, dict):
                for key in value:
                    if key not in columns:
                        columns.append(str(key))
        if len(columns) > limits.max_columns:
            truncated = True
        columns = columns[: limits.max_columns]
        rows = []
        for value in values:
            if isinstance(value, dict):
                rows.append([value.get(column) for column in columns])
            else:
                rows.append([value])
        return {"encoding": encoding, "columns": columns, "rows": rows}, truncated

    def _parse_text(self, path: Path, limits: InspectionLimits) -> ParserResult:
        raw = _read_prefix(path, limits.max_text_bytes + 4)
        text, encoding = _decode_text(raw)
        text = _truncate_utf8(text, limits.max_text_bytes)
        return {
            "encoding": encoding,
            "text": text,
        }, len(raw) > limits.max_text_bytes or path.stat().st_size > len(raw)

    def _parse_xlsx(self, path: Path, limits: InspectionLimits) -> ParserResult:
        _validate_zip_bounds(path, limits)
        openpyxl = self._require("openpyxl", "xlsx")
        workbook = openpyxl.load_workbook(
            path, read_only=True, data_only=True, keep_links=False
        )
        sheets = []
        truncated = len(workbook.sheetnames) > limits.max_sheets
        try:
            for worksheet in list(workbook.worksheets)[: limits.max_sheets]:
                rows = []
                for index, row in enumerate(worksheet.iter_rows(values_only=True)):
                    # Header rides for free: max_rows counts data rows only.
                    if index > limits.max_rows:
                        truncated = True
                        break
                    values = list(row)
                    if len(values) > limits.max_columns:
                        truncated = True
                    rows.append(values[: limits.max_columns])
                sheets.append({"name": worksheet.title, "rows": rows})
        finally:
            workbook.close()
        return {"sheets": sheets}, truncated

    def _parse_xls(self, path: Path, limits: InspectionLimits) -> ParserResult:
        xlrd = self._require("xlrd", "xls")
        workbook = xlrd.open_workbook(path, on_demand=True)
        sheets = []
        truncated = workbook.nsheets > limits.max_sheets
        try:
            for worksheet in workbook.sheets()[: limits.max_sheets]:
                rows = []
                # Header rides for free: max_rows counts data rows only.
                for row_index in range(min(worksheet.nrows, limits.max_rows + 1)):
                    row = worksheet.row_values(row_index)
                    rows.append(row[: limits.max_columns])
                truncated |= (
                    worksheet.nrows > limits.max_rows + 1
                    or worksheet.ncols > limits.max_columns
                )
                sheets.append({"name": worksheet.name, "rows": rows})
        finally:
            workbook.release_resources()
        return {"sheets": sheets}, truncated

    def _parse_parquet(self, path: Path, limits: InspectionLimits) -> ParserResult:
        parquet = self._require("pyarrow.parquet", "parquet")
        source = parquet.ParquetFile(path)
        columns = source.schema.names[: limits.max_columns]
        batches = source.iter_batches(
            batch_size=limits.max_rows, columns=columns, use_threads=False
        )
        batch = next(batches, None)
        rows = (
            [] if batch is None else [list(row.values()) for row in batch.to_pylist()]
        )
        truncated = (
            source.metadata.num_rows > limits.max_rows
            or len(source.schema.names) > limits.max_columns
        )
        return {"columns": columns, "rows": rows}, truncated

    def _parse_pdf(self, path: Path, limits: InspectionLimits) -> ParserResult:
        pypdf = self._require("pypdf", "pdf")
        reader = pypdf.PdfReader(path, strict=True)
        pages = []
        remaining = limits.max_text_bytes
        truncated = len(reader.pages) > limits.max_pages
        for index, page in enumerate(reader.pages[: limits.max_pages]):
            text = page.extract_text() or ""
            text = _truncate_utf8(text, remaining)
            remaining -= len(text.encode("utf-8"))
            pages.append({"page": index + 1, "text": text})
            if remaining <= 0:
                truncated = True
                break
        return {"page_count": len(reader.pages), "pages": pages}, truncated

    def _parse_document(self, path: Path, limits: InspectionLimits) -> ParserResult:
        suffix = path.suffix.lower()
        if suffix == ".doc":
            raise _InspectionError(
                "PARSER_UNAVAILABLE", "Parser for doc is unavailable."
            )
        _validate_zip_bounds(path, limits)
        extra_slides = False
        if suffix == ".docx":
            names = ("word/document.xml",)
            tags = {"{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t"}
        else:
            with zipfile.ZipFile(path) as archive:
                slide_names = [
                    name
                    for name in archive.namelist()
                    if name.startswith("ppt/slides/slide") and name.endswith(".xml")
                ]
            slide_names.sort(
                key=lambda name: int(
                    name.rsplit("slide", 1)[1].split(".")[0]
                    if name.rsplit("slide", 1)[1].split(".")[0].isdigit()
                    else 0
                )
            )
            names = tuple(slide_names[: limits.max_pages])
            extra_slides = len(slide_names) > limits.max_pages
            tags = {"{http://schemas.openxmlformats.org/drawingml/2006/main}t"}
        chunks = []
        used = 0
        nodes = 0
        truncated = extra_slides
        with zipfile.ZipFile(path) as archive:
            for name in names:
                with archive.open(name) as stream:
                    iterator = ElementTree.iterparse(stream, events=("end",))
                    for _, node in iterator:
                        nodes += 1
                        if nodes > limits.max_xml_nodes:
                            return {"text": "\n".join(chunks)}, True
                        if node.tag in tags and node.text:
                            text = _truncate_utf8(
                                node.text, limits.max_text_bytes - used
                            )
                            chunks.append(text)
                            used += len(text.encode("utf-8"))
                            if used >= limits.max_text_bytes:
                                return {"text": "\n".join(chunks)}, True
                        node.clear()
        return {"text": "\n".join(chunks)}, truncated

    def _require(self, module_name: str, format_name: str) -> Any:
        module = self._optional_import(module_name)
        if module is None:
            raise _InspectionError(
                "PARSER_UNAVAILABLE", f"Parser for {format_name} is unavailable."
            )
        return module

    @staticmethod
    def _failure(kind: str, media_type: str, code: str) -> InspectionResult:
        messages = {
            "CORRUPT_FILE": "The file could not be parsed safely.",
            "INSPECTION_TIMEOUT": "File preview timed out.",
            "INTERNAL_PREVIEW_VIOLATION": "The preview contained internal metadata.",
            "UNSUPPORTED_TYPE": "The file type is not supported.",
            "INSPECTION_BUSY": "Inspection backlog is full; retry later.",
        }
        return InspectionResult(
            kind=kind,
            media_type=media_type,
            status=SessionFileStatus.PREVIEW_FAILED,
            preview={},
            truncated=False,
            error_code=code,
            error_message=messages[code],
        )


def _optional_import(module_name: str) -> Optional[Any]:
    try:
        return importlib.import_module(module_name)
    except ImportError:
        return None


def _inspect_builtin(
    path: Path,
    declared_media_type: Optional[str],
    limits: InspectionLimits,
) -> InspectionResult:
    return SessionFileInspector(limits)._inspect_core(path, declared_media_type)


def _apply_resource_limits(limits: InspectionLimits) -> None:
    """Best-effort per-worker guardrails; ignored when unavailable."""
    try:
        import resource
    except ImportError:
        return
    try:
        resource.setrlimit(resource.RLIMIT_NOFILE, (limits.max_open_files,) * 2)
    except (ValueError, OSError):
        pass
    try:
        cpu_seconds = int(limits.timeout_seconds) + 5
        resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds))
    except (ValueError, OSError):
        pass
    try:
        # Cap address space generously above the parse input cap; platforms
        # that cannot enforce it (e.g. some macOS paths) are skipped silently.
        address_space = max(limits.max_parse_bytes * 32, 512 * 1024 * 1024)
        resource.setrlimit(resource.RLIMIT_AS, (address_space, address_space))
    except (ValueError, OSError):
        pass


def _process_worker(
    output: Any,
    target: Callable[..., Any],
    args: Tuple[Any, ...],
    limits: Optional[InspectionLimits],
) -> None:
    if limits is not None:
        _apply_resource_limits(limits)
    try:
        output.send((True, target(*args)))
    except BaseException as error:
        output.send((False, error))
    finally:
        output.close()


def _run_isolated(
    target: Callable[..., Any],
    args: Tuple[Any, ...],
    timeout_seconds: float,
    limits: Optional[InspectionLimits] = None,
) -> Tuple[bool, Any]:
    """Run picklable built-in work in a process that can be forcibly stopped."""
    context = multiprocessing.get_context("spawn")
    output, child_output = context.Pipe(duplex=False)
    process = context.Process(
        target=_process_worker, args=(child_output, target, args, limits)
    )
    process.start()
    child_output.close()

    # Drain the pipe concurrently: large results must not block the worker
    # while the parent is joining (capacity is smaller than max_preview_bytes).
    received: list = []
    received_error: list = []

    def _drain() -> None:
        try:
            received.append(output.recv())
        except EOFError as error:  # child crashed / exited without result
            received_error.append(error)
        except BaseException as error:  # unpicklable error objects, etc.
            received_error.append(error)
        finally:
            output.close()

    drainer = threading.Thread(
        target=_drain, name="session-file-pipe-drain", daemon=True
    )
    drainer.start()
    process.join(timeout_seconds)
    if process.is_alive():
        process.terminate()
        process.join(0.2)
        if process.is_alive():
            process.kill()
            process.join(0.2)
        if process.is_alive():
            raise RuntimeError("Inspection worker did not terminate.")
        return False, process.pid
    process.join()
    drainer.join(timeout=1.0)
    if received_error:
        raise RuntimeError("Inspection worker exited without a result.")
    if not received:
        raise RuntimeError("Inspection worker exited without a result.")
    succeeded, value = received[0]
    if not succeeded:
        raise value
    return True, value


def _pid_exists(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


def _run_trusted_thread(
    target: Callable[..., Any],
    args: Tuple[Any, ...],
    timeout_seconds: float,
    slot: threading.BoundedSemaphore,
) -> Tuple[bool, Any]:
    """Run an injected extension without requiring it to be picklable.

    Trusted extensions cannot be killed safely. Their slot remains held until the
    thread exits, preventing timed-out extensions from exceeding max_concurrency.
    """
    output: queue.Queue = queue.Queue(maxsize=1)

    def run() -> None:
        try:
            output.put((True, target(*args)))
        except BaseException as error:
            output.put((False, error))
        finally:
            slot.release()

    thread = threading.Thread(
        target=run, name="session-file-inspector-extension", daemon=True
    )
    thread.start()
    try:
        succeeded, value = output.get(timeout=timeout_seconds)
    except queue.Empty:
        return False, None
    if not succeeded:
        raise value
    return True, value


def _result_type(path: Path) -> Tuple[str, str]:
    type_info = _TYPE_INFO.get(path.suffix.lower())
    if type_info is None:
        return "binary", "application/octet-stream"
    return type_info[0], type_info[1]


def _read_prefix(path: Path, limit: int) -> bytes:
    with path.open("rb") as stream:
        return stream.read(limit)


def _looks_like_text(data: bytes) -> bool:
    if not data:
        return True
    if b"\x00" in data:
        return False
    control = sum(byte < 9 or 13 < byte < 32 for byte in data)
    return control / len(data) < 0.05


def _decode_text(data: bytes) -> Tuple[str, str]:
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return data.decode("utf-16"), "utf-16"
    try:
        return data.decode("utf-8-sig"), "utf-8"
    except UnicodeDecodeError:
        return data.decode("cp1252"), "cp1252"


def _validate_zip_bounds(path: Path, limits: InspectionLimits) -> None:
    try:
        with zipfile.ZipFile(path) as archive:
            infos = archive.infolist()
            total = sum(info.file_size for info in infos)
            if (
                len(infos) > limits.max_archive_entries
                or total > limits.max_archive_uncompressed_bytes
                or any(
                    info.file_size > limits.max_archive_entry_bytes
                    or (
                        info.file_size > 0
                        and info.file_size / max(info.compress_size, 1)
                        > limits.max_compression_ratio
                    )
                    for info in infos
                )
            ):
                raise _InspectionError(
                    "PREVIEW_TOO_LARGE", "Document archive exceeds preview limits."
                )
    except zipfile.BadZipFile as error:
        raise _InspectionError(
            "CORRUPT_FILE", "The file could not be parsed safely."
        ) from error


def _validate_ooxml_type(path: Path, suffix: str) -> None:
    required = {
        ".xlsx": "xl/workbook.xml",
        ".docx": "word/document.xml",
        ".pptx": "ppt/presentation.xml",
    }
    try:
        with zipfile.ZipFile(path) as archive:
            names = set(archive.namelist())
    except zipfile.BadZipFile as error:
        raise _InspectionError(
            "TYPE_MISMATCH", "File signature does not match."
        ) from error
    valid = "[Content_Types].xml" in names and required[suffix] in names
    if suffix == ".pptx":
        valid = valid and any(
            re.fullmatch(r"ppt/slides/slide\d+\.xml", name) for name in names
        )
    if not valid:
        raise _InspectionError("TYPE_MISMATCH", "OOXML package type does not match.")


def _truncate_utf8(value: str, max_bytes: int) -> str:
    if max_bytes <= 0:
        return ""
    encoded = value.encode("utf-8")
    if len(encoded) <= max_bytes:
        return value
    return encoded[:max_bytes].decode("utf-8", errors="ignore")


def _bound_preview(preview: Dict[str, Any], max_bytes: int) -> ParserResult:
    bounded = json.loads(json.dumps(preview, ensure_ascii=False, default=str))
    truncated = False
    collection_keys = ("rows", "pages", "sheets")
    while _serialized_size(bounded) > max_bytes:
        previous_size = _serialized_size(bounded)
        candidates = [
            value
            for key in collection_keys
            if isinstance((value := bounded.get(key)), list) and value
        ]
        for sheet in bounded.get("sheets", []):
            if isinstance(sheet, dict) and sheet.get("rows"):
                candidates.append(sheet["rows"])
        if candidates:
            max(candidates, key=len).pop()
            truncated = True
        else:
            strings = list(_string_locations(bounded))
            if not strings:
                raise _InspectionError(
                    "PREVIEW_TOO_LARGE",
                    "File exceeds the bounded preview output limit.",
                )
            parent, key, value = max(
                strings, key=lambda item: len(item[2].encode("utf-8"))
            )
            encoded_length = len(value.encode("utf-8"))
            if encoded_length <= 1:
                parent[key] = ""
            else:
                parent[key] = _truncate_utf8(value, encoded_length // 2)
            truncated = True
        if _serialized_size(bounded) >= previous_size:
            raise _InspectionError(
                "PREVIEW_TOO_LARGE",
                "File exceeds the bounded preview output limit.",
            )
    return bounded, truncated


def _serialized_size(value: Any) -> int:
    return len(json.dumps(value, ensure_ascii=False).encode("utf-8"))


_SENSITIVE_PREVIEW_KEYS = {
    "path",
    "source",
    "storageuri",
    "storagepath",
    "filepath",
}


def _validate_preview(value: Any) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            normalized = re.sub(r"[^a-z0-9]", "", str(key).lower())
            if normalized in _SENSITIVE_PREVIEW_KEYS:
                raise _InspectionError(
                    "INTERNAL_PREVIEW_VIOLATION",
                    "The preview contained internal metadata.",
                )
            _validate_preview(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            _validate_preview(child)


def _string_locations(value: Any):
    if isinstance(value, dict):
        for key, child in value.items():
            if isinstance(child, str):
                yield value, key, child
            else:
                yield from _string_locations(child)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            if isinstance(child, str):
                yield value, index, child
            else:
                yield from _string_locations(child)


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return _FrozenDict({key: _freeze(child) for key, child in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(child) for child in value)
    return value
