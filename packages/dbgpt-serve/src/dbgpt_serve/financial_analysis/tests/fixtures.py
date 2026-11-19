"""SYNTHETIC financial data; never real filings or human gold labels."""

import hashlib
from copy import deepcopy


def extracted(company="合成甲股份有限公司", year="2024", values=None, token="a"):
    """Build synthetic normalized facts and their matching evidence references."""
    values = values or {
        "revenue": "1000.01",
        "net_profit": "100",
        "non_recurring_net_profit": "80",
        "operating_cash_flow": "120",
        "cost_of_sales": "600",
        "total_assets": "2000",
        "total_liabilities": "800",
        "selling_expenses": "20",
        "financial_expenses": "-5",
        "administrative_expenses": "30",
        "research_expenses": "10",
    }
    digest = hashlib.sha256(("%PDF synthetic " + token).encode()).hexdigest()
    document = {"id": "document-" + digest[:16], "sha256": digest, "pageCount": 3}
    facts, evidence = [], []
    for code, value in values.items():
        instant = code in {
            "total_assets",
            "total_liabilities",
            "current_assets",
            "current_liabilities",
            "inventory",
            "equity",
        }
        ev_id = document["id"] + "-" + code + "-" + year
        facts.append(
            {
                "id": document["id"] + "-" + code + "-" + year,
                "metricCode": code,
                "metricName": code,
                "rawValue": value or "",
                "normalizedValue": value,
                "displayValue": value or "缺失",
                "unit": "元",
                "currency": "CNY",
                "fiscalPeriod": year,
                "periodType": "instant" if instant else "flow",
                "statementScope": "合并",
                "attribution": "owners_of_parent"
                if code in {"net_profit", "non_recurring_net_profit", "equity"}
                else "consolidated",
                "sourcePeriods": [
                    {
                        "year": year,
                        "role": "closing" if instant else "annual",
                        "adjustment": "unspecified",
                    }
                ],
                "extractionStatus": "parsed" if value is not None else "missing",
                "evidenceExcerptIds": [ev_id],
                "qualityStatus": "warning",
            }
        )
        evidence.append(
            {
                "id": ev_id,
                "sourceDocumentId": document["id"],
                "page": 2,
                "snippet": "SYNTHETIC " + code + " " + str(value),
                "qualityStatus": "warning",
            }
        )
    return {
        "company_name": company,
        "report_year": year,
        "document": document,
        "facts": facts,
        "evidence": evidence,
        "_meta": {"status": "parsed", "synthetic": True},
    }


def member(data, file_id):
    """Wrap an extraction fixture as a completed comparison member."""
    return {
        "file_id": file_id,
        "file_name": file_id + ".pdf",
        "status": "completed",
        "sha256": data["document"]["sha256"],
        "extractor_version": "financial-document-v2",
        "error": None,
        "extracted": deepcopy(data),
    }


def report_config(kind="peer", baseline="a"):
    """Return the explicit policy versions used by comparison fixtures."""
    return {
        "kind": kind,
        "baseline_file_id": baseline,
        "policy_version": "paired-disclosure-v1",
        "formula_version": "decimal-v1",
    }


def annual_report_pdf():
    """Create a synthetic Chinese text PDF with a ruled two-year income table.

    Use a standard PDF CJK font and explicit object offsets, avoiding a PDF
    generation dependency while exercising the actual parser and cell geometry.
    """
    commands = []
    for x, y, text in [
        (30, 740, "合成股份有限公司"),
        (30, 715, "2024年年度报告"),
        (30, 680, "合并利润表"),
        (30, 660, "单位：元 币种：人民币"),
        (35, 620, "项目"),
        (215, 620, "2024年度"),
        (335, 620, "2023年度"),
        (35, 590, "营业收入"),
        (215, 590, "100.25"),
        (335, 590, "90.00"),
        (35, 560, "营业成本"),
        (215, 560, "40.00"),
        (335, 560, "30.00"),
    ]:
        encoded = text.encode("utf-16-be").hex()
        commands.append(f"BT /F1 12 Tf {x} {y} Td <{encoded}> Tj ET")
    for y in (550, 580, 610, 640):
        commands.append(f"30 {y} m 450 {y} l S")
    for x in (30, 210, 330, 450):
        commands.append(f"{x} 550 m {x} 640 l S")
    stream = ("\n".join(commands) + "\n").encode("ascii")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 6 0 R >>",
        b"<< /Type /Font /Subtype /Type0 /BaseFont /STSong-Light "
        b"/Encoding /UniGB-UCS2-H /DescendantFonts [5 0 R] >>",
        b"<< /Type /Font /Subtype /CIDFontType0 /BaseFont /STSong-Light "
        b"/CIDSystemInfo << /Registry (Adobe) /Ordering (GB1) /Supplement 4 >> >>",
        b"<< /Length "
        + str(len(stream)).encode("ascii")
        + b" >>\nstream\n"
        + stream
        + b"\nendstream",
    ]
    document = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for number, obj in enumerate(objects, 1):
        offsets.append(len(document))
        document.extend(f"{number} 0 obj\n".encode("ascii") + obj + b"\nendobj\n")
    xref = len(document)
    document.extend(f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode("ascii"))
    for offset in offsets[1:]:
        document.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    document.extend(
        (
            f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\n"
            f"startxref\n{xref}\n%%EOF\n"
        ).encode("ascii")
    )
    return bytes(document)
