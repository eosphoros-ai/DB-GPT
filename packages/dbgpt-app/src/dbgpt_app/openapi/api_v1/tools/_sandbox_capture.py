"""Build self-contained capture helpers for images without DB-GPT installed."""

import inspect
import json
import os
from pathlib import Path

from dbgpt.core.interface.report_capture import (
    normalize_artifact_value,
    restore_artifact_value,
)


class TrackedSQLResults(list):
    """Track reads of complete datasets already materialized by the host."""

    def __init__(self, values: list, trace_path: str):
        super().__init__(restore_artifact_value(values))
        self.trace_path = trace_path
        self.used: set[str] = set()

    def _record(self, value):
        for item in value if isinstance(value, list) else [value]:
            if isinstance(item, dict) and isinstance(item.get("artifact_id"), str):
                if item.get("truncated"):
                    raise ValueError("SQL_RESULT_INCOMPLETE: full snapshot required")
                self.used.add(item["artifact_id"])
        trace = Path(self.trace_path)
        temporary = trace.with_suffix(".pending")
        temporary.write_text(json.dumps(sorted(self.used)), encoding="utf-8")
        os.replace(temporary, trace)
        return value

    def __getitem__(self, index):
        return self._record(super().__getitem__(index))

    def __iter__(self):
        for item in super().__iter__():
            yield self._record(item)

    def copy(self):
        return list(self)

    def __reversed__(self):
        for item in super().__reversed__():
            yield self._record(item)

    def __add__(self, other):
        return list(self) + other

    def __mul__(self, count):
        return list(self) * count

    __rmul__ = __mul__


def capture_helper_source() -> str:
    """Reuse host serialization rules without importing host packages in children.

    The returned source runs in a private module namespace. Only standard-library
    imports are shipped; SQL snapshot URIs must be resolved before execution.
    """
    imports = """
import base64
import json
import math
import os
import uuid
from collections.abc import Mapping
from datetime import date, datetime, time
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any
"""
    return imports + "\n\n".join(
        inspect.getsource(definition)
        for definition in (
            normalize_artifact_value,
            restore_artifact_value,
            TrackedSQLResults,
        )
    )
