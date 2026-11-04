import re
import json
import sys
import os


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
        text = read_file_content(file_path)
    except Exception as e:
        return {"error": True, "message": f"Failed to read file: {e}"}

    if not text or not text.strip():
        return {"error": True, "message": "File is empty or could not be parsed"}

    data = extract_from_text(text)

    # Add a summary of which fields were successfully extracted
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
            'Usage: python3 extract_financials.py \'{"file_path": "/path/to/report.pdf"}\''
        )
