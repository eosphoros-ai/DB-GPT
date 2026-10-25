"""Conservative extractor for text-based Chinese non-financial annual reports.

Amounts come only from recognized tables, never from nearby narrative numbers.
The canonical values are decimal strings; legacy numeric fields are an adapter.
No OCR, restatement reconciliation, or human verification is implied.
"""

import hashlib
import json
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path

from table_structure import aligned_columns, relative_columns, structure_table

UNITS = {"元": 1, "千元": 1000, "万元": 10000, "百万元": 1000000, "亿元": 100000000}
METRICS = {
    "revenue": ("营业收入", "flow", ["营业收入"]),
    "net_profit": (
        "归母净利润",
        "flow",
        ["归属于上市公司股东的净利润", "归属于母公司所有者的净利润"],
    ),
    "non_recurring_net_profit": (
        "扣非归母净利润",
        "flow",
        ["归属于上市公司股东的扣除非经常性损益的净利润"],
    ),
    "operating_cash_flow": (
        "经营活动现金流量净额",
        "flow",
        ["经营活动产生的现金流量净额"],
    ),
    "total_assets": ("总资产", "instant", ["资产总计", "资产总额", "总资产"]),
    "total_liabilities": ("总负债", "instant", ["负债合计", "负债总计", "总负债"]),
    "equity": (
        "归母净资产",
        "instant",
        ["归属于上市公司股东的净资产", "归属于母公司所有者权益合计"],
    ),
    "cost_of_sales": ("营业成本", "flow", ["营业成本"]),
    "selling_expenses": ("销售费用", "flow", ["销售费用"]),
    "administrative_expenses": ("管理费用", "flow", ["管理费用"]),
    "research_expenses": ("研发费用", "flow", ["研发费用"]),
    "financial_expenses": ("财务费用", "flow", ["财务费用"]),
    "current_assets": ("流动资产", "instant", ["流动资产合计"]),
    "current_liabilities": ("流动负债", "instant", ["流动负债合计"]),
    "inventory": ("存货", "instant", ["存货"]),
}
STATEMENT = re.compile(
    r"^(?:\d{1,2}[、.．])?(合并|母公司)(资产负债表|利润表|现金流量表|所有者权益变动表)$"
)
SUMMARY = re.compile(r"^(?:[一二三四五六七八九十]+[、.．])?主要会计数据和财务指标$")
MAJOR_HEADING = re.compile(r"^[一二三四五六七八九十]+[、.．]")


def compact(value):
    return re.sub(r"\s+", "", value or "")


def amount(raw, unit):
    """Return exact yuan or a reason; blanks/dashes are not zero."""
    value = compact(raw).replace("，", ",").replace("−", "-").replace("－", "-")
    value = value.replace("（", "(").replace("）", ")")
    if not value or value in {"-", "--", "—", "–", "/", "不适用"}:
        return None, "missing_value"
    if re.fullmatch(r"\(.+\)", value):
        value = "-" + value[1:-1]
    if not re.fullmatch(r"[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?", value):
        return None, "invalid_amount"
    if unit not in UNITS:
        return None, "unknown_unit"
    try:
        return format(Decimal(value.replace(",", "")) * UNITS[unit], "f"), None
    except InvalidOperation:
        return None, "invalid_amount"


def period_header(raw):
    value = compact(raw)
    match = re.fullmatch(r"(20\d{2})(?:年(?:度|末)?|年12月31日|-12-31)", value)
    return match.group(1) if match else None


def source_period(raw):
    """Keep opening dates distinct from preceding closing balances."""
    value = compact(raw)
    opening = re.fullmatch(r"(20\d{2})(?:年0?1月0?1日|-01-01)", value)
    if opening:
        year = opening.group(1)
        return {"year": year, "role": "opening", "date": f"{year}-01-01"}
    year = period_header(raw)
    if not year:
        return None
    closing = value.endswith(("年末", "12月31日", "-12-31"))
    return {
        "year": year,
        "role": "closing" if closing else "annual",
        "date": f"{year}-12-31" if closing else None,
    }


