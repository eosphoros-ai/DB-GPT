import datetime
import json
import logging
import os
import queue
import threading
import time
from concurrent.futures import Executor, ThreadPoolExecutor
from typing import List, Optional

from dbgpt.component import SystemApp
from dbgpt.util.tracer.base import Span, SpanStorage

logger = logging.getLogger(__name__)


class MemorySpanStorage(SpanStorage):
    def __init__(self, system_app: SystemApp | None = None):
        super().__init__(system_app)
        self.spans = []
        self._lock = threading.Lock()

    def append_span(self, span: Span):
        with self._lock:
            self.spans.append(span)


class SpanStorageContainer(SpanStorage):
    def __init__(
        self,
        system_app: SystemApp | None = None,
        batch_size=10,
        flush_interval=10,
        executor: Executor = None,
    ):
        super().__init__(system_app)
        if not executor:
            executor = ThreadPoolExecutor(thread_name_prefix="trace_storage_sync_")
        self.executor = executor
        self.storages: List[SpanStorage] = []
        self.last_date = (
            datetime.datetime.now().date()
        )  # Store the current date for checking date changes
        self.queue = queue.Queue()
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self.last_flush_time = time.time()
        self.flush_signal_queue = queue.Queue()
        self.flush_thread = threading.Thread(
            target=self._flush_to_storages, daemon=True
        )
        self.flush_thread.start()

    def append_storage(self, storage: SpanStorage):
        """Append sotrage to container

        Args:
            storage ([`SpanStorage`]): The storage to be append to current container
        """
        self.storages.append(storage)

    def append_span(self, span: Span):
        self.queue.put(span)
        if self.queue.qsize() >= self.batch_size:
            try:
                self.flush_signal_queue.put_nowait(True)
            except queue.Full:
                pass  # If the signal queue is full, it's okay. The flush thread will handle it.

    def _flush_to_storages(self):
        while True:
            interval = time.time() - self.last_flush_time
            if interval < self.flush_interval:
                try:
                    self.flush_signal_queue.get(
                        block=True, timeout=self.flush_interval - interval
                    )
                except Exception:
                    # Timeout
                    pass

            spans_to_write = []
            while not self.queue.empty():
                spans_to_write.append(self.queue.get())
            for s in self.storages:

                def append_and_ignore_error(
                    storage: SpanStorage, spans_to_write: List[SpanStorage]
                ):
                    try:
                        storage.append_span_batch(spans_to_write)
                    except Exception as e:
                        logger.warn(
                            f"Append spans to storage {str(storage)} failed: {str(e)}, span_data: {spans_to_write}"
                        )

                self.executor.submit(append_and_ignore_error, s, spans_to_write)
            self.last_flush_time = time.time()


class FileSpanStorage(SpanStorage):
    def __init__(self, filename: str):
        super().__init__()
        self.filename = filename
        # Split filename into prefix and suffix
        self.filename_prefix, self.filename_suffix = os.path.splitext(filename)
        if not self.filename_suffix:
            self.filename_suffix = ".log"
        self.last_date = (
            datetime.datetime.now().date()
        )  # Store the current date for checking date changes
        self.queue = queue.Queue()

        if not os.path.exists(filename):
            # New file if not exist
            os.makedirs(os.path.dirname(filename), exist_ok=True)
            with open(filename, "a"):
                pass

    def append_span(self, span: Span):
        self._write_to_file([span])

    def append_span_batch(self, spans: List[Span]):
        self._write_to_file(spans)

    def _get_dated_filename(self, date: datetime.date) -> str:
        """Return the filename based on a specific date."""
        date_str = date.strftime("%Y-%m-%d")
        return f"{self.filename_prefix}_{date_str}{self.filename_suffix}"

    def _roll_over_if_needed(self):
        """Checks if a day has changed since the last write, and if so, renames the current file."""
        current_date = datetime.datetime.now().date()
        if current_date != self.last_date:
            if os.path.exists(self.filename):
                os.rename(self.filename, self._get_dated_filename(self.last_date))
            self.last_date = current_date

    def _write_to_file(self, spans: List[Span]):
        self._roll_over_if_needed()

        with open(self.filename, "a", encoding="utf8") as file:
            for span in spans:
                span_data = span.to_dict()
                try:
                    file.write(json.dumps(span_data, ensure_ascii=False) + "\n")
                except Exception as e:
                    logger.warning(
                        f"Write span to file failed: {str(e)}, span_data: {span_data}"
                    )
