import json
import os
import re
import sys


def read_file_content(file_path):
    """Read content from a file, supporting both text and PDF formats."""
    _, ext = os.path.splitext(file_path.lower())

    if ext == ".pdf":
        try:
            import pdfplumber

            text_parts = []
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text_parts.append(page_text)
            return "\n".join(text_parts)
        except ImportError:
            raise RuntimeError(
                "pdfplumber is required to read PDF files. "
                "Install it with: pip install pdfplumber"
            )
    else:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()


def extract_from_text(text):
    """Extract key financial data from text using regex.

    Scans Chinese financial reports for common accounting line items and
    returns the first numeric match found for each metric.
    """
    data = {
        "company_name": None,
        "report_year": None,
        "report_date": None,
        "revenue": None,
        "net_profit": None,
        "total_assets": None,
        "total_liabilities": None,
        "equity": None,
        "operating_cash_flow": None,
        "cost_of_sales": None,
    }

    # ── Extract basic info: company name, year, date ──────────────
    # Company name: look for patterns like "XX公司" or "XX股份有限公司"
    company_patterns = [
        r"公司名称[：:\s]*([\u4e00-\u9fa5]{2,}(?:股份有限公司|有限责任公司|有限公司|集团|公司))",
        r"([\u4e00-\u9fa5]{2,}(?:股份有限公司|有限责任公司|有限公司))\s*\d{4}\s*年",
        r"([\u4e00-\u9fa5]{2,}(?:股份有限公司|有限责任公司|有限公司))",
    ]
    for pat in company_patterns:
        m = re.search(pat, text[:3000])
        if m:
            data["company_name"] = m.group(1).strip()
            break

    # Report year: "2023年年度报告" / "2023年度" / "2023 年"
    year_patterns = [
        r"(\d{4})\s*年\s*(?:年度|半年度|第[一二三四]季度)?\s*报告",
        r"(\d{4})\s*年度",
        r"(\d{4})\s*年",
    ]
    for pat in year_patterns:
        m = re.search(pat, text[:5000])
        if m:
            data["report_year"] = m.group(1)
            break

    # Report date: "报告期 2023-12-31" / "2023年12月31日"
    date_patterns = [
        r"报告期[末：:\s]*(\d{4}[-/年]\d{1,2}[-/月]\d{1,2}日?)",
        r"(\d{4}年\d{1,2}月\d{1,2}日)",
        r"(\d{4}-\d{2}-\d{2})",
    ]
    for pat in date_patterns:
        m = re.search(pat, text[:5000])
        if m:
            data["report_date"] = m.group(1)
            break

    patterns = {
        "revenue": [
            r"营业收入[^\d]*?([\d,]+\.?\d*)",
            r"营业总收入[^\d]*?([\d,]+\.?\d*)",
        ],
        "net_profit": [
            r"归属于上市公司股东的净利润[^\d]*?([\d,]+\.?\d*)",
            r"净利润[^\d]*?([\d,]+\.?\d*)",
        ],
        "total_assets": [
            r"总资产[^\d]*?([\d,]+\.?\d*)",
            r"资产总[计额][^\d]*?([\d,]+\.?\d*)",
        ],
        "total_liabilities": [
            r"总负债[^\d]*?([\d,]+\.?\d*)",
            r"负债[总合][计额][^\d]*?([\d,]+\.?\d*)",
        ],
        "equity": [
            r"归属于上市公司股东的净资产[^\d]*?([\d,]+\.?\d*)",
            r"所有者权益合计[^\d]*?([\d,]+\.?\d*)",
            r"股东权益合计[^\d]*?([\d,]+\.?\d*)",
        ],
        "operating_cash_flow": [
            r"经营活动产生的现金流量净额[^\d]*?([\d,]+\.?\d*)",
        ],
        "cost_of_sales": [
            r"营业成本[^\d]*?([\d,]+\.?\d*)",
            r"营业总成本[^\d]*?([\d,]+\.?\d*)",
        ],
    }

    for key, regex_list in patterns.items():
        for regex in regex_list:
            match = re.search(regex, text)
            if match:
                val_str = match.group(1).replace(",", "")
                try:
                    data[key] = float(val_str)
                    break
                except ValueError:
                    continue

    return data


