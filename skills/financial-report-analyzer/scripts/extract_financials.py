import re
import json
import sys
import os

# Chinese financial report line-item labels (Unicode escapes keep parsing without CJK in source)
_CO = "\u80a1\u4efd\u6709\u9650\u516c\u53f8"
_LLC = "\u6709\u9650\u8d23\u4efb\u516c\u53f8"
_LTD = "\u6709\u9650\u516c\u53f8"
_GROUP = "\u96c6\u56e2"
_COMPANY = "\u516c\u53f8"
_CNAME = "\u516c\u53f8\u540d\u79f0"
_REPORT_PERIOD = "\u62a5\u544a\u671f"
_YEAR = "\u5e74"
_ANNUAL = "\u5e74\u5ea6"
_SEMI = "\u534a\u5e74\u5ea6"
_REPORT = "\u62a5\u544a"
_Q1 = "\u7b2c\u4e00"
_Q2 = "\u7b2c\u4e8c"
_Q3 = "\u7b2c\u4e09"
_Q4 = "\u7b2c\u56db"
_MONTH = "\u6708"
_DAY = "\u65e5"
_REVENUE = "\u8425\u4e1a\u6536\u5165"
_TOTAL_REVENUE = "\u8425\u4e1a\u603b\u6536\u5165"
_NET_PROFIT_PARENT = "\u5f52\u5c5e\u4e8e\u4e0a\u5e02\u516c\u53f8\u80a1\u4e1c\u7684\u51c0\u5229\u6da6"
_NET_PROFIT = "\u51c0\u5229\u6da6"
_TOTAL_ASSETS = "\u603b\u8d44\u4ea7"
_ASSETS_TOTAL = "\u8d44\u4ea7\u603b"
_TOTAL_LIAB = "\u603b\u8d1f\u503a"
_LIAB_TOTAL = "\u8d1f\u503a"
_EQUITY_PARENT = "\u5f52\u5c5e\u4e8e\u4e0a\u5e02\u516c\u53f8\u80a1\u4e1c\u7684\u51c0\u8d44\u4ea7"
_OWNER_EQUITY = "\u6240\u6709\u8005\u6743\u76ca\u5408\u8ba1"
_SHAREHOLDER_EQUITY = "\u80a1\u4e1c\u6743\u76ca\u5408\u8ba1"
_OPERATING_CF = "\u7ecf\u8425\u6d3b\u52a8\u4ea7\u751f\u7684\u73b0\u91d1\u6d41\u91cf\u51c0\u989d"
_COST_OF_SALES = "\u8425\u4e1a\u6210\u672c"
_TOTAL_COST = "\u8425\u4e1a\u603b\u6210\u672c"


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

    # Extract basic info: company name, year, date
    company_patterns = [
        rf"{_CNAME}[：:\s]*([\u4e00-\u9fa5]{{2,}}(?:{_CO}|{_LLC}|{_LTD}|{_GROUP}|{_COMPANY}))",
        rf"([\u4e00-\u9fa5]{{2,}}(?:{_CO}|{_LLC}|{_LTD}))\s*\d{{4}}\s*{_YEAR}",
        rf"([\u4e00-\u9fa5]{{2,}}(?:{_CO}|{_LLC}|{_LTD}))",
    ]
    for pat in company_patterns:
        m = re.search(pat, text[:3000])
        if m:
            data["company_name"] = m.group(1).strip()
            break

    year_patterns = [
        rf"(\d{{4}})\s*{_YEAR}\s*(?:{_ANNUAL}|{_SEMI}|{_Q1}|{_Q2}|{_Q3}|{_Q4}\u5b63\u5ea6)?\s*{_REPORT}",
        rf"(\d{{4}})\s*{_ANNUAL}",
        rf"(\d{{4}})\s*{_YEAR}",
    ]
    for pat in year_patterns:
        m = re.search(pat, text[:5000])
        if m:
            data["report_year"] = m.group(1)
            break

    date_patterns = [
        rf"{_REPORT_PERIOD}[\u672b：:\s]*(\d{{4}}[-/]{_YEAR}]\d{{1,2}}[-/]{_MONTH}]\d{{1,2}}{_DAY}?)",
        rf"(\d{{4}}{_YEAR}\d{{1,2}}{_MONTH}\d{{1,2}}{_DAY})",
        r"(\d{4}-\d{2}-\d{2})",
    ]
    for pat in date_patterns:
        m = re.search(pat, text[:5000])
        if m:
            data["report_date"] = m.group(1)
            break

    patterns = {
        "revenue": [
            rf"{_REVENUE}[^\d]*?([\d,]+\.?\d*)",
            rf"{_TOTAL_REVENUE}[^\d]*?([\d,]+\.?\d*)",
        ],
        "net_profit": [
            rf"{_NET_PROFIT_PARENT}[^\d]*?([\d,]+\.?\d*)",
            rf"{_NET_PROFIT}[^\d]*?([\d,]+\.?\d*)",
        ],
        "total_assets": [
            rf"{_TOTAL_ASSETS}[^\d]*?([\d,]+\.?\d*)",
            rf"{_ASSETS_TOTAL}[\u8ba1\u989d][^\d]*?([\d,]+\.?\d*)",
        ],
        "total_liabilities": [
            rf"{_TOTAL_LIAB}[^\d]*?([\d,]+\.?\d*)",
            rf"{_LIAB_TOTAL}[\u603b\u5408][\u8ba1\u989d][^\d]*?([\d,]+\.?\d*)",
        ],
        "equity": [
            rf"{_EQUITY_PARENT}[^\d]*?([\d,]+\.?\d*)",
            rf"{_OWNER_EQUITY}[^\d]*?([\d,]+\.?\d*)",
            rf"{_SHAREHOLDER_EQUITY}[^\d]*?([\d,]+\.?\d*)",
        ],
        "operating_cash_flow": [
            rf"{_OPERATING_CF}[^\d]*?([\d,]+\.?\d*)",
        ],
        "cost_of_sales": [
            rf"{_COST_OF_SALES}[^\d]*?([\d,]+\.?\d*)",
            rf"{_TOTAL_COST}[^\d]*?([\d,]+\.?\d*)",
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
        text = read_file_content(file_path)
    except Exception as e:
        return {"error": True, "message": f"Failed to read file: {e}"}

    if not text or not text.strip():
        return {"error": True, "message": "File is empty or could not be parsed"}

    data = extract_from_text(text)

    extracted = [k for k, v in data.items() if v is not None]
    missing = [k for k, v in data.items() if v is None]
    data["_meta"] = {
        "file": os.path.basename(file_path),
        "text_length": len(text),
        "extracted_fields": extracted,
        "missing_fields": missing,
    }

    return data


if __name__ == "__main__":
    if len(sys.argv) > 1:
        arg = sys.argv[1]

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
            'Usage: python3 extract_financials.py \'{"file_path": "/path/to/report.pdf"}\''
        )
