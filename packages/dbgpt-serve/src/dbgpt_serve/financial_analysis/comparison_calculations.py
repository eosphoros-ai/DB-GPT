"""Exact comparisons with complete, flattened source-fact provenance."""

from decimal import Decimal, InvalidOperation, localcontext

from .comparison_alignment import CORE_METRICS
from .comparison_schema import FORMULA_VERSION, POLICY_VERSION, decimal_value, stable_id

RATIOS = {
    "gross_margin": ("毛利率", ["revenue", "cost_of_sales"], "%"),
    "selling_expense_ratio": ("销售费用率", ["selling_expenses", "revenue"], "%"),
    "administrative_expense_ratio": (
        "管理费用率",
        ["administrative_expenses", "revenue"],
        "%",
    ),
    "research_expense_ratio": ("研发费用率", ["research_expenses", "revenue"], "%"),
    "financial_expense_ratio": ("财务费用率", ["financial_expenses", "revenue"], "%"),
    "cash_profit_ratio": ("现金利润比", ["operating_cash_flow", "net_profit"], "×"),
    "debt_ratio": ("资产负债率", ["total_liabilities", "total_assets"], "%"),
}


def _ratio(code, values):
    if code == "gross_margin":
        return (values[0] - values[1]) / values[0] * 100
    return values[0] / values[1] * (100 if RATIOS[code][2] == "%" else 1)