def row_metric(label):
    value = compact(label).replace("（", "(").replace("）", ")")
    value = re.sub(r"^(?:[一二三四五六七八九十]+[、.]|\d+[.、])", "", value)
    value = re.sub(r"^(?:其中[:：])", "", value)
    value = re.sub(r"\((?:人民币)?(?:百万元|千元|万元|亿元|元)\)$", "", value)
    for code, (_, _, aliases) in METRICS.items():
        if value in aliases:
            return code
    return None


def unit_in(text):
    match = re.search(
        r"(?:单位[:：]|[（(])(?:人民币)?(百万元|千元|万元|亿元|元)"
        r"(?:[）)]|币种|$)",
        compact(text),
    )
    return match.group(1) if match else None


def currency_in(text):
    for pattern, currency in [
        (r"美元|USD", "USD"),
        (r"港币|港元|HKD", "HKD"),
        (r"欧元|EUR", "EUR"),
        (r"日元|JPY", "JPY"),
        (r"人民币|CNY|RMB", "CNY"),
    ]:
        if re.search(pattern, text, re.IGNORECASE):
            return currency
    return None


def logical_rows(rows, *, preserve_columns=False):
    """Merge pdfplumber's split labels/amounts without collapsing empty columns.

    Globally empty phantom columns are removed. Label-only suffixes belong to
    the preceding row; a new recognizable label starts a new row. Keeping the
    original row indexes makes the transformation auditable.
    """
    width = max((len(row) for row in rows), default=0)
    active = (
        list(range(width))
        if preserve_columns
        else [
            i for i in range(width) if any(i < len(r) and compact(r[i]) for r in rows)
        ]
    )
    pending = None
    for index, raw in enumerate(rows):
        row = [raw[i] if i < len(raw) else None for i in active]
        if not row or not any(compact(c) for c in row):
            continue
        label = compact(row[0])
        has_values = any(compact(c) for c in row[1:])
        # Headers and complete rows are never joined to prior amounts.
        is_header = sum(source_period(c) is not None for c in row) >= 2
        is_suffix = label.startswith(("（", "(", "经常性", "常性", "损益", "净利润"))
        combined = compact(pending["cells"][0]) + label if pending else ""
        metric_continuation = bool(
            label and pending and compact(pending["cells"][0])
        ) and any(
            alias.startswith(combined) or row_metric(combined) == code
            for code, (_, _, aliases) in METRICS.items()
            for alias in aliases
        )
        if pending and not has_values and (is_suffix or metric_continuation):
            pending["cells"][0] = (pending["cells"][0] or "") + label
            pending["rowIndexes"].append(index)
        elif (
            pending
            and not label
            and has_values
            and not is_header
            and not any(compact(c) for c in pending["cells"][1:])
        ):
            pending["cells"][1:] = row[1:]
            pending["rowIndexes"].append(index)
        else:
            if pending:
                yield pending
            pending = {"cells": row, "rowIndexes": [index], "columnIndexes": active}
    if pending:
        yield pending


