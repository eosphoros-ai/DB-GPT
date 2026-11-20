"""Extract explicitly scoped, year-backed statement rows from text reports."""

import datetime
import re
import unicodedata
from decimal import Decimal

UNIT_MULTIPLIERS = {
    "元": 1,
    "千元": 1000,
    "万元": 10000,
    "百万元": 1000000,
    "亿元": 100000000,
}


def _normalize_financial_label(text):
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", text)).strip(
        "()[]【】，,。.;；"
    )


def _unit_declaration(text):
    label = _normalize_financial_label(text)
    marker = re.search(r"单位[:=]?(.*)", label)
    if marker is None:
        return False, None
    value = _normalize_financial_label(marker.group(1).split("币种", 1)[0])
    value = value.removeprefix("人民币")
    return True, value if value in UNIT_MULTIPLIERS else None


def _column_date(segment):
    """Keep year-only and invalid dates unknown."""
    match = re.search(
        r"(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日"
        r"|(\d{4})[-/](\d{1,2})[-/](\d{1,2})",
        segment,
    )
    if match is None:
        return None
    year, month, day = (int(part) for part in match.groups() if part)
    try:
        return datetime.date(year, month, day).isoformat()
    except ValueError:
        return None


def _column_periods(heading_text):
    anchors = list(
        re.finditer(r"(?:19|20)\d{2}(?=年|[-/]\d{1,2}[-/]\d{1,2})", heading_text)
    )
    years, column_dates = [], []
    for index, anchor in enumerate(anchors):
        end = (
            anchors[index + 1].start()
            if index + 1 < len(anchors)
            else len(heading_text)
        )
        segment = heading_text[anchor.start() : end]
        years.append(segment[:4])
        column_dates.append(_column_date(segment))
    return years, column_dates


def _opening_restatement(source, year):
    dates = source.get("column_dates") or []
    return (
        len(dates) == 2
        and all(dates)
        and set(dates) == {f"{int(year) - 1}-12-31", f"{year}-01-01"}
    )


def _select_balance_sheet_candidate(matches, year):
    previous = str(int(year) - 1)
    eligible = [
        source
        for source in matches
        if year in source["years"]
        and previous in source["years"]
        and not _opening_restatement(source, year)
    ]
    return eligible[0] if len(eligible) == 1 else None


