"""Compose a data-ready report before any optional model analysis."""

from .comparison_alignment import align
from .comparison_calculations import calculate_comparison
from .comparison_schema import validate_snapshot


def build_comparison(members, run, config, resolutions=None):
    aligned = align(members, config, resolutions)
    for index, excerpt in enumerate(aligned["evidence"], 1):
        excerpt["label"] = "E" + str(index)
    calculations = calculate_comparison(aligned, config)
    entities = aligned["entities"]
    periods = aligned["periods"]
    label = "横向对比" if config["kind"] == "peer" else "跨年对比"
    title = "、".join(e["name"] for e in entities) + " · " + label
    stage = "data_ready" if aligned["comparisonReady"] else "needs_selection"
    failed = [m for m in members if m["status"] in {"failed", "interrupted"}]
    report = {
        "schemaVersion": 2,
        "mode": "comparison",
        "revision": run["id"] + "-data-" + run["token"],
        "comparison": {
            "kind": config["kind"],
            "title": title,
            "entities": entities,
            "periods": periods,
            "objects": aligned["objects"],
            "baselineEntityId": aligned["baselineEntityId"],
            "baselinePeriod": aligned["baselinePeriod"],
            "policyVersion": config["policy_version"],
            "formulaVersion": config["formula_version"],
            "config": config,
            "cells": aligned["cells"],
            "clarifications": aligned["clarifications"],
            "ready": aligned["comparisonReady"],
            "limitations": [
                "自动提取待核对；财务定义可比较不代表业务结构或行业相同。",
                "不根据指标高低评定企业优劣；没有附注支持时不推断变化原因。",
                "跨年关系逐对检查共同披露基础；缺口保留为断点。",
            ],
        },
        "lifecycle": {
            "dataStatus": "ready" if aligned["comparisonReady"] else "incomplete",
            "analysisStatus": "pending",
            "publicationStatus": "draft",
            "stage": stage,
        },
        # Shared workspace metadata deliberately has no single-company identity.
        "report": {
            "id": "report-" + run["id"],
            "title": title,
            "fiscalPeriod": " / ".join(periods),
            "statementScope": "合并报表",
            "currency": "人民币",
            "sourceDocumentIds": [d["id"] for d in aligned["documents"]],
            "run": {
                "id": run["id"],
                "agentName": "财报对比分析",
                "modelName": run.get("model", ""),
                "skillName": "financial-report-analyzer",
                "status": "completed",
                "evidenceCoverage": 0,
                "startedAt": run["started_at"],
                "completedAt": run["completed_at"],
            },
        },
        "documents": aligned["documents"],
        "facts": aligned["facts"],
        "evidence": aligned["evidence"],
        "calculations": calculations,
        "findings": [],
        "metrics": [],
        "members": [
            {
                k: m.get(k)
                for k in (
                    "file_id",
                    "file_name",
                    "status",
                    "error",
                    "sha256",
                    "extractor_version",
                    "started_at",
                    "completed_at",
                )
            }
            for m in members
        ],
        "steps": [
            {
                "id": "document-" + m["file_id"],
                "order": i + 1,
                "type": "read",
                "title": m["file_name"],
                "detail": m.get("error") or "已保存提取结果",
                "status": "completed" if m["status"] == "completed" else "failed",
                "capability": "existing",
                "startedAt": m.get("started_at"),
                "completedAt": m.get("completed_at"),
            }
            for i, m in enumerate(members)
        ],
        "sections": {
            key: {
                "findingIds": [],
                "factIds": [],
                "calculationIds": [],
                "description": "文件提取存在失败，已保留可用资料。" if failed else "",
            }
            for key in ("overview", "profitability", "cashflow", "balance")
        },
        "artifacts": [],
        "agent": {
            "userQuery": label,
            "summary": "财务数据已保存，分析尚未发布。",
            "groups": [
                {
                    "id": "data",
                    "title": "文档提取与对齐",
                    "content": "每份文件独立保存",
                    "stepIds": ["document-" + m["file_id"] for m in members],
                }
            ],
        },
    }
    return validate_snapshot(report)