def extract_financials(file_path):
    """Extract key financial data from a file.

    Args:
        file_path: Path to the financial report file (supports .pdf, .txt, .md, etc.)

    Returns:
        dict with extracted financial metrics.
    """
    if not os.path.exists(file_path):
        return {"error": True, "message": f"File not found: {file_path}"}

    try:
        if file_path.lower().endswith(".pdf"):
            import pdfplumber

            with pdfplumber.open(file_path) as pdf:
                pages = [page.extract_text() or "" for page in pdf.pages]
            text = "\n".join(pages)
        else:
            text = read_file_content(file_path)
            pages = [text]
    except Exception as e:
        return {"error": True, "message": f"Failed to read file: {e}"}

    if not text or not text.strip():
        return {"error": True, "message": "File is empty or could not be parsed"}

    data = extract_from_text(text)
    # Never treat an unscoped first regex match as a financial statement value.
    # Only rows from identified consolidated statements with explicit years and
    # units are eligible; unresolved or ambiguous values remain missing.
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
    for name in {name for mapping in fields.values() for name in mapping}:
        data[name] = None
    sources = {}
    active = None
    unit = None
    years = []
    candidates = {}
    heading = re.compile(
        r"^\s*(?:(?:[（(]?[一二三四五六七八九十百\d]+[）)、.．]?)[\s]*)?"
        r"((?:合并|母公司)(?:资产负债表|利润表|现金流量表))\s*$"
    )
    number = r"[-−]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?"
    for page_number, page in enumerate(pages, 1):
        for line in page.splitlines():
            line = line.strip()
            match = heading.match(line)
            if match:
                active = match.group(1)
                unit, years = None, []
                continue
            if re.search(
                r"(?:资产负债表|利润表|现金流量表|所有者权益变动表)(?:[（(](?:续|续表)[）)])?\s*$",
                line,
            ):
                # An unsupported statement heading still ends the old scope.
                active, unit, years = None, None, []
                continue
            if active not in fields:
                continue
            if re.fullmatch(r"单位[：:]\s*元", line):
                unit = "元"
            if line.startswith("项目"):
                years = re.findall(r"(?:19|20)\d{2}(?=年)", line)
            if unit != "元" or len(years) != 2 or years[0] == years[1]:
                continue
            for key, label in fields[active].items():
                row = re.fullmatch(
                    r"(?:其中[：:]|[一二三四五六七八九十]+[、.．]|\d+[.．])?\s*"
                    + re.escape(label)
                    + r"\s+("
                    + number
                    + r")\s+("
                    + number
                    + r")\s*",
                    line,
                )
                if row:
                    candidates.setdefault(key, []).append(
                        {
                            "statement": active,
                            "page": page_number,
                            "row": line,
                            "unit": unit,
                            "years": years[:],
                            "values": [
                                float(row.group(i).replace(",", "").replace("−", "-"))
                                for i in (1, 2)
                            ],
                        }
                    )
    for key, matches in candidates.items():
        if len(matches) != 1 or not data.get("report_year"):
            continue
        source = matches[0]
        year = str(data["report_year"])
        if year not in source["years"] or str(int(year) - 1) not in source["years"]:
            continue
        data[key] = source["values"][source["years"].index(year)]
        data["prev_" + key] = source["values"][
            source["years"].index(str(int(year) - 1))
        ]
        sources[key] = source

    # Add a summary of which fields were successfully extracted
    extracted = [k for k, v in data.items() if v is not None]
    missing = [k for k, v in data.items() if v is None]
    data["_meta"] = {
        "file": os.path.basename(file_path),
        "text_length": len(text),
        "extracted_fields": extracted,
        "missing_fields": missing,
        "sources": sources,
    }

    return data


if __name__ == "__main__":
    if len(sys.argv) > 1:
        arg = sys.argv[1]

        # Parse the JSON argument passed by execute_skill_script_file
        try:
            parsed = json.loads(arg)
            if isinstance(parsed, dict):
                fp = parsed.get("file_path", "")
            else:
                fp = str(parsed)
        except json.JSONDecodeError:
            fp = arg

        if not fp:
            print(
                json.dumps(
                    {"error": True, "message": "Missing required parameter: file_path"},
                    ensure_ascii=False,
                )
            )
            sys.exit(1)

        result = extract_financials(fp)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(
            "Usage: python3 extract_financials.py "
            '\'{"file_path": "/path/to/report.pdf"}\''
        )
