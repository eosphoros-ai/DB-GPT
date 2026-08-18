"""Tests for bounded session-file inspection."""

import asyncio
import json
import multiprocessing
import pickle
import threading
import time
import zipfile
from dataclasses import FrozenInstanceError

import pytest

from dbgpt_serve.session_file import inspector as inspector_module
from dbgpt_serve.session_file.domain import SessionFileStatus
from dbgpt_serve.session_file.inspector import (
    InspectionLimits,
    InspectionResult,
    SessionFileInspector,
    _bound_preview,
    _InspectionError,
)


def _write_ooxml(path, parts):
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>',
        )
        for name, content in parts.items():
            archive.writestr(name, content)


def test_inspection_limits_and_result_are_immutable():
    limits = InspectionLimits()
    result = InspectionResult(
        kind="document",
        media_type="text/plain",
        status=SessionFileStatus.READY,
        preview={"text": "safe"},
        truncated=False,
    )

    with pytest.raises(FrozenInstanceError):
        limits.max_rows = 1
    with pytest.raises(FrozenInstanceError):
        result.kind = "table"
    with pytest.raises(TypeError):
        result.preview["path"] = "/private/source.txt"
    assert pickle.loads(pickle.dumps(result)) == result


def test_csv_preview_caps_rows_columns_and_serialized_bytes(tmp_path):
    path = tmp_path / "large.csv"
    path.write_text(
        "name;value;ignored\n" + "long-value;2;secret\n" * 20,
        encoding="utf-8",
    )
    limits = InspectionLimits(max_rows=3, max_columns=2, max_preview_bytes=180)

    result = SessionFileInspector(limits).inspect(path, "text/csv")

    assert result.status is SessionFileStatus.READY
    assert result.kind == "table"
    assert result.media_type == "text/csv"
    assert result.preview["delimiter"] == ";"
    assert result.preview["encoding"] == "utf-8"
    # max_rows counts data rows only; the header row rides for free.
    assert len(result.preview["rows"]) == 4
    assert all(len(row) <= 2 for row in result.preview["rows"])
    assert len(json.dumps(result.preview, ensure_ascii=False).encode("utf-8")) <= 180
    assert result.truncated is True


def test_csv_detects_bounded_non_utf8_encoding(tmp_path):
    path = tmp_path / "latin.csv"
    path.write_bytes("city,value\nMontréal,1\n".encode("cp1252"))

    result = SessionFileInspector().inspect(path)

    assert result.status is SessionFileStatus.READY
    assert result.preview["rows"][1][0] == "Montréal"
    assert result.preview["encoding"] in {"cp1252", "latin-1"}


def test_json_and_jsonl_are_bounded(tmp_path):
    json_path = tmp_path / "items.json"
    json_path.write_text(json.dumps([{"a": i, "b": i, "c": i} for i in range(8)]))
    jsonl_path = tmp_path / "items.jsonl"
    jsonl_path.write_text("".join(json.dumps({"a": i}) + "\n" for i in range(8)))
    inspector = SessionFileInspector(InspectionLimits(max_rows=2, max_columns=2))

    json_result = inspector.inspect(json_path)
    jsonl_result = inspector.inspect(jsonl_path)

    assert len(json_result.preview["rows"]) == 2
    assert len(json_result.preview["columns"]) == 2
    assert json_result.truncated is True
    assert len(jsonl_result.preview["rows"]) == 2
    assert jsonl_result.truncated is True


def test_text_preview_caps_input_and_output_bytes(tmp_path):
    path = tmp_path / "notes.md"
    path.write_text("é" * 1_000)

    result = SessionFileInspector(
        InspectionLimits(max_sniff_bytes=128, max_text_bytes=31, max_preview_bytes=100)
    ).inspect(path)

    assert result.status is SessionFileStatus.READY
    assert len(result.preview["text"].encode("utf-8")) <= 31
    assert len(json.dumps(result.preview, ensure_ascii=False).encode("utf-8")) <= 100
    assert result.truncated is True


