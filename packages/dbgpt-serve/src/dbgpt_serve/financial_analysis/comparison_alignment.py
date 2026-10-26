"""Auditable selection over immutable source facts, never over model narrative."""

import re
from collections import defaultdict
from copy import deepcopy

from .comparison_schema import POLICY_VERSION, decimal_value, stable_id

CORE_METRICS = {
    "revenue": "营业收入",
    "net_profit": "归母净利润",
    "non_recurring_net_profit": "扣非归母净利润",
    "operating_cash_flow": "经营现金流",
    "cost_of_sales": "营业成本",
    "selling_expenses": "销售费用",
    "administrative_expenses": "管理费用",
    "research_expenses": "研发费用",
    "financial_expenses": "财务费用",
    "total_assets": "总资产",
    "total_liabilities": "总负债",
    "current_assets": "流动资产",
    "current_liabilities": "流动负债",
    "inventory": "存货",
    "equity": "归母净资产",
}
BALANCES = {
    "total_assets",
    "total_liabilities",
    "current_assets",
    "current_liabilities",
    "inventory",
    "equity",
}


def identity(extracted, file_id, resolution=None):
    resolution = resolution or {}
    metadata = extracted.get("company_identity", {})
    names = metadata.get("candidates") or [extracted.get("company_name")]
    names = sorted({re.sub(r"\s+", "", n) for n in names if n})
    company = resolution.get("company_name")
    name = company or (names[0] if len(names) == 1 else None)
    year = resolution.get("report_year") or extracted.get("report_year")
    if not re.fullmatch(r"20\d{2}", str(year or "")):
        year = None
    return {
        "name": name,
        "period": year,
        "status": "resolved" if name and year else "ambiguous",
        "candidates": names,
        "basis": metadata.get("basis", "extracted_cover_text"),
        "evidence": metadata.get("evidence", []),
        "resolution": resolution or None,
        "fileId": file_id,
    }


def _facts(extracted, entity_id):
    """Retain observations including conflicting and pre-restatement values."""
    templates = {(f["metricCode"], f["fiscalPeriod"]): f for f in extracted["facts"]}
    observations = extracted.get("sourceObservations", [])
    result = []
    observed = set()
    for observation in observations:
        key = observation["metricCode"], observation["fiscalPeriod"]
        template = templates.get(key)
        if not template:
            continue
        fact = deepcopy(template)
        evidence = observation["evidence"]
        source_period = observation.get("sourcePeriod", {})
        value = observation.get("normalizedValue")
        fact.update(
            id=stable_id("fact", entity_id, evidence["id"]),
            entityId=entity_id,
            sourceDocumentId=extracted["document"]["id"],
            rawValue=observation["rawValue"],
            normalizedValue=value if decimal_value(value) is not None else None,
            evidenceExcerptIds=[evidence["id"]],
            sourcePeriods=[source_period],
            sourceUnits=[observation.get("sourceUnit")],
            sourceCurrency=evidence.get("sourceCurrency"),
            extractionStatus="parsed" if value is not None else "missing",
            adjustment=source_period.get("adjustment", "unspecified"),
            sourceRole=source_period.get("role", "annual"),
        )
        observed.add(key)
        result.append(fact)
    for key, template in templates.items():
        if key in observed:
            continue
        fact = deepcopy(template)
        periods = fact.get("sourcePeriods") or [{}]
        fact.update(
            entityId=entity_id,
            sourceDocumentId=extracted["document"]["id"],
            adjustment=periods[0].get("adjustment", "unspecified"),
            sourceRole=periods[0].get(
                "role", "closing" if fact.get("periodType") == "instant" else "annual"
            ),
        )
        result.append(fact)
    for fact in result:
        year = fact["fiscalPeriod"]
        instant = fact.get("periodType") == "instant"
        fact["periodStart"] = None if instant else year + "-01-01"
        fact["periodEnd"] = year + "-12-31"
        fact["asOf"] = year + "-12-31" if instant else None
        value = decimal_value(fact.get("normalizedValue"))
        fact["displayValue"] = f"{value:,.2f} 元" if value is not None else "缺失"
        fact["policyVersion"] = POLICY_VERSION
    return result


def fact_basis(fact):
    return tuple(
        fact.get(k)
        for k in (
            "currency",
            "unit",
            "statementScope",
            "attribution",
            "periodType",
            "periodStart",
            "periodEnd",
            "asOf",
        )
    )


def select_cell(entity_id, period, code, facts):
    candidates = [
        f
        for f in facts
        if (f["entityId"], f["fiscalPeriod"], f["metricCode"])
        == (entity_id, period, code)
    ]
    valid = [
        f
        for f in candidates
        if decimal_value(f.get("normalizedValue")) is not None
        and f.get("sourceRole") != "opening"
        and f.get("adjustment") != "before"
    ]
    selected, reason = None, "missing_input"
    status = "missing"
    if valid:
        bases = {fact_basis(f) for f in valid}
        values = {decimal_value(f["normalizedValue"]) for f in valid}
        after = [f for f in valid if f.get("adjustment") == "after"]
        # An explicit before/after pair is the only override of unequal sources.
        restated = [
            f
            for f in after
            if any(
                c["sourceDocumentId"] == f["sourceDocumentId"]
                and c.get("adjustment") == "before"
                and c.get("sourceRole") == f.get("sourceRole")
                and fact_basis(c) == fact_basis(f)
                for c in candidates
            )
        ]
        if len(bases) != 1:
            status, reason = "conflict", "conflicting_basis"
        elif len(values) == 1:
            selected = sorted(valid, key=lambda f: f["id"])[0]
            status, reason = "available", "equal_disclosures"
        elif (
            restated
            and len({decimal_value(f["normalizedValue"]) for f in restated}) == 1
            and values
            <= {
                decimal_value(c.get("normalizedValue"))
                for c in candidates
                if c.get("adjustment") in {"before", "after"}
                and any(
                    c["sourceDocumentId"] == f["sourceDocumentId"] for f in restated
                )
            }
        ):
            selected = sorted(restated, key=lambda f: f["id"])[0]
            status, reason = "available", "explicit_paired_restatement"
        else:
            status, reason = "conflict", "unexplained_conflicting_values"
    elif any(f.get("extractionStatus") == "conflict" for f in candidates):
        status, reason = "conflict", "unexplained_conflicting_values"
    return {
        "id": stable_id("cell", entity_id, period, code),
        "entityId": entity_id,
        "period": period,
        "metricCode": code,
        "metricName": CORE_METRICS.get(code, code),
        "dataStatus": status,
        "factId": selected["id"] if selected else None,
        "calculationId": None,
        "candidateFactIds": [f["id"] for f in candidates],
        "selectionReason": reason,
        "policyVersion": POLICY_VERSION,
        "comparability": {"status": "unchecked", "rules": [], "reasons": []},
    }