def calculate_comparison(aligned, config):
    entity_names = {e["id"]: e["name"] for e in aligned["entities"]}
    facts = {f["id"]: f for f in aligned["facts"]}
    cells = aligned["cells"]
    index = {(c["entityId"], c["period"], c["metricCode"]): c for c in cells}
    calculations = []

    def inputs(entity, period, code):
        codes = RATIOS[code][1] if code in RATIOS else [code]
        selected = [index.get((entity, period, c)) for c in codes]
        refs = [facts[c["factId"]] for c in selected if c and c.get("factId")]
        reason = next(
            (
                c["selectionReason"]
                if c["dataStatus"] != "available"
                else ",".join(c["comparability"]["reasons"])
                for c in selected
                if c
                and (
                    c["dataStatus"] != "available"
                    or c["comparability"]["status"] != "comparable"
                )
            ),
            None,
        )
        if len(refs) != len(codes):
            reason = reason or "missing_input"
        return refs, reason

    def trace(code, name, refs, operation, unit, formula, reason=None, **roles):
        result = None
        if not reason:
            try:
                with localcontext() as context:
                    context.prec = 38
                    result = operation([Decimal(f["normalizedValue"]) for f in refs])
            except (ZeroDivisionError, InvalidOperation):
                reason = "zero_denominator"
        entry = {
            "id": stable_id("calc", code, roles, [f["id"] for f in refs], config),
            "code": code,
            "name": name,
            "metricCode": roles.pop("metricCode", code),
            "kind": "deterministic",
            "formula": formula,
            "formulaVersion": FORMULA_VERSION,
            "policyVersion": POLICY_VERSION,
            "inputFactIds": list(dict.fromkeys(f["id"] for f in refs)),
            "inputCalculationIds": [],
            "result": format(result, "f") if result is not None else None,
            "displayResult": f"{result:,.2f} {unit}"
            if result is not None
            else "不可计算",
            "unit": unit,
            "status": "unavailable" if reason else "calculated",
            "reason": reason,
            "steps": [
                f"{entity_names[f['entityId']]} / {f['fiscalPeriod']} / "
                f"{f['metricName']}"
                f" = {f['normalizedValue']} {f['unit']}"
                for f in refs
            ]
            + ([reason] if reason else [f"结果 = {result} {unit}"]),
            **roles,
        }
        entry["fiscalPeriod"] = roles.get("subjectPeriod", roles.get("period", ""))
        if roles.get("comparisonType"):
            entry["direction"] = (
                "unavailable"
                if result is None
                else "higher"
                if result > 0
                else "lower"
                if result < 0
                else "equal"
            )
        calculations.append(entry)
        return entry

    for obj in aligned["objects"]:
        entity, period = obj["entityId"], obj["period"]
        for code, (name, codes, unit) in RATIOS.items():
            refs, reason = inputs(entity, period, code)
            formula = (
                "(营业收入 - 营业成本) / 营业收入 * 100"
                if code == "gross_margin"
                else " / ".join(CORE_METRICS.get(c, c) for c in codes)
                + (" * 100" if unit == "%" else "")
            )
            calc = trace(
                code,
                name,
                refs,
                lambda values, c=code: _ratio(c, values),
                unit,
                formula,
                reason,
                entityId=entity,
                period=period,
            )
            cell = {
                "id": stable_id("cell", entity, period, code),
                "entityId": entity,
                "period": period,
                "metricCode": code,
                "metricName": name,
                "dataStatus": "available"
                if calc["result"] is not None
                else ("conflict" if reason and "conflict" in reason else "missing"),
                "factId": None,
                "calculationId": calc["id"],
                "candidateFactIds": [f["id"] for f in refs],
                "selectionReason": reason or "deterministic_formula",
                "policyVersion": POLICY_VERSION,
                "comparability": {
                    "status": "incomparable" if reason else "comparable",
                    "rules": ["compatible_formula_inputs"],
                    "reasons": [reason] if reason else [],
                },
            }
            cells.append(cell)
    if not aligned["comparisonReady"]:
        return calculations
    baseline_entity = aligned["baselineEntityId"]
    ordered = sorted(aligned["objects"], key=lambda o: o["period"])
    relations = []
    for position, obj in enumerate(ordered):
        entity, period = obj["entityId"], obj["period"]
        base_period = period if config["kind"] == "peer" else aligned["baselinePeriod"]
        if (entity, period) != (baseline_entity, base_period):
            relations.append(
                (entity, period, baseline_entity, base_period, "difference")
            )
        if config["kind"] == "trend" and position:
            relations.append(
                (entity, period, entity, ordered[position - 1]["period"], "growth")
            )
    for entity, period, base_entity, base_period, comparison_type in relations:
        for code in [
            "revenue",
            "net_profit",
            "non_recurring_net_profit",
            "operating_cash_flow",
            *RATIOS,
        ]:
            left, left_reason = inputs(entity, period, code)
            right, right_reason = inputs(base_entity, base_period, code)
            reason = left_reason or right_reason
            if config["kind"] == "trend" and not reason:
                for metric in RATIOS[code][1] if code in RATIOS else [code]:
                    a = next(f for f in left if f["metricCode"] == metric)
                    b = next(f for f in right if f["metricCode"] == metric)
                    # A continuous trend needs one disclosure containing both
                    # selected values on the same restatement basis.
                    a_docs = {
                        f["sourceDocumentId"]
                        for f in aligned["facts"]
                        if (f["entityId"], f["metricCode"], f["fiscalPeriod"])
                        == (entity, metric, period)
                        and decimal_value(f.get("normalizedValue"))
                        == decimal_value(a["normalizedValue"])
                        and f.get("adjustment") != "before"
                    }
                    b_docs = {
                        f["sourceDocumentId"]
                        for f in aligned["facts"]
                        if (f["entityId"], f["metricCode"], f["fiscalPeriod"])
                        == (entity, metric, base_period)
                        and decimal_value(f.get("normalizedValue"))
                        == decimal_value(b["normalizedValue"])
                        and f.get("adjustment") != "before"
                    }
                    if not a_docs & b_docs:
                        reason = "trend_basis_gap"
            ratio = code in RATIOS
            if comparison_type == "growth" and ratio:
                continue
            name = (
                RATIOS[code][0]
                if ratio
                else next(c["metricName"] for c in cells if c["metricCode"] == code)
            )
            split = len(left)

            def difference(values, metric=code, count=split):
                a, b = values[:count], values[count:]
                return (
                    _ratio(metric, a) - _ratio(metric, b)
                    if metric in RATIOS
                    else a[0] - b[0]
                )

            roles = {
                "subjectEntityId": entity,
                "baselineEntityId": base_entity,
                "subjectPeriod": period,
                "baselinePeriod": base_period,
                "comparisonType": "difference",
                "metricCode": code,
                "inputRoles": {
                    "subjectFactIds": [f["id"] for f in left],
                    "baselineFactIds": [f["id"] for f in right],
                },
            }
            unit = (
                "百分点" if ratio and RATIOS[code][2] == "%" else "×" if ratio else "元"
            )
            if comparison_type == "difference":
                trace(
                    code + "_difference",
                    name + "差额",
                    left + right,
                    difference,
                    unit,
                    "对象值 - 基准值（比率先用原始事实精确计算）",
                    reason,
                    **roles,
                )
            else:
                roles["comparisonType"] = "growth"
                if int(period) != int(base_period) + 1:
                    reason = "nonconsecutive_periods"
                calc = trace(
                    code + "_growth",
                    name + "同比",
                    left + right,
                    lambda values: (values[0] - values[1]) / abs(values[1]) * 100,
                    "%",
                    "(本期 - 上期) / abs(上期) * 100",
                    reason,
                    **roles,
                )
                if right and decimal_value(right[0]["normalizedValue"]) < 0:
                    calc["steps"].append(
                        "负基数按绝对值计算；不能据此等同通常正基数增长。"
                    )
    return calculations
