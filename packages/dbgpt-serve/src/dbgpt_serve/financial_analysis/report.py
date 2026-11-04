"""Adapt extracted facts and calculations to the existing ReportData contract."""

from copy import deepcopy
from decimal import Decimal

from .calculations import EXPENSE_RATIOS, calculate


def build_report(extracted, run, file_record):
    year = extracted.get("report_year")
    if not year or extracted.get("_meta", {}).get("status") == "unsupported":
        raise ValueError("未识别到支持的年度财务表格；扫描件需要 OCR。")
    facts = deepcopy(extracted["facts"])
    for fact in facts:
        value = fact["normalizedValue"]
        fact["displayValue"] = (
            f"{Decimal(value):,.2f} 元" if value is not None else "未识别（待核对）"
        )
    calculations = calculate(facts, year)
    calc = {c["code"]: c for c in calculations if c["fiscalPeriod"] == year}
    prior = str(int(year) - 1)
    expense_rates = dict(EXPENSE_RATIOS.values())
    rate_codes = {"gross_margin": "毛利率", **expense_rates}
    current = {f["metricCode"]: f for f in facts if f["fiscalPeriod"] == year}
    company = extracted.get("company_name") or "未识别公司名称"
    evidence = deepcopy(extracted["evidence"])
    # Short labels keep the existing citation UI readable; references stay exact.
    labels = {item["id"]: f"E{i}" for i, item in enumerate(evidence, 1)}
    for item in evidence:
        item["id"] = labels[item["id"]]
    for fact in facts:
        fact["evidenceExcerptIds"] = [labels[e] for e in fact["evidenceExcerptIds"]]
    document = dict(
        extracted["document"],
        fileName=file_record.display_name,
        fileId=file_record.file_id,
        sizeBytes=file_record.size_bytes,
        reportType="年度报告",
        fiscalPeriod=year,
        version="上传原件",
    )
    metrics = []
    for code in [
        "revenue",
        "net_profit",
        "non_recurring_net_profit",
        "operating_cash_flow",
    ]:
        fact = current[code]
        metrics.append(
            {
                "id": "metric-" + code,
                "code": code,
                "name": fact["metricName"],
                "displayValue": fact["displayValue"],
                "informationKind": "fact",
                "factIds": [fact["id"]],
                "calculationId": calc[code + "_yoy"]["id"],
                "changeDisplay": calc[code + "_yoy"]["displayResult"],
                "changeLabel": "同比",
                "citationLabel": "查看计算与来源",
            }
        )
    periods = sorted({f["fiscalPeriod"] for f in facts}, reverse=True)

    def trend(codes, divisor):
        return [
            {
                "year": f["fiscalPeriod"],
                "metric": f["metricName"],
                "value": float(Decimal(f["normalizedValue"]) / divisor),
            }
            for f in sorted(facts, key=lambda f: f["fiscalPeriod"])
            if f["metricCode"] in codes and f["normalizedValue"] is not None
        ]

    available = [f for f in facts if f["normalizedValue"] is not None]
    coverage = (
        round(
            100
            * sum(bool(f["evidenceExcerptIds"]) for f in available)
            / len(available),
            2,
        )
        if available
        else 0
    )
    steps = [
        {
            "id": code,
            "order": i,
            "type": kind,
            "title": title,
            "detail": detail,
            "status": "completed",
            "capability": "existing",
        }
        for i, (code, kind, title, detail) in enumerate(
            [
                ("read", "read", "读取上传 PDF", file_record.display_name),
                (
                    "extract",
                    "python",
                    "提取带来源的财务事实",
                    f"读取 {document['pageCount']} 页，获得 {len(available)} 个可用值；"
                    "自动结果待核对。",
                ),
                (
                    "calculate",
                    "python",
                    "执行确定性计算",
                    "使用十进制金额；缺失输入、口径不符或零分母不计算。",
                ),
                (
                    "save",
                    "analysis",
                    "保存报告快照",
                    "事实、计算和引用已保存，可刷新重新读取。",
                ),
            ],
            1,
        )
    ]
    return {
        "schemaVersion": 1,
        "revision": run["id"] + "-1",
        "mode": "report",
        "report": {
            "id": "report-" + run["id"],
            "companyName": company,
            "shortName": company,
            "stockCode": "",
            "title": year + " 年年度财务数据",
            "fiscalPeriod": year,
            "statementScope": "合并报表",
            "currency": "人民币",
            "sourceDocumentIds": [document["id"]],
            "run": {
                "id": run["id"],
                "agentName": "财报分析",
                "modelName": "确定性提取与计算",
                "skillName": "financial-report-analyzer",
                "status": "completed",
                "evidenceCoverage": coverage,
                "completedAt": run["completed_at"],
            },
        },
        "documents": [document],
        "facts": facts,
        "evidence": evidence,
        # Keep alternate bases for audit/JSON export, outside the canonical facts
        # and model context. Old snapshots need no migration or regeneration.
        "extractionAudit": {
            "observations": deepcopy(
                [
                    item
                    for item in extracted.get("sourceObservations", [])
                    if item["sourcePeriod"]["role"] == "opening"
                    or item["sourcePeriod"]["adjustment"] == "before"
                ]
            ),
            "tableIssues": deepcopy(extracted.get("_meta", {}).get("tableIssues", [])),
        },
        "calculations": calculations,
        "metrics": metrics,
        "findings": [],
        "steps": steps,
        "trends": {
            "revenue": trend({"revenue"}, Decimal(100000000)),
            "cashFlow": trend(
                {"net_profit", "operating_cash_flow"}, Decimal(100000000)
            ),
            "profit": trend({"net_profit", "non_recurring_net_profit"}, Decimal(10000)),
            "expenses": [
                {
                    "expense": expense_rates[c["code"]],
                    "year": c["fiscalPeriod"],
                    "value": float(Decimal(c["result"])),
                    "calculationId": c["id"],
                }
                for c in calculations
                if c["code"] in expense_rates and c["result"] is not None
            ],
            "financialUnit": "亿元",
            "profitUnit": "万元",
        },
        "sections": {
            "overview": {"findingIds": []},
            "profitability": {
                "title": "盈利质量",
                "description": "展示披露事实及计算结果，分析结论尚未生成。",
                "findingIds": [],
                "calculationIds": [
                    calc[k]["id"] for k in ["nonrecurring_impact", "nonrecurring_share"]
                ],
                "rateComparisons": [
                    {
                        "id": code,
                        "name": label,
                        "currentCalculationId": f"calc-{code}-{year}",
                        "previousCalculationId": f"calc-{code}-{prior}",
                        "changeCalculationId": f"calc-{code}_change-{year}",
                    }
                    for code, label in rate_codes.items()
                ],
                "comparisonLabel": f"{year} 年较 {prior} 年",
            },
            "cashflow": {
                "findingIds": [],
                "calculationIds": [calc["cash_profit_ratio"]["id"]],
            },
            "balance": {
                "description": year + " 年末 · 合并报表",
                "findingIds": [],
                "factIds": [
                    current[k]["id"]
                    for k in [
                        "total_assets",
                        "total_liabilities",
                        "current_assets",
                        "current_liabilities",
                        "inventory",
                    ]
                    if k in current
                ],
            },
        },
        "healthMetrics": [
            {
                "id": code,
                "name": calc[code]["name"],
                "displayValue": calc[code]["displayResult"],
                "selection": {"calculationId": calc[code]["id"]},
            }
            for code in ["debt_ratio", "cash_profit_ratio", "current_ratio"]
        ],
        "statements": {
            "unit": "元",
            "periods": [{"period": p, "label": p + " 年"} for p in periods],
            "rows": [
                {
                    "id": code,
                    "name": fact["metricName"],
                    "factIds": [f["id"] for f in facts if f["metricCode"] == code],
                }
                for code, fact in current.items()
            ],
        },
        "artifacts": [],
        "agent": {
            "userQuery": "分析上传的年度报告，提取财务事实并计算核心指标。",
            "summary": f"已完成 {company} {year} 年报的事实提取与计算。\n\n"
            "数字保留来源，自动提取结果待人工核对。模型分析和追问将在后续接入。",
            "groups": [
                {
                    "id": "data",
                    "title": "财务数据处理",
                    "content": "读取、提取、计算与保存",
                    "stepIds": [s["id"] for s in steps],
                }
            ],
        },
    }
