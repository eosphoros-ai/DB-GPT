"""SYNTHETIC financial data; never real filings or human gold labels."""

import hashlib
from copy import deepcopy


def extracted(company="合成甲股份有限公司", year="2024", values=None, token="a"):
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
    return {
        "kind": kind,
        "baseline_file_id": baseline,
        "policy_version": "paired-disclosure-v1",
        "formula_version": "decimal-v1",
    }