def parse_pdf(path):
    """Keep page text and original cells for supported financial table regions."""
    import pdfplumber

    pages = []
    context = None
    with pdfplumber.open(path) as pdf:
        for number, page in enumerate(pdf.pages, 1):
            lines = page.extract_text_lines()
            text = "\n".join(line["text"] for line in lines)
            record = {"page": number, "text": text, "tables": []}
            events = []
            for line in lines:
                value = compact(line["text"])
                title = STATEMENT.fullmatch(value)
                if title or SUMMARY.fullmatch(value):
                    events.append((line["top"], "heading", value))
                elif MAJOR_HEADING.match(value):
                    events.append((line["top"], "end", value))
                if value.startswith(("单位", "币种")) or "报表的单位为" in value:
                    events.append((line["top"], "unit", value))
            if context or any(kind == "heading" for _, kind, _ in events):
                tables = page.find_tables()
                # Statement rows such as “一、营业总收入” are not section ends.
                events = [
                    event
                    for event in events
                    if event[1] != "end"
                    or not any(
                        table.bbox[1] <= event[0] <= table.bbox[3] for table in tables
                    )
                ]
                for table in tables:
                    events.append((table.bbox[1], "table", table))
            for _, kind, value in sorted(
                events, key=lambda event: (event[0], event[1] == "table")
            ):
                if kind == "heading":
                    title = STATEMENT.fullmatch(value)
                    context = {
                        "section": value,
                        "scope": title.group(1) if title else "summary",
                        "statement": title.group(2) if title else "summary",
                        "headingPage": number,
                        "unit": None,
                        "unitPage": None,
                        "unitText": None,
                        "currency": None,
                    }
                elif kind == "end":
                    context = None
                elif kind == "unit" and context:
                    context = dict(
                        context, currency=currency_in(value) or context["currency"]
                    )
                    if value.startswith("单位"):
                        context.update(
                            unit=unit_in(value), unitPage=number, unitText=value
                        )
                elif kind == "table" and context:
                    raw_rows = value.extract()
                    boxes = [row.cells for row in value.rows]
                    record["tables"].append(
                        {
                            "id": f"p{number}-t{len(record['tables']) + 1}",
                            "bbox": list(value.bbox),
                            "rows": raw_rows,
                            "cellBoxes": boxes,
                            "structure": structure_table(raw_rows, boxes, value.bbox),
                            **context,
                        }
                    )
            pages.append(record)
            page.close()
    return pages


def join_label_continuations(pages):
    """Join a verified metric suffix in a label-only table on the next page."""
    previous = None
    for page in pages:
        for table in page["tables"]:
            if previous:
                prior_page, prior = previous
                structure = prior.get("structure", {})
                same_section = (table["section"], table["headingPage"]) == (
                    prior["section"],
                    prior["headingPage"],
                )
                if (
                    same_section
                    and page["page"] == prior_page + 1
                    and structure.get("status") == "mapped"
                ):
                    logical = list(
                        logical_rows(structure["rows"], preserve_columns=True)
                    )
                    fragments = [
                        compact(c) for row in table["rows"] for c in row if compact(c)
                    ]
                    if logical and fragments:
                        last = logical[-1]
                        label = compact(last["cells"][0])
                        suffix = "".join(fragments)
                        label_bounds = structure["columns"][0]
                        fragment_boxes = [
                            box
                            for values, boxes in zip(
                                table["rows"], table.get("cellBoxes", [])
                            )
                            for value, box in zip(values, boxes)
                            if compact(value) and box
                        ]
                        if (
                            not row_metric(label)
                            and row_metric(label + suffix)
                            and fragment_boxes
                            and all(
                                box[0] >= label_bounds[0] - 2
                                and box[2] <= label_bounds[1] + 2
                                for box in fragment_boxes
                            )
                        ):
                            row_index = last["rowIndexes"][-1]
                            structure["rows"][row_index][0] = (
                                structure["rows"][row_index][0] or ""
                            ) + suffix
                            prior["labelContinuation"] = {
                                "rowIndex": row_index,
                                "page": page["page"],
                                "table": table["id"],
                                "text": suffix,
                                "bbox": table["bbox"],
                            }
                            table["labelContinuationOf"] = prior["id"]
            previous = (page["page"], table)


