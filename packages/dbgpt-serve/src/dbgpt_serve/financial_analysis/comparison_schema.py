"""Versioned comparison protocol and deterministic, task-scoped identifiers."""

import hashlib
import json
from decimal import Decimal, InvalidOperation
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

POLICY_VERSION = "paired-disclosure-v1"
FORMULA_VERSION = "decimal-v1"
EXTRACTOR_VERSION = "financial-document-v2"
MAX_DOCUMENTS = 5


class ComparisonConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["peer", "trend"]
    baseline_file_id: str | None = Field(default=None, min_length=1, max_length=64)
    policy_version: Literal["paired-disclosure-v1"] = POLICY_VERSION
    formula_version: Literal["decimal-v1"] = FORMULA_VERSION


class ComparisonRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    file_ids: list[str] = Field(min_length=2, max_length=MAX_DOCUMENTS)
    comparison: ComparisonConfig

    @model_validator(mode="after")
    def validate_members(self):
        if len(set(self.file_ids)) != len(self.file_ids):
            raise ValueError("Duplicate attachment IDs")
        baseline = self.comparison.baseline_file_id
        if baseline and baseline not in self.file_ids:
            raise ValueError("Baseline must be a task member")
        return self


def stable_id(prefix, *parts):
    encoded = json.dumps(parts, ensure_ascii=False, separators=(",", ":"))
    return prefix + "-" + hashlib.sha256(encoded.encode()).hexdigest()[:24]


def fingerprint(file_ids, config):
    # Order is intentional: it determines presentation and the default baseline.
    value = {"mode": "comparison", "file_ids": file_ids, "comparison": config}
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def decimal_value(value):
    """Reject floats rather than importing their rounding into business values."""
    if not isinstance(value, str):
        return None
    try:
        result = Decimal(value)
        return result if result.is_finite() else None
    except InvalidOperation:
        return None


def report_title(report):
    return (
        report["comparison"]["title"]
        if report.get("mode") == "comparison"
        else report["report"]["companyName"] + "财报分析"
    )


def validate_snapshot(report):
    pair = report.get("schemaVersion"), report.get("mode")
    if pair not in {(1, "report"), (2, "comparison")}:
        raise ValueError("Unsupported financial report protocol")
    if pair == (2, "comparison"):
        for fact in report["facts"]:
            if (
                fact["normalizedValue"] is not None
                and decimal_value(fact["normalizedValue"]) is None
            ):
                raise ValueError("Comparison facts require decimal strings")
        for calculation in report["calculations"]:
            if (
                calculation["result"] is not None
                and decimal_value(calculation["result"]) is None
            ):
                raise ValueError("Comparison calculations require decimal strings")
        for key in ("facts", "calculations", "evidence", "documents"):
            ids = [item["id"] for item in report[key]]
            if len(ids) != len(set(ids)):
                raise ValueError("Duplicate comparison identifiers: " + key)
    return report
