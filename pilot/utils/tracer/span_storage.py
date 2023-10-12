import os
import json
import time
import threading
import queue
import logging

from pilot.component import SystemApp
from pilot.utils.tracer.base import Span, SpanStorage


logger = logging.getLogger(__name__)


class MemorySpanStorage(SpanStorage):
    def __init__(self, system_app: SystemApp | None = None):
        super().__init__(system_app)
        self.spans = []
        self._lock = threading.Lock()

    def append_span(self, span: Span):
        with self._lock:
            self.spans.append(span)


class FileSpanStorage(SpanStorage):
    def __init__(self, filename: str, batch_size=10, flush_interval=10):
        super().__init__()
        self.filename = filename
        self.queue = queue.Queue()
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self.last_flush_time = time.time()
        self.flush_signal_queue = queue.Queue()

        if not os.path.exists(filename):
            with open(filename, "w") as _:
                pass
        self.flush_thread = threading.Thread(target=self._flush_to_file, daemon=True)
        self.flush_thread.start()

    def append_span(self, span: Span):
        span_data = span.to_dict()
        logger.debug(f"append span: {span_data}")
        self.queue.put(span_data)

        if self.queue.qsize() >= self.batch_size:
            try:
                self.flush_signal_queue.put_nowait(True)
            except queue.Full:
                pass  # If the signal queue is full, it's okay. The flush thread will handle it.

    def _write_to_file(self):
        spans_to_write = []
        while not self.queue.empty():
            spans_to_write.append(self.queue.get())

        with open(self.filename, "a") as file:
            for span_data in spans_to_write:
                try:
                    file.write(json.dumps(span_data, ensure_ascii=False) + "\n")
                except Exception as e:
                    logger.warning(
                        f"Write span to file failed: {str(e)}, span_data: {span_data}"
                    )

    def _flush_to_file(self):
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
            self._write_to_file()
            self.last_flush_time = time.time()
