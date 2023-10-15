import os
import pytest
import asyncio
import json
import tempfile
import time

from pilot.utils.tracer import SpanStorage, FileSpanStorage, Span, SpanType


@pytest.fixture
def storage(request):
    if not request or not hasattr(request, "param"):
        batch_size = 10
        flush_interval = 10
        file_does_not_exist = False
    else:
        batch_size = request.param.get("batch_size", 10)
        flush_interval = request.param.get("flush_interval", 10)
        file_does_not_exist = request.param.get("file_does_not_exist", False)

    if file_does_not_exist:
        with tempfile.TemporaryDirectory() as tmp_dir:
            filename = os.path.join(tmp_dir, "non_existent_file.jsonl")
            storage_instance = FileSpanStorage(
                filename, batch_size=batch_size, flush_interval=flush_interval
            )
            yield storage_instance
    else:
        with tempfile.NamedTemporaryFile(delete=True) as tmp_file:
            filename = tmp_file.name
            storage_instance = FileSpanStorage(
                filename, batch_size=batch_size, flush_interval=flush_interval
            )
            yield storage_instance


def read_spans_from_file(filename):
    with open(filename, "r") as f:
        return [json.loads(line) for line in f.readlines()]


@pytest.mark.parametrize(
    "storage", [{"batch_size": 1, "flush_interval": 5}], indirect=True
)
def test_write_span(storage: SpanStorage):
    span = Span("1", "a", SpanType.BASE, "b", "op1")
    storage.append_span(span)
    time.sleep(0.1)

    spans_in_file = read_spans_from_file(storage.filename)
    assert len(spans_in_file) == 1
    assert spans_in_file[0]["trace_id"] == "1"


@pytest.mark.parametrize(
    "storage", [{"batch_size": 1, "flush_interval": 5}], indirect=True
)
def test_incremental_write(storage: SpanStorage):
    span1 = Span("1", "a", SpanType.BASE, "b", "op1")
    span2 = Span("2", "c", SpanType.BASE, "d", "op2")

    storage.append_span(span1)
    storage.append_span(span2)
    time.sleep(0.1)

    spans_in_file = read_spans_from_file(storage.filename)
    assert len(spans_in_file) == 2


@pytest.mark.parametrize(
    "storage", [{"batch_size": 2, "flush_interval": 5}], indirect=True
)
def test_sync_and_async_append(storage: SpanStorage):
    span = Span("1", "a", SpanType.BASE, "b", "op1")

    storage.append_span(span)

    async def async_append():
        storage.append_span(span)

    asyncio.run(async_append())

    time.sleep(0.1)
    spans_in_file = read_spans_from_file(storage.filename)
    assert len(spans_in_file) == 2


@pytest.mark.asyncio
async def test_flush_policy(storage: SpanStorage):
    span = Span("1", "a", SpanType.BASE, "b", "op1")

    for _ in range(storage.batch_size - 1):
        storage.append_span(span)

    spans_in_file = read_spans_from_file(storage.filename)
    assert len(spans_in_file) == 0

    # Trigger batch write
    storage.append_span(span)
    await asyncio.sleep(0.1)

    spans_in_file = read_spans_from_file(storage.filename)
    assert len(spans_in_file) == storage.batch_size


@pytest.mark.parametrize(
    "storage", [{"batch_size": 2, "file_does_not_exist": True}], indirect=True
)
def test_non_existent_file(storage: SpanStorage):
    span = Span("1", "a", SpanType.BASE, "b", "op1")
    span2 = Span("2", "c", SpanType.BASE, "d", "op2")
    storage.append_span(span)
    time.sleep(0.1)

    spans_in_file = read_spans_from_file(storage.filename)
    assert len(spans_in_file) == 0

    storage.append_span(span2)
    time.sleep(0.1)
    spans_in_file = read_spans_from_file(storage.filename)
    assert len(spans_in_file) == 2
    assert spans_in_file[0]["trace_id"] == "1"
    assert spans_in_file[1]["trace_id"] == "2"