def test_xlsx_preview_caps_sheets_rows_and_columns(tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    path = tmp_path / "book.xlsx"
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.append(["a", "b", "c"])
    sheet.append([1, 2, 3])
    sheet.append([4, 5, 6])
    workbook.create_sheet("extra").append(["hidden by cap"])
    workbook.save(path)

    result = SessionFileInspector(
        InspectionLimits(max_sheets=1, max_rows=2, max_columns=2)
    ).inspect(path)

    assert result.status is SessionFileStatus.READY
    assert len(result.preview["sheets"]) == 1
    # max_rows counts data rows only; the header row rides for free.
    assert len(result.preview["sheets"][0]["rows"]) == 3
    assert len(result.preview["sheets"][0]["rows"][0]) == 2
    assert result.truncated is True


def test_pdf_preview_caps_pages_and_text(tmp_path):
    pypdf = pytest.importorskip("pypdf")
    path = tmp_path / "pages.pdf"
    writer = pypdf.PdfWriter()
    for _ in range(3):
        writer.add_blank_page(width=72, height=72)
    with path.open("wb") as stream:
        writer.write(stream)

    result = SessionFileInspector(
        InspectionLimits(max_pages=2, max_text_bytes=16)
    ).inspect(path)

    assert result.status is SessionFileStatus.READY
    assert result.preview["page_count"] == 3
    assert len(result.preview["pages"]) == 2
    assert result.truncated is True


@pytest.mark.parametrize(
    ("suffix", "signature", "expected_media_type"),
    [
        (".doc", b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1payload", "application/msword"),
        (
            ".docx",
            b"PK\x03\x04payload",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ),
        (
            ".pptx",
            b"PK\x03\x04payload",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        ),
    ],
)
def test_document_formats_dispatch_through_bounded_adapter(
    tmp_path, suffix, signature, expected_media_type
):
    path = tmp_path / f"document{suffix}"
    if suffix == ".docx":
        _write_ooxml(path, {"word/document.xml": "<document/>"})
    elif suffix == ".pptx":
        _write_ooxml(
            path,
            {
                "ppt/presentation.xml": "<presentation/>",
                "ppt/slides/slide1.xml": "<slide/>",
            },
        )
    else:
        path.write_bytes(signature)
    calls = []

    def adapter(adapter_path, limits):
        calls.append((adapter_path.name, limits.max_text_bytes))
        return {"text": "adapter text", "external_refs_followed": False}, False

    result = SessionFileInspector(document_adapter=adapter).inspect(path)

    assert result.status is SessionFileStatus.READY
    assert result.kind == "document"
    assert result.media_type == expected_media_type
    assert result.preview["text"] == "adapter text"
    assert calls == [(path.name, InspectionLimits().max_text_bytes)]


def test_missing_optional_parser_returns_deterministic_preview_failure(tmp_path):
    path = tmp_path / "legacy.xls"
    path.write_bytes(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1payload")

    result = SessionFileInspector(optional_import=lambda name: None).inspect(path)

    assert result.status is SessionFileStatus.PREVIEW_FAILED
    assert result.kind == "table"
    assert result.error_code == "PARSER_UNAVAILABLE"
    assert "xls" in result.error_message.lower()
    assert str(path) not in result.error_message


@pytest.mark.parametrize(
    ("name", "content", "declared_media_type"),
    [
        ("fake.pdf", b"not a pdf", "application/pdf"),
        ("fake.csv", b"a,b\n1,2\n", "application/pdf"),
        ("fake.xlsx", b"%PDF-1.7\n", None),
    ],
)
def test_rejects_extension_signature_or_media_mismatch(
    tmp_path, name, content, declared_media_type
):
    path = tmp_path / name
    path.write_bytes(content)

    result = SessionFileInspector().inspect(path, declared_media_type)

    assert result.status is SessionFileStatus.PREVIEW_FAILED
    assert result.error_code == "TYPE_MISMATCH"
    assert str(path) not in (result.error_message or "")


def test_corrupt_allowlisted_file_returns_safe_failure(tmp_path):
    path = tmp_path / "corrupt.json"
    path.write_text('{"secret_path": "/srv/private/data", broken')

    result = SessionFileInspector().inspect(path)

    assert result.status is SessionFileStatus.PREVIEW_FAILED
    assert result.error_code == "CORRUPT_FILE"
    assert result.preview == {}
    assert str(path) not in result.error_message
    assert "/srv/private/data" not in result.error_message


def test_unsupported_binary_is_rejected_without_dispatch(tmp_path):
    path = tmp_path / "payload.bin"
    path.write_bytes(b"\x00\x01\x02\x03" * 100)

    result = SessionFileInspector().inspect(path)

    assert result.status is SessionFileStatus.PREVIEW_FAILED
    assert result.kind == "binary"
    assert result.error_code == "UNSUPPORTED_TYPE"
    assert result.preview == {}


@pytest.mark.asyncio
async def test_async_inspection_times_out_deterministically(tmp_path):
    path = tmp_path / "blocked.txt"
    path.write_text("safe")
    entered = threading.Event()
    release = threading.Event()

    def blocked_parser(parser_path, limits):
        entered.set()
        release.wait(timeout=1)
        return {"text": "too late"}, False

    inspector = SessionFileInspector(
        InspectionLimits(timeout_seconds=0.01), parsers={".txt": blocked_parser}
    )
    try:
        result = await inspector.inspect_async(path)
    finally:
        release.set()
        await asyncio.sleep(0)

    assert entered.is_set()
    assert result.status is SessionFileStatus.PREVIEW_FAILED
    assert result.error_code == "INSPECTION_TIMEOUT"
    assert result.preview == {}


def test_isolated_timeout_terminates_worker_and_allows_followup(tmp_path):
    completed, pid = inspector_module._run_isolated(
        time.sleep, (5,), timeout_seconds=0.2
    )

    assert completed is False
    assert not inspector_module._pid_exists(pid)
    assert all(child.pid != pid for child in multiprocessing.active_children())

    path = tmp_path / "followup.txt"
    path.write_text("ok")
    result = SessionFileInspector().inspect(path)
    assert result.status is SessionFileStatus.READY
    assert result.preview["text"] == "ok"


def test_isolated_worker_returns_preview_larger_than_pipe_buffer(tmp_path):
    path = tmp_path / "large-preview.txt"
    path.write_text("x" * 32_000)

    result = SessionFileInspector(
        InspectionLimits(max_text_bytes=40_000, timeout_seconds=1)
    ).inspect(path)

    assert result.status is SessionFileStatus.READY
    assert len(result.preview["text"]) == 32_000


def test_unrelated_injected_parser_does_not_degrade_builtin_isolation(
    tmp_path, monkeypatch
):
    path = tmp_path / "safe.csv"
    path.write_text("name,value\nsafe,1\n")
    inspector = SessionFileInspector(
        parsers={".txt": lambda path, limits: ({"text": "trusted"}, False)}
    )

    def reject_thread_fallback(*args, **kwargs):
        raise AssertionError("built-in parser ran in trusted extension thread")

    monkeypatch.setattr(inspector_module, "_run_trusted_thread", reject_thread_fallback)

    result = inspector.inspect(path)

    assert result.status is SessionFileStatus.READY
    assert result.preview["rows"][1] == ("safe", "1")


@pytest.mark.asyncio
async def test_trusted_parser_keeps_slot_until_timed_out_work_finishes(tmp_path):
    first_path = tmp_path / "first.txt"
    second_path = tmp_path / "second.txt"
    first_path.write_text("first")
    second_path.write_text("second")
    entered = []
    release = threading.Event()

    def parser(path, limits):
        entered.append(path.name)
        if path == first_path:
            release.wait(timeout=2)
        return {"text": path.name}, False

    inspector = SessionFileInspector(
        InspectionLimits(max_concurrency=1, timeout_seconds=0.05),
        parsers={".txt": parser},
    )
    first = await inspector.inspect_async(first_path)
    second_task = asyncio.create_task(inspector.inspect_async(second_path))
    await asyncio.sleep(0.1)

    assert first.error_code == "INSPECTION_TIMEOUT"
    assert entered == ["first.txt"]
    assert not second_task.done()

    release.set()
    second = await second_task
    assert second.status is SessionFileStatus.READY
    assert entered == ["first.txt", "second.txt"]


@pytest.mark.parametrize(
    ("suffix", "parts"),
    [
        (".xlsx", {}),
        (".docx", {"xl/workbook.xml": "<workbook/>"}),
        (".pptx", {"ppt/presentation.xml": "<presentation/>"}),
    ],
)
def test_rejects_empty_or_wrong_ooxml_container(tmp_path, suffix, parts):
    path = tmp_path / f"invalid{suffix}"
    _write_ooxml(path, parts)

    result = SessionFileInspector().inspect(path)

    assert result.status is SessionFileStatus.PREVIEW_FAILED
    assert result.error_code == "TYPE_MISMATCH"


def test_zip_rejects_single_large_entry_and_high_compression_ratio(tmp_path):
    entry_path = tmp_path / "entry.docx"
    ratio_path = tmp_path / "ratio.docx"
    content = "x" * 4096
    _write_ooxml(entry_path, {"word/document.xml": content})
    with zipfile.ZipFile(ratio_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("word/document.xml", content)

    entry_result = SessionFileInspector(
        InspectionLimits(max_archive_entry_bytes=1024)
    ).inspect(entry_path)
    ratio_result = SessionFileInspector(
        InspectionLimits(max_compression_ratio=2)
    ).inspect(ratio_path)

    assert entry_result.error_code == "PREVIEW_TOO_LARGE"
    assert ratio_result.error_code == "PREVIEW_TOO_LARGE"


def test_rejects_sensitive_preview_key_recursively(tmp_path):
    path = tmp_path / "safe.txt"
    path.write_text("safe")

    result = SessionFileInspector(
        parsers={
            ".txt": lambda path, limits: (
                {"nested": [{"Storage_Path": str(path)}]},
                False,
            )
        }
    ).inspect(path)

    assert result.status is SessionFileStatus.PREVIEW_FAILED
    assert result.error_code == "INTERNAL_PREVIEW_VIOLATION"
    assert result.preview == {}


def test_preview_cap_uses_public_json_serialization_with_unicode(tmp_path):
    path = tmp_path / "safe.txt"
    path.write_text("safe")
    inspector = SessionFileInspector(
        InspectionLimits(max_preview_bytes=16),
        parsers={".txt": lambda path, limits: ({"a": "éééé"}, False)},
    )

    result = inspector.inspect(path)
    serialized = json.dumps(result.preview, ensure_ascii=False).encode("utf-8")

    assert result.status is SessionFileStatus.READY
    assert len(serialized) <= 16
    assert json.loads(serialized) == result.preview
    assert result.truncated is True


def test_bound_preview_raises_instead_of_looping_when_limit_unattainable():
    with pytest.raises(_InspectionError) as error:
        _bound_preview({"a": ""}, 1)

    assert error.value.code == "PREVIEW_TOO_LARGE"


def _write_pptx(path, slide_numbers):
    parts = {
        "ppt/presentation.xml": '<?xml version="1.0"?>'
        '<p:presentation xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"/>',
    }
    for number in slide_numbers:
        pptx_ns = "http://schemas.openxmlformats.org/presentationml/2006/main"
        parts[f"ppt/slides/slide{number}.xml"] = (
            '<?xml version="1.0"?>'
            f'<p:sld xmlns:p="{pptx_ns}" '
            'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">'
            f"<a:t>slide {number}</a:t>"
            "</p:sld>"
        )
    _write_ooxml(path, parts)


def test_pptx_slides_are_naturally_ordered_and_truncated(tmp_path):
    path = tmp_path / "deck.pptx"
    _write_pptx(path, [1, 2, 10])

    result = SessionFileInspector(InspectionLimits(max_pages=2)).inspect(path)

    assert result.status is SessionFileStatus.READY
    assert result.preview["text"] == "slide 1\nslide 2"
    assert result.truncated is True


def test_isolated_process_handles_result_larger_than_pipe_buffer(tmp_path):
    path = tmp_path / "large.txt"
    path.write_text("a" * (64 * 1024))

    result = SessionFileInspector(
        InspectionLimits(max_preview_bytes=32 * 1024)
    ).inspect(path)

    assert result.status is SessionFileStatus.READY
    assert result.truncated is True
    assert len(json.dumps(result.preview).encode("utf-8")) <= 32 * 1024


def test_symlink_inputs_are_rejected_safely(tmp_path):
    real = tmp_path / "real.txt"
    real.write_text("safe")
    link = tmp_path / "link.txt"
    link.symlink_to(real)

    result = SessionFileInspector().inspect(link)

    assert result.status is SessionFileStatus.PREVIEW_FAILED
    assert result.error_code == "UNSAFE_FILE_REFERENCE"


def test_inspection_returns_busy_when_slots_are_held(tmp_path):
    path = tmp_path / "busy.txt"
    path.write_text("safe")
    inspector = SessionFileInspector(
        InspectionLimits(max_concurrency=1, queue_timeout_seconds=0.05)
    )
    semaphore = inspector._slots
    semaphore.acquire()
    try:
        result = inspector.inspect(path)
    finally:
        semaphore.release()

    assert result.status is SessionFileStatus.PREVIEW_FAILED
    assert result.error_code == "INSPECTION_BUSY"


@pytest.mark.asyncio
async def test_async_inspection_returns_busy_when_slots_are_held(tmp_path):
    path = tmp_path / "busy.txt"
    path.write_text("safe")
    inspector = SessionFileInspector(
        InspectionLimits(max_concurrency=1, queue_timeout_seconds=0.05)
    )
    semaphore = inspector._slots
    semaphore.acquire()
    try:
        result = await inspector.inspect_async(path)
    finally:
        semaphore.release()

    assert result.status is SessionFileStatus.PREVIEW_FAILED
    assert result.error_code == "INSPECTION_BUSY"


def test_process_worker_applies_limits_before_target(monkeypatch):
    calls = []
    monkeypatch.setattr(
        inspector_module,
        "_apply_resource_limits",
        lambda limits: calls.append(limits),
    )

    class _FakeOutput:
        def __init__(self):
            self.sent = []
            self.closed = False

        def send(self, value):
            self.sent.append(value)

        def close(self):
            self.closed = True

    output = _FakeOutput()
    limits = InspectionLimits()
    inspector_module._process_worker(output, lambda: "done", (), limits)

    assert calls == [limits]
    assert output.sent == [(True, "done")]
    assert output.closed is True


def test_apply_resource_limits_calls_os_guardrails(monkeypatch):
    import sys
    from types import SimpleNamespace

    calls = []
    fake_resource = SimpleNamespace(
        RLIMIT_NOFILE=1,
        RLIMIT_CPU=2,
        RLIMIT_AS=3,
        setrlimit=lambda res, value: calls.append((res, value)),
    )
    monkeypatch.setitem(sys.modules, "resource", fake_resource)
    limits = InspectionLimits()

    inspector_module._apply_resource_limits(limits)

    applied = {res for res, _ in calls}
    assert {1, 2, 3} <= applied
