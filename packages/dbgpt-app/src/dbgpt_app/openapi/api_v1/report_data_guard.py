"""Validate report HTML against data returned by SQL tools."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from html.parser import HTMLParser
from typing import Any, Iterable


@dataclass
class SqlResult:
    columns: list[str]
    rows: list[list[Any]]
    row_count: int
    sql: str = ""


@dataclass
class ReportDataValidation:
    ok: bool
    untraceable_values: list[str] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)


class _VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._skip_depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag.lower() in {"script", "style", "svg", "canvas"}:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style", "svg", "canvas"} and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self._skip_depth and data.strip():
            self.parts.append(data)


def validate_html_report_data(
    html: str,
    sql_results: Iterable[SqlResult | dict[str, Any]],
) -> ReportDataValidation:
    """Return whether visible report numbers are traceable to SQL results.

    This guard intentionally validates rendered business text, not CSS/layout
    numbers. A value is traceable when it appears in SQL output or is a common
    derived value from the same result set, such as a column sum or percentage.
    """

    normalized_results = [_coerce_sql_result(item) for item in sql_results]
    normalized_results = [item for item in normalized_results if item.rows]
    if not normalized_results:
        return ReportDataValidation(ok=True)

    allowed_values = _build_allowed_values(normalized_results)
    candidates = _extract_report_numbers(html)
    untraceable = [
        item.raw for item in candidates if item.normalized not in allowed_values
    ]
    if not untraceable:
        return ReportDataValidation(ok=True)

    unique_untraceable = list(dict.fromkeys(untraceable))
    issues = [
        (
            "HTML report contains values that are not traceable to successful "
            "sql_query results: "
            + ", ".join(unique_untraceable[:20])
        )
    ]
    return ReportDataValidation(
        ok=False,
        untraceable_values=unique_untraceable,
        issues=issues,
    )


@dataclass(frozen=True)
class _NumberToken:
    raw: str
    normalized: str


def _coerce_sql_result(item: SqlResult | dict[str, Any]) -> SqlResult:
    if isinstance(item, SqlResult):
        return item
    return SqlResult(
        columns=[str(col) for col in item.get("columns", [])],
        rows=[list(row) for row in item.get("rows", [])],
        row_count=int(item.get("row_count") or len(item.get("rows", []))),
        sql=str(item.get("sql") or ""),
    )


def _build_allowed_values(sql_results: list[SqlResult]) -> set[str]:
    allowed: set[str] = set()
    numeric_columns_by_result: list[list[list[Decimal]]] = []

    for result in sql_results:
        allowed.add(_normalize_decimal(Decimal(result.row_count)))
        columns: list[list[Decimal]] = [[] for _ in result.columns]
        for row in result.rows:
            row_values: list[Decimal] = []
            for idx, value in enumerate(row):
                decimal_value = _to_decimal(value)
                if decimal_value is None:
                    continue
                allowed.update(_decimal_variants(decimal_value))
                row_values.append(decimal_value)
                if idx < len(columns):
                    columns[idx].append(decimal_value)
            _add_ratio_values(allowed, row_values)
        numeric_columns_by_result.append(columns)

    for columns in numeric_columns_by_result:
        column_sums = [sum(values, Decimal("0")) for values in columns if values]
        for total in column_sums:
            allowed.update(_decimal_variants(total))
        _add_ratio_values(allowed, column_sums)

    return allowed


def _add_ratio_values(allowed: set[str], values: list[Decimal]) -> None:
    for numerator in values:
        for denominator in values:
            if denominator == 0:
                continue
            ratio = numerator / denominator * Decimal("100")
            if Decimal("-100000") <= ratio <= Decimal("100000"):
                allowed.update(_decimal_variants(ratio, max_places=2))


def _extract_report_numbers(html: str) -> list[_NumberToken]:
    parser = _VisibleTextParser()
    parser.feed(html)
    text = " ".join(parser.parts)
    text = _remove_date_like_text(text)

    tokens: list[_NumberToken] = []
    for match in re.finditer(r"(?<![\w])-?\d[\d,]*(?:\.\d+)?%?", text):
        raw = match.group(0)
        if _should_ignore_token(raw, text, match.start(), match.end()):
            continue
        normalized = _normalize_raw_number(raw)
        if normalized is not None:
            tokens.append(_NumberToken(raw=raw, normalized=normalized))
    return tokens


def _remove_date_like_text(text: str) -> str:
    patterns = [
        r"\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日",
        r"\d{4}\s*[-/]\s*\d{1,2}\s*[-/]\s*\d{1,2}",
        r"\d{1,2}\s*月\s*\d{1,2}\s*日",
        r"\d{1,2}\s*:\s*\d{2}(?::\d{2})?",
    ]
    for pattern in patterns:
        text = re.sub(pattern, " ", text)
    return text


def _should_ignore_token(raw: str, text: str, start: int, end: int) -> bool:
    stripped = raw.rstrip("%").replace(",", "")
    if "." not in stripped and "%" not in raw:
        try:
            number = int(stripped)
        except ValueError:
            number = 0
        if -10 < number < 10:
            return True

    before = text[max(0, start - 8) : start].lower()
    after = text[end : end + 8].lower()
    if "top" in before or "top" in after:
        return True
    return False


def _normalize_raw_number(raw: str) -> str | None:
    value = raw.rstrip("%").replace(",", "")
    try:
        return _normalize_decimal(Decimal(value))
    except InvalidOperation:
        return None


def _to_decimal(value: Any) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float, Decimal)):
        try:
            return Decimal(str(value))
        except InvalidOperation:
            return None
    if isinstance(value, str):
        text = value.strip().replace(",", "")
        if not re.fullmatch(r"-?\d+(?:\.\d+)?", text):
            return None
        try:
            return Decimal(text)
        except InvalidOperation:
            return None
    return None


def _decimal_variants(value: Decimal, max_places: int = 2) -> set[str]:
    variants = {_normalize_decimal(value)}
    for places in range(max_places + 1):
        quant = Decimal("1") if places == 0 else Decimal("1").scaleb(-places)
        rounded = value.quantize(quant, rounding=ROUND_HALF_UP)
        variants.add(_normalize_decimal(rounded))
    return variants


def _normalize_decimal(value: Decimal) -> str:
    normalized = value.normalize()
    if normalized == normalized.to_integral():
        return str(normalized.quantize(Decimal("1")))
    return format(normalized, "f").rstrip("0").rstrip(".")