def table_candidates(pages, document_id):
    for page in pages:
        for table in page["tables"]:
            table.pop("parseIssues", None)
    join_label_continuations(pages)
    header = None
    previous_section = None
    candidates = []
    for page in pages:
        for table in page["tables"]:
            section_key = (table["section"], table["headingPage"])
            if section_key != previous_section:
                header = None
                previous_section = section_key
            if (
                table["scope"] not in {"合并", "summary"}
                or table["statement"] == "所有者权益变动表"
            ):
                continue
            structure = table.get("structure")
            geometry = structure and structure["status"] == "mapped"
            if table.get("labelContinuationOf"):
                continue
            if structure and not geometry:
                table["parseIssues"] = [structure["reason"]]
                header = None
                continue
            if (
                header
                and geometry
                and (
                    not header.get("bounds")
                    or not aligned_columns(header["bounds"], relative_columns(table))
                )
            ):
                header = None
            rows = structure["rows"] if geometry else table["rows"]
            for row in logical_rows(rows, preserve_columns=bool(geometry)):
                cells = row["cells"]
                if any(
                    re.search(r"调整前|调整后|调整数|重述", compact(c)) for c in cells
                ):
                    # Only coordinate-mapped subheaders can qualify a merged
                    # year. Index-only legacy extraction records remain conservative.
                    if (
                        geometry
                        and header
                        and not any(source_period(c) for c in cells)
                        and not any(
                            re.search(r"调整数|重述", compact(c)) for c in cells
                        )
                    ):
                        for col in header["years"]:
                            marker = compact(cells[col])
                            if marker in {"调整前", "调整后"}:
                                header["adjustments"][col] = (
                                    "before" if marker == "调整前" else "after"
                                )
                        header["subheader"] = " | ".join(str(c or "") for c in cells)
                    else:
                        header = None
                    continue
                periods = {
                    i: source_period(c)
                    for i, c in enumerate(cells)
                    if source_period(c)
                    and (geometry or source_period(c)["role"] != "opening")
                }
                if len(periods) >= 2:
                    header = {
                        "years": {i: p["year"] for i, p in periods.items()},
                        "periods": periods,
                        "adjustments": {},
                        "cells": cells,
                        "page": page["page"],
                        "tableId": table["id"],
                        "width": len(cells),
                        "bounds": relative_columns(table) if geometry else None,
                    }
                    continue
                # An unrecognized date/header must not inherit a previous annual header.
                if any(
                    re.search(r"20\d{2}年\d+月\d+日|调整数|重述", compact(c))
                    for c in cells
                ):
                    header = None
                code = row_metric(cells[0])
                if not code or not header or header["width"] != len(cells):
                    continue
                allowed = {
                    "资产负债表": {
                        "total_assets",
                        "total_liabilities",
                        "equity",
                        "current_assets",
                        "current_liabilities",
                        "inventory",
                    },
                    "利润表": {
                        "revenue",
                        "net_profit",
                        "cost_of_sales",
                        "selling_expenses",
                        "administrative_expenses",
                        "research_expenses",
                        "financial_expenses",
                    },
                    "现金流量表": {"operating_cash_flow"},
                    "summary": set(METRICS),
                }
                if code not in allowed.get(table["statement"], set()):
                    continue
                label = cells[0]
                row_unit = unit_in(label)
                unit = row_unit or table["unit"]
                for column, year in header["years"].items():
                    period = header["periods"][column]
                    adjustment = header["adjustments"].get(column, "unspecified")
                    same_period = [
                        i for i, p in header["periods"].items() if p == period
                    ]
                    if len(same_period) > 1 and sorted(
                        header["adjustments"].get(i, "unspecified") for i in same_period
                    ) != ["after", "before"]:
                        table.setdefault("parseIssues", []).append(
                            "ambiguous_period_columns"
                        )
                        continue
                    if METRICS[code][1] == "flow" and period["role"] != "annual":
                        continue
                    raw = cells[column] or ""
                    value, reason = amount(raw, unit)
                    currency = currency_in(label) or table.get("currency")
                    if currency and currency != "CNY":
                        value, reason = None, "unsupported_currency"
                    evidence_id = (
                        f"{document_id}-{table['id']}-r{row['rowIndexes'][0]}"
                        f"-c{row['columnIndexes'][column]}"
                    )
                    candidates.append(
                        {
                            "metricCode": code,
                            "fiscalPeriod": year,
                            "sourcePeriod": dict(period, adjustment=adjustment),
                            "rawValue": raw,
                            "normalizedValue": value,
                            "reason": reason,
                            "sourceUnit": unit,
                            "evidence": {
                                "id": evidence_id,
                                "sourceDocumentId": document_id,
                                "page": page["page"],
                                "section": table["section"],
                                "table": table["id"],
                                "row": label,
                                "column": header["cells"][column],
                                "sourcePeriod": dict(period, adjustment=adjustment),
                                "columnSubheader": header.get("subheader"),
                                "snippet": " | ".join(str(c or "") for c in cells),
                                "extractedValue": raw,
                                "normalizedValue": value,
                                "sourceUnit": unit,
                                "sourceCurrency": currency,
                                "qualityStatus": "warning",
                                "headerPage": header["page"],
                                "headerTableId": header["tableId"],
                                "headerSnippet": " | ".join(
                                    str(c or "") for c in header["cells"]
                                ),
                                "unitPage": page["page"]
                                if row_unit
                                else table["unitPage"],
                                "unitText": label if row_unit else table["unitText"],
                                "headingPage": table["headingPage"],
                                "rowIndexes": row["rowIndexes"],
                                "labelContinuation": table.get("labelContinuation")
                                if table.get("labelContinuation", {}).get("rowIndex")
                                in row["rowIndexes"]
                                else None,
                                "sourceCells": [
                                    {
                                        "row": r,
                                        "column": c,
                                        "bbox": table["cellBoxes"][r][c],
                                    }
                                    for logical_row in row["rowIndexes"]
                                    for r, c in structure["sourceCells"][logical_row][
                                        column
                                    ]
                                ]
                                if geometry
                                else [],
                            },
                        }
                    )
    return candidates