def extract_text_report(file_path):
    text = file_path.read_text(encoding="utf-8")
    if not text.strip():
        return {"error": True, "message": "File is empty or could not be parsed"}
    data = {
        "company_name": None,
        "report_year": None,
        "report_date": None,
        "net_profit": None,
        "total_assets": None,
        "total_liabilities": None,
        "equity": None,
        "operating_cash_flow": None,
        "revenue": None,
        "cost_of_sales": None,
    }
    for pattern in [
        r"公司名称[：:\s]*([\u4e00-\u9fa5]{2,}(?:股份有限公司|有限责任公司|有限公司|集团|公司))",
        r"([\u4e00-\u9fa5]{2,}(?:股份有限公司|有限责任公司|有限公司))\s*\d{4}\s*年",
        r"([\u4e00-\u9fa5]{2,}(?:股份有限公司|有限责任公司|有限公司))",
    ]:
        match = re.search(pattern, text[:3000])
        if match:
            data["company_name"] = match.group(1).strip()
            break
    for pattern in [
        r"(\d{4})\s*年\s*(?:年度|半年度|第[一二三四]季度)?\s*报告",
        r"(\d{4})\s*年度",
        r"(\d{4})\s*年",
    ]:
        match = re.search(pattern, text[:5000])
        if match:
            data["report_year"] = match.group(1)
            break
    for pattern in [
        r"报告期[末：:\s]*(\d{4}[-/年]\d{1,2}[-/月]\d{1,2}日?)",
        r"(\d{4}年\d{1,2}月\d{1,2}日)",
        r"(\d{4}-\d{2}-\d{2})",
    ]:
        match = re.search(pattern, text[:5000])
        if match:
            data["report_date"] = match.group(1)
            break
    fields = {
        "合并资产负债表": {
            "total_assets": "资产总计",
            "total_liabilities": "负债合计",
            "equity": "归属于母公司所有者权益合计",
            "total_equity": "所有者权益合计",
        },
        "合并利润表": {
            "revenue": "营业收入",
            "cost_of_sales": "营业成本",
            "net_profit": "归属于母公司所有者的净利润",
        },
        "合并现金流量表": {"operating_cash_flow": "经营活动产生的现金流量净额"},
    }
    for mapping in fields.values():
        for name in mapping:
            data[name] = None
    sources, candidates = {}, {}
    active, unit, years, column_dates, note_column = None, None, [], [], False
    heading = re.compile(
        r"^(?:[（(]?[一二三四五六七八九十百\d]+[）)、.．]?)?"
        r"((?:合并|母公司)?(?:资产负债表|利润表|现金流量表|所有者权益变动表))(.*)$"
    )
    number = r"[-−]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?"
    for line in text.splitlines():
        line = line.strip()
        heading_text = _normalize_financial_label(line)
        match = heading.match(heading_text)
        if match:
            statement, suffix = match.groups()
            continuation = "续" in suffix
            suffix = suffix.replace("续表", "").replace("续", "")
            declared, heading_unit = _unit_declaration(suffix)
            has_currency_label = "币种" in suffix
            remainder = re.sub(r"[（()）、，,。.;；:：]", "", suffix)
            if not (continuation and active == statement):
                unit, years, column_dates, note_column = None, [], [], False
            active = (
                statement if not remainder or declared or has_currency_label else None
            )
            if declared:
                unit = heading_unit
            elif remainder:
                unit, years, column_dates = None, [], []
            continue
        if re.search(r"资产负债表|利润表|现金流量表|所有者权益变动表", heading_text):
            active, unit, years, column_dates = None, None, [], []
            continue
        if active not in fields:
            continue
        declared, declared_unit = _unit_declaration(heading_text)
        if declared:
            unit = declared_unit
        if heading_text.startswith("项目"):
            years, column_dates = _column_periods(heading_text)
            note_column = "附注" in heading_text
        if unit not in UNIT_MULTIPLIERS or len(years) != 2 or years[0] == years[1]:
            continue
        for key, label in fields[active].items():
            note = (
                r"(?:附注\s*)?[（(]?[一二三四五六七八九十百\d]+[）)]?"
                r"(?:[、.．-]\d+)?"
            )
            explicit_note = (
                r"附注\s*[（(]?[一二三四五六七八九十百\d]+[）)]?(?:[、.．-]\d+)?"
            )
            row = re.fullmatch(
                r"(?:其中[：:]|[一二三四五六七八九十]+[、.．]|\d+[.．])?\s*"
                + re.escape(label)
                + r"\s+(?:(?P<note>"
                + (note if note_column else explicit_note)
                + r")\s+)?(?P<current>"
                + number
                + r")\s+(?P<previous>"
                + number
                + r")\s*",
                line,
            )
            if row:
                candidates.setdefault(key, []).append(
                    {
                        "statement": active,
                        "page": 1,
                        "row": line,
                        "unit": unit,
                        "normalized_unit": "元",
                        "unit_multiplier": UNIT_MULTIPLIERS[unit],
                        "note": row.group("note"),
                        "years": years[:],
                        "column_dates": column_dates[:],
                        "values": [
                            float(
                                Decimal(row.group(i).replace(",", "").replace("−", "-"))
                                * UNIT_MULTIPLIERS[unit]
                            )
                            for i in ("current", "previous")
                        ],
                        "raw_values": [row.group(i) for i in ("current", "previous")],
                    }
                )
    for key, matches in candidates.items():
        if not data.get("report_year"):
            continue
        year = str(data["report_year"])
        previous = str(int(year) - 1)
        if key in fields["合并资产负债表"]:
            source = _select_balance_sheet_candidate(matches, year)
        else:
            source = matches[0] if len(matches) == 1 else None
            if source is not None and not (
                year in source["years"] and previous in source["years"]
            ):
                source = None
        if source is None:
            continue
        data[key] = source["values"][source["years"].index(year)]
        data["prev_" + key] = source["values"][source["years"].index(previous)]
        sources[key] = source
    data["_meta"] = {
        "file": file_path.name,
        "text_length": len(text),
        "extracted_fields": [k for k, v in data.items() if v is not None],
        "missing_fields": [k for k, v in data.items() if v is None],
        "sources": sources,
    }
    return data