def align(members, config, resolutions=None):
    entities, documents, facts, evidence, clarifications = [], [], [], [], []
    entity_index = {}
    for member in members:
        extracted = member.get("extracted")
        if not extracted:
            continue
        found = identity(
            extracted, member["file_id"], (resolutions or {}).get(member["file_id"])
        )
        if found["status"] != "resolved":
            clarifications.append(found)
            continue
        name, period = found["name"], found["period"]
        if name not in entity_index:
            entity_index[name] = stable_id("entity", name)
            entities.append(
                {
                    "id": entity_index[name],
                    "name": name,
                    "identityStatus": "resolved",
                    "identifications": [],
                }
            )
        entity_id = entity_index[name]
        entity = next(e for e in entities if e["id"] == entity_id)
        entity["identifications"].append(found)
        document = dict(
            extracted["document"],
            fileId=member["file_id"],
            fileName=member["file_name"],
            fiscalPeriod=period,
            entityId=entity_id,
            reportType="年度报告",
            version="上传原件",
            extractorVersion=member["extractor_version"],
        )
        documents.append(document)
        facts.extend(_facts(extracted, entity_id))
        evidence.extend(deepcopy(extracted["evidence"]))
        evidence.extend(
            deepcopy(o["evidence"]) for o in extracted.get("sourceObservations", [])
        )
    periods = sorted({d["fiscalPeriod"] for d in documents})
    if config["kind"] == "peer":
        if len(periods) > 1:
            clarifications.append({"reason": "peer_requires_same_report_year"})
        objects = [
            {"entityId": e["id"], "period": p}
            for e in entities
            for p in periods
            if any(
                d["entityId"] == e["id"] and d["fiscalPeriod"] == p for d in documents
            )
        ]
        comparable = len(entities) >= 2 and len(periods) == 1
    else:
        if len(entities) > 1:
            clarifications.append({"reason": "trend_requires_same_company"})
        objects = [
            {"entityId": e["id"], "period": p} for e in entities for p in periods
        ]
        comparable = len(entities) == 1 and len(periods) >= 2
    cells = [
        select_cell(o["entityId"], o["period"], code, facts)
        for o in objects
        for code in CORE_METRICS
    ]
    baseline = next(
        (d for d in documents if d["fileId"] == config.get("baseline_file_id")), None
    )
    if not baseline and documents:
        baseline = (
            min(documents, key=lambda d: d["fiscalPeriod"])
            if config["kind"] == "trend"
            else documents[0]
        )
    groups = defaultdict(list)
    for cell in cells:
        groups[cell["metricCode"]].append(cell)
    fact_map = {f["id"]: f for f in facts}
    for group in groups.values():
        usable = [fact_map[c["factId"]] for c in group if c["factId"]]
        # Period dates deliberately differ in trend mode, but types must agree.
        bases = {fact_basis(f)[:5] for f in usable}
        for cell in group:
            reasons = []
            if not comparable or clarifications:
                reasons.append("comparison_objects_unresolved")
            if len(bases) > 1:
                reasons.append("incompatible_basis")
            if cell["dataStatus"] != "available":
                reasons.append(cell["selectionReason"])
            if cell["factId"]:
                fact = fact_map[cell["factId"]]
                expected_type = "instant" if cell["metricCode"] in BALANCES else "flow"
                attribution = (
                    "owners_of_parent"
                    if cell["metricCode"]
                    in {"net_profit", "non_recurring_net_profit", "equity"}
                    else "consolidated"
                )
                if (
                    fact.get("currency"),
                    fact.get("unit"),
                    fact.get("statementScope"),
                    fact.get("periodType"),
                    fact.get("attribution"),
                ) != ("CNY", "元", "合并", expected_type, attribution):
                    reasons.append("unsupported_basis")
            cell["comparability"] = {
                "status": "incomparable" if reasons else "comparable",
                "rules": [
                    "currency",
                    "scope",
                    "attribution",
                    "period_type",
                    POLICY_VERSION,
                ],
                "reasons": reasons,
            }
    return {
        "entities": entities,
        "documents": documents,
        "facts": facts,
        "evidence": list({e["id"]: e for e in evidence}.values()),
        "objects": objects,
        "periods": periods,
        "cells": cells,
        "clarifications": clarifications,
        "baselineEntityId": baseline["entityId"] if baseline else None,
        "baselinePeriod": baseline["fiscalPeriod"] if baseline else None,
        "comparisonReady": comparable and not clarifications,
    }