def build_result(pages, document_id, file_name):
    cover = "\n".join(page["text"] for page in pages[:5])
    year_match = re.search(r"(20\d{2})\s*年\s*(?:年度|度)?\s*报告", cover)
    company_match = re.search(
        r"([\u4e00-\u9fff]{2,}(?:股份有限公司|有限责任公司|有限公司))", cover
    )
    year = year_match.group(1) if year_match else None
    company = company_match.group(1) if company_match else None
    company_candidates = sorted(
        set(
            re.findall(
                r"([\u4e00-\u9fff]{2,}(?:股份有限公司|有限责任公司|有限公司))", cover
            )
        )
    )
    cover_candidates = sorted(
        set(
            re.findall(
                r"([\u4e00-\u9fff]{2,}(?:股份有限公司|有限责任公司|有限公司))",
                pages[0]["text"] if pages else "",
            )
        )
    )
    observations = table_candidates(pages, document_id) if year else []
    # Opening balances and pre-adjustment values remain auditable observations,
    # but are not silently converted into comparable year-end financial facts.
    candidates = [
        c
        for c in observations
        if c["sourcePeriod"]["role"] != "opening"
        and c["sourcePeriod"]["adjustment"] != "before"
    ]
    facts, evidence = [], []
    periods = sorted(
        {c["fiscalPeriod"] for c in candidates}
        | ({year, str(int(year) - 1)} if year else set()),
        reverse=True,
    )
    for code, (name, period_type, _) in METRICS.items():
        for period in periods:
            matches = [
                c
                for c in candidates
                if c["metricCode"] == code and c["fiscalPeriod"] == period
            ]
            values = {
                Decimal(c["normalizedValue"])
                for c in matches
                if c["normalizedValue"] is not None
            }
            valid = [c for c in matches if c["normalizedValue"] is not None]
            status = (
                "parsed" if len(values) == 1 else "conflict" if values else "missing"
            )
            value = valid[0]["normalizedValue"] if status == "parsed" else None
            reason = (
                None
                if status == "parsed"
                else "conflicting_values"
                if values
                else ",".join(sorted({c["reason"] for c in matches if c["reason"]}))
                or "row_not_found"
            )
            facts.append(
                {
                    "id": f"{document_id}-{code}-{period}",
                    "metricCode": code,
                    "metricName": name,
                    "rawValue": valid[0]["rawValue"] if status == "parsed" else "",
                    "normalizedValue": value,
                    "displayValue": value or "未识别",
                    "unit": "元",
                    "currency": "CNY",
                    "currencyBasis": "yuan_in_chinese_annual_report",
                    "sourceUnits": sorted(
                        {c["sourceUnit"] for c in matches if c["sourceUnit"]}
                    ),
                    "fiscalPeriod": period,
                    "periodType": period_type,
                    "statementScope": "合并",
                    "sourcePeriods": [c["sourcePeriod"] for c in valid]
                    if status == "parsed"
                    else [],
                    "attribution": "owners_of_parent"
                    if code in {"net_profit", "non_recurring_net_profit", "equity"}
                    else "consolidated",
                    "evidenceExcerptIds": [c["evidence"]["id"] for c in matches],
                    "qualityStatus": "warning",
                    "extractionStatus": status,
                    "missingReason": reason,
                }
            )
            evidence.extend(c["evidence"] for c in matches)
    result = {"company_name": company, "report_year": year, "report_date": None}
    result["company_identity"] = {
        "candidates": cover_candidates or company_candidates,
        "basis": "cover_page" if cover_candidates else "first_five_pdf_pages",
        "evidence": [
            {"page": page["page"], "snippet": page["text"][:600]}
            for page in pages[:5]
            if company and company in compact(page["text"])
        ],
    }
    for code in METRICS:
        for prefix, period in [
            ("", year),
            ("prev_", str(int(year) - 1) if year else None),
        ]:
            fact = next(
                (
                    f
                    for f in facts
                    if f["metricCode"] == code and f["fiscalPeriod"] == period
                ),
                None,
            )
            result[prefix + code] = (
                float(fact["normalizedValue"])
                if fact and fact["normalizedValue"] is not None
                else None
            )
    parsed = [f for f in facts if f["extractionStatus"] == "parsed"]
    result.update(
        {
            "schemaVersion": 1,
            "document": {
                "id": document_id,
                "fileName": file_name,
                "pageCount": len(pages),
            },
            "facts": facts,
            "evidence": evidence,
            "sourceObservations": observations,
        }
    )
    result["_meta"] = {
        "file": file_name,
        "text_length": sum(len(p["text"]) for p in pages),
        "extracted_fields": [k for k in METRICS if result[k] is not None],
        "missing_fields": [k for k in METRICS if result[k] is None],
        "status": "parsed" if parsed else "unsupported",
        "pageNumbering": "physical_1_based",
        "humanVerified": False,
        "reason": None
        if parsed
        else "No supported annual financial tables; scanned PDFs require OCR.",
        "limitations": [
            "仅支持中文文本年报的规则表格；未执行OCR",
            "自动提取待人工核对；仅识别显式调整前/后，期初余额不冒充上期末；未处理多币种",
        ],
        "tableIssues": [
            {
                "page": p["page"],
                "table": t["id"],
                "reasons": sorted(set(t["parseIssues"])),
            }
            for p in pages
            for t in p["tables"]
            if t.get("parseIssues")
        ],
    }
    return result


def extract_document(path, *, artifact_dir=None):
    path = Path(path)
    if path.suffix.lower() != ".pdf":
        raise ValueError(
            "Only text-based annual-report PDFs are supported; "
            "no narrative-number fallback."
        )
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    pages = parse_pdf(path)
    result = build_result(pages, "document-" + digest[:16], path.name)
    result["document"]["sha256"] = digest
    # Full page text/raw cells are opt-in developer artifacts, not model context.
    if artifact_dir is not None:
        directory = Path(artifact_dir)
        directory.mkdir(parents=True, exist_ok=True)
        artifact = directory / f"{digest[:16]}-pages.json"
        artifact.write_text(json.dumps(pages, ensure_ascii=False), encoding="utf-8")
        result["_meta"]["parseArtifact"] = str(artifact)
    return result
