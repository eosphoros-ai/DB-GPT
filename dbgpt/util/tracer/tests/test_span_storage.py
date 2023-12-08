import os
import pytest
import asyncio
import json
import tempfile
import time
from unittest.mock import patch
from datetime import datetime, timedelta

from dbgpt.util.tracer import (
    SpanStorage,
    FileSpanStorage,
    Span,
    SpanType,
    SpanStorageContainer,
)


@pytest.fixture
def storage(request):
    if not request or not hasattr(request, "param"):
        file_does_not_exist = False
    else:
        file_does_not_exist = request.param.get("file_does_not_exist", False)

    if file_does_not_exist:
        with tempfile.TemporaryDirectory() as tmp_dir:
            filename = os.path.join(tmp_dir, "non_existent_file.jsonl")
            storage_instance = FileSpanStorage(filename)
            yield storage_instance
    else:
        with tempfile.NamedTemporaryFile(delete=True) as tmp_file:
            filename = tmp_file.name
            storage_instance = FileSpanStorage(filename)
            yield storage_instance


@pytest.fixture
def storage_container(request):
    if not request or not hasattr(request, "param"):
        batch_size = 10
        flush_interval = 10
    else:
        batch_size = request.param.get("batch_size", 10)
        flush_interval = request.param.get("flush_interval", 10)
    storage_container = SpanStorageContainer(
        batch_size=batch_size, flush_interval=flush_interval
    )
    yield storage_container


def read_spans_from_file(filename):
    with open(filename, "r") as f:
        return [json.loads(line) for line in f.readlines()]


def test_write_span(storage: SpanStorage):
    span = Span("1", "a", SpanType.BASE, "b", "op1")
    storage.append_span(span)
    time.sleep(0.1)

    spans_in_file = read_spans_from_file(storage.filename)
    assert len(spans_in_file) == 1
    assert spans_in_file[0]["trace_id"] == "1"


def test_incremental_write(storage: SpanStorage):
    span1 = Span("1", "a", SpanType.BASE, "b", "op1")
    span2 = Span("2", "c", SpanType.BASE, "d", "op2")

    storage.append_span(span1)
    storage.append_span(span2)
    time.sleep(0.1)

    spans_in_file = read_spans_from_file(storage.filename)
    assert len(spans_in_file) == 2


def test_sync_and_async_append(storage: SpanStorage):
    span = Span("1", "a", SpanType.BASE, "b", "op1")

    storage.append_span(span)

    async def async_append():
        storage.append_span(span)

    asyncio.run(async_append())

    time.sleep(0.1)
    spans_in_file = read_spans_from_file(storage.filename)
    assert len(spans_in_file) == 2


@pytest.mark.parametrize("storage", [{"file_does_not_exist": True}], indirect=True)
def test_non_existent_file(storage: SpanStorage):
    span = Span("1", "a", SpanType.BASE, "b", "op1")
    span2 = Span("2", "c", SpanType.BASE, "d", "op2")
    storage.append_span(span)
    time.sleep(0.1)

    spans_in_file = read_spans_from_file(storage.filename)
    assert len(spans_in_file) == 1

    storage.append_span(span2)
    time.sleep(0.1)
    spans_in_file = read_spans_from_file(storage.filename)
    assert len(spans_in_file) == 2
    assert spans_in_file[0]["trace_id"] == "1"
    assert spans_in_file[1]["trace_id"] == "2"


@pytest.mark.parametrize("storage", [{"file_does_not_exist": True}], indirect=True)
def test_log_rollover(storage: SpanStorage):
    # mock start date
    mock_start_date = datetime(2023, 10, 18, 23, 59)

    with patch("datetime.datetime") as mock_datetime:
        mock_datetime.now.return_value = mock_start_date

        span1 = Span("1", "a", SpanType.BASE, "b", "op1")
        storage.append_span(span1)
        time.sleep(0.1)

        # mock new day
        mock_datetime.now.return_value = mock_start_date + timedelta(minutes=1)

        span2 = Span("2", "c", SpanType.BASE, "d", "op2")
        storage.append_span(span2)
        time.sleep(0.1)

    # origin filename need exists
    assert os.path.exists(storage.filename)

    # get roll over filename
    dated_filename = os.path.join(
        os.path.dirname(storage.filename),
        f"{os.path.basename(storage.filename).split('.')[0]}_2023-10-18.jsonl",
    )

    assert os.path.exists(dated_filename)

    # check origin filename just include the second span
    spans_in_original_file = read_spans_from_file(storage.filename)
    assert len(spans_in_original_file) == 1
    assert spans_in_original_file[0]["trace_id"] == "2"

    # check the roll over filename just include the first span
    spans_in_dated_file = read_spans_from_file(dated_filename)
    assert len(spans_in_dated_file) == 1
    assert spans_in_dated_file[0]["trace_id"] == "1"


@pytest.mark.asyncio
@pytest.mark.parametrize("storage_container", [{"batch_size": 5}], indirect=True)
async def test_container_flush_policy(
    storage_container: SpanStorageContainer, storage: FileSpanStorage
):
    storage_container.append_storage(storage)
    span = Span("1", "a", SpanType.BASE, "b", "op1")

    filename = storage.filename

    for _ in range(storage_container.batch_size - 1):
        storage_container.append_span(span)

    spans_in_file = read_spans_from_file(filename)
    assert len(spans_in_file) == 0

    # Trigger batch write
    storage_container.append_span(span)
    await asyncio.sleep(0.1)

    spans_in_file = read_spans_from_file(filename)
    assert len(spans_in_file) == storage_container.batch_size
