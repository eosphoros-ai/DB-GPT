"""Sectional state transitions and validation over one saved extraction."""

import json
from copy import deepcopy
from datetime import datetime, timezone
from uuid import uuid4

from dbgpt_serve.session_file.api.endpoints import SessionFileApiError

from .analysis import (
    REFERENCE,
    InvalidFindings,
    _render_text,
    apply_findings,
    model_context,
    validate_findings,
)
from .summary import report_summary

TOPICS = {
    "operating": (
        "经营表现",
        "overview",
        {"revenue", "net_profit"},
        "比较收入与利润变化是否同步，指出现象与解释边界。",
    ),
    "recurring": (
        "扣非与利润构成",
        "profitability",
        {"net_profit", "non_recurring_net_profit"},
        "比较归母与扣非利润，分析非经常性影响，不编造损益项目。",
    ),
    "margins": (
        "毛利变化",
        "profitability",
        {"revenue", "cost_of_sales"},
        "比较本期与上期毛利率，区分变化事实和待查原因。",
    ),
    "expenses": (
        "费用变化",
        "profitability",
        {
            "revenue",
            "selling_expenses",
            "administrative_expenses",
            "research_expenses",
            "financial_expenses",
        },
        "分别分析可用费用率及百分点变动，识别负财务费用；分条解释，避免将所有指标挤入一条。",
    ),
    "cashflow": (
        "现金流与利润支撑",
        "cashflow",
        {"net_profit", "operating_cash_flow"},
        "比较现金流与利润及其变化，不能凭现金利润比推断具体回款原因。",
    ),
    "balance": (
        "资产负债与流动性",
        "balance",
        {
            "total_assets",
            "total_liabilities",
            "current_assets",
            "current_liabilities",
            "inventory",
        },
        "结合负债率、流动比率和可用余额描述结构；缺少债务期限与受限资产时不得宣称偿债安全。",
    ),
}
TERMINAL = {"ready", "reviewed", "insufficient", "failed"}


def stamp():
    return datetime.now(timezone.utc).isoformat()


def fail(message):
    raise SessionFileApiError(409, "WORKFLOW_INCOMPLETE", message)


def initialize(report):
    report["workflow"] = {
        "version": 1,
        "status": "draft",
        "publishedAt": None,
        "review": None,
        "history": [],
        "dataQuality": {
            "availableFacts": sum(
                f.get("normalizedValue") is not None for f in report["facts"]
            ),
            "missingFacts": [
                f["id"] for f in report["facts"] if f.get("normalizedValue") is None
            ],
            "unavailableCalculations": [
                {"id": c["id"], "name": c["name"], "reason": c.get("reason")}
                for c in report["calculations"]
                if c.get("status") != "calculated"
            ],
        },
        "topics": [
            {
                "id": key,
                "title": value[0],
                "section": value[1],
                "status": "pending",
                "attempts": 0,
                "failures": 0,
                "findingIds": [],
                "note": "尚未分析",
                "history": [],
            }
            for key, value in TOPICS.items()
        ],
    }
    quality = report["workflow"]["dataQuality"]
    report["steps"].append(
        {
            "id": "quality",
            "order": len(report["steps"]) + 1,
            "type": "analysis",
            "title": "检查已提取数据与计算缺口",
            "status": "completed",
            "capability": "existing",
            "detail": (
                f"可用事实 {quality['availableFacts']} 个；"
                f"不可计算 {len(quality['unavailableCalculations'])} 项。"
                "仅表示当前提取范围，不代表整份年报覆盖率。"
            ),
        }
    )
    report["agent"]["groups"][0]["stepIds"].append("quality")
    sync(report)
    return report


def topic_context(report, topic_id):
    if topic_id not in TOPICS:
        fail("未知分析专题。")
    title, section, codes, instructions = TOPICS[topic_id]
    context = model_context(report)
    ids = {f["id"] for f in report["facts"] if f["metricCode"] in codes}
    context["facts"] = [f for f in context["facts"] if f["id"] in ids]
    ids = {f["id"] for f in context["facts"]}
    context["calculations"] = [
        c for c in context["calculations"] if set(c["inputFactIds"]) <= ids
    ]
    evidence = {i for f in context["facts"] for i in f["evidenceExcerptIds"]}
    context["evidence"] = [e for e in context["evidence"] if e["id"] in evidence]
    available = {
        f["metricCode"]
        for f in report["facts"]
        if f["id"] in ids and f["fiscalPeriod"] == report["report"]["fiscalPeriod"]
    }
    required = (
        codes
        if topic_id not in {"expenses", "balance"}
        else (
            {"revenue"}
            if topic_id == "expenses"
            else {"total_assets", "total_liabilities"}
        )
    )
    missing = sorted(required - available)
    if topic_id == "expenses" and not available - {"revenue"}:
        missing.append("expense_data")
    for kind, key in (("fact", "facts"), ("calculation", "calculations")):
        for item in context[key]:
            item["reference"] = "{{" + kind + ":" + item["id"] + "}}"
    return {
        "topic_id": topic_id,
        "title": title,
        "section": section,
        "instructions": instructions
        + "有依据时形成两到三条互不重复的发现，给出判断、引用、反向信息和待核查事项。",
        "missingRequiredMetrics": missing,
        "data": context,
    }


def sync(report):
    workflow = report["workflow"]
    report["steps"] = [
        s
        for s in report["steps"]
        if not s["id"].startswith("topic-")
        and s["id"] not in {"analyze", "review", "publish"}
    ]
    for topic in workflow["topics"]:
        status = topic["status"]
        report["steps"].append(
            {
                "id": "topic-" + topic["id"],
                "order": len(report["steps"]) + 1,
                "type": "analysis",
                "title": topic["title"],
                "detail": topic["note"],
                "status": "completed"
                if status in {"ready", "reviewed", "insufficient"}
                else "failed"
                if status == "failed"
                else "pending"
                if status == "pending"
                else "running",
                "capability": "existing",
                "startedAt": topic.get("startedAt"),
                "completedAt": topic.get("completedAt"),
            }
        )
    for key, title, done in (
        ("review", "复核方向、口径与解释依据", workflow.get("review") is not None),
        ("publish", "汇总发布报告", workflow["status"] == "published"),
    ):
        report["steps"].append(
            {
                "id": key,
                "order": len(report["steps"]) + 1,
                "type": "analysis",
                "title": title,
                "detail": "已完成；结论仍待人工核对" if done else "等待专题完成",
                "status": "completed" if done else "pending",
                "capability": "existing",
            }
        )
    report["agent"]["groups"] = [
        g for g in report["agent"]["groups"] if g["id"] != "analysis"
    ] + [
        {
            "id": "analysis",
            "title": "专题分析与复核",
            "content": "逐专题保存，缺项明确说明",
            "stepIds": ["topic-" + t["id"] for t in workflow["topics"]]
            + ["review", "publish"],
        }
    ]
    report["agent"]["summary"] = report_summary(report)


def changed(report):
    report["revision"] = report["report"]["run"]["id"] + "-" + uuid4().hex[:12]
    report["analysis"].update(status="partial", completedAt=None)
    report["workflow"].update(status="draft", review=None, publishedAt=None)
    sync(report)
    return report


def topic(report, topic_id):
    if "workflow" not in report:
        fail("旧版报告未启用专题流程，请发起新分析。")
    for item in report["workflow"]["topics"]:
        if item["id"] == topic_id:
            return item
    fail("未知分析专题。")


def start_topic(report, topic_id, retry=False):
    item = topic(report, topic_id)
    # Refreshing unfinished work must not reset its repair budget or revision.
    if item["status"] in {"running", "needs_revision"}:
        return report
    if item["status"] in TERMINAL and not retry:
        return report
    if retry:
        item["failures"] = 0
    item.pop("review", None)
    item["issues"] = []
    item.update(
        status="running",
        startedAt=stamp(),
        completedAt=None,
        attempts=item["attempts"] + 1,
        note="正在基于当前专题数据分析",
    )
    return changed(report)


def save_topic(
    report,
    topic_id,
    findings=None,
    missing_reason="",
    patches=None,
    append_findings=None,
):
    item = topic(report, topic_id)
    if item["status"] not in {"running", "needs_revision"}:
        fail("请先读取该专题；重做已完成专题时显式指定 retry=true。")
    scoped = topic_context(report, topic_id)
    if patches is not None or append_findings is not None:
        if findings is not None or not item.get("draftFindings"):
            fail("局部修订需已有草稿，仅传 patches，不同时传 findings。")
        if patches is not None and not isinstance(patches, list):
            fail("patches 必须为字段修订对象数组。")
        if append_findings is not None and (
            not isinstance(append_findings, list)
            or not append_findings
            or any(not isinstance(f, dict) for f in append_findings)
        ):
            fail("append_findings 必须为非空发现对象数组。")
        findings = deepcopy(item["draftFindings"])
        seen = set()
        for patch in patches or []:
            if not isinstance(patch, dict):
                fail("patches 必须为字段修订对象数组。")
            index = patch.get("finding_index")
            changes = patch.get("changes")
            if (
                type(index) is not int
                or not 0 <= index < len(findings)
                or index in seen
                or not isinstance(changes, dict)
            ):
                fail("patches 需唯一、有效的 finding_index 和 changes 字段对象。")
            seen.add(index)
            findings[index].update(changes)
        findings.extend(deepcopy(append_findings or []))
    # Raw drafts are repair-only. Display/publication uses validated findings.
    if findings:
        item["draftFindings"] = deepcopy(findings)
    item["saveAttempts"] = item.get("saveAttempts", 0) + 1
    if not findings:
        if not missing_reason or not scoped["missingRequiredMetrics"]:
            fail("现有数据可用于分析，不能用空结论跳过；缺项时需说明不足。")
        note = _render_text(missing_reason, {}, {}, set())
        accepted = []
    else:
        try:
            accepted, _ = validate_findings(
                json.dumps({"findings": findings}, ensure_ascii=False),
                report,
                strict=True,
                section=item["section"],
                allowed_fact_ids={f["id"] for f in scoped["data"]["facts"]},
            )
            if topic_id == "expenses":
                # Coverage needs narrative support, not unused IDs attached merely
                # to satisfy a checklist. Calculations contribute their inputs.
                used = {
                    ref
                    for f in findings
                    for ref in REFERENCE.findall(
                        f["summary"].replace("{{calc-", "{{calculation:calc-")
                    )
                }
                referenced = {ref for kind, ref in used if kind == "fact"}
                for calculation in report["calculations"]:
                    if ("calculation", calculation["id"]) in used:
                        referenced.update(calculation["inputFactIds"])
                available = {
                    f["metricCode"]
                    for f in report["facts"]
                    if f["id"] in {x["id"] for x in scoped["data"]["facts"]}
                }
                covered = {
                    f["metricCode"] for f in report["facts"] if f["id"] in referenced
                }
                missing = sorted(available - covered - {"revenue"})
                if missing:
                    metric_codes = {f["id"]: f["metricCode"] for f in report["facts"]}
                    raise InvalidFindings(
                        ["incomplete_topic_coverage"],
                        [
                            {
                                "field": "findings",
                                "code": "incomplete_topic_coverage",
                                "missing_metrics": missing,
                                "missing_facts": [
                                    {**f, "metricCode": metric_codes[f["id"]]}
                                    for f in scoped["data"]["facts"]
                                    if metric_codes[f["id"]] in missing
                                ],
                                "hint": (
                                    "已有发现字段校验通过，但遗漏所列费用科目。"
                                    "仅用 append_findings 补充缺失科目的实质分析，"
                                    "保留已有草稿；或 patches 在已有发现中补充。"
                                    "不能只在 factIds 中挂引用而不分析该科目。"
                                ),
                            }
                        ],
                    )
        except (InvalidFindings, ValueError) as exc:
            item["failures"] += 1
            errors = getattr(exc, "details", None) or [{"code": str(exc)}]
            boundary_error = any(e["code"].startswith("unsupported_") for e in errors)
            coverage_error = any(
                e["code"] == "incomplete_topic_coverage" for e in errors
            )
            item.update(
                status="failed" if item["failures"] >= 3 else "needs_revision",
                note=(
                    "本专题尚未覆盖已提供的费用科目，请补充分析。"
                    if coverage_error
                    else "本专题结论超出当前证据的解释边界，需修订相关判断。"
                    if boundary_error
                    else (
                        "本专题结论格式或引用校验失败；不代表历史数据缺失。"
                        "可在执行过程中查看错误并单独重试。"
                    )
                ),
                errorCode="TOPIC_COVERAGE_INCOMPLETE"
                if coverage_error
                else "EXPLANATION_BOUNDARY_FAILED"
                if boundary_error
                else "FINDING_VALIDATION_FAILED",
                issues=errors,
                completedAt=stamp() if item["failures"] >= 3 else None,
            )
            item.setdefault("validationHistory", []).append(
                {
                    "at": stamp(),
                    "revision": report["revision"],
                    "issues": deepcopy(item["issues"]),
                    "errorCode": item["errorCode"],
                }
            )
            return changed(report)
        note = f"已保存 {len(accepted)} 条发现，等待复核；结论仍需人工核对。"
    item["history"].append(
        {
            "revision": report["revision"],
            "status": item["status"],
            "findings": [
                deepcopy(f) for f in report["findings"] if f["id"] in item["findingIds"]
            ],
        }
    )
    for index, finding in enumerate(accepted):
        finding["id"] = f"topic-{topic_id}-{index + 1}"
    kept = [f for f in report["findings"] if f["id"] not in item["findingIds"]]
    item.pop("review", None)
    item.update(
        status="ready" if accepted else "insufficient",
        note=note,
        findingIds=[f["id"] for f in accepted],
        completedAt=stamp(),
        issues=[],
        errorCode=None if accepted else "MISSING_REQUIRED_METRICS",
    )
    report = apply_findings(report, kept + accepted)
    return changed(report)


def advance_topic(report):
    """Hand off sequentially; never concurrently mutate a shared revision."""
    if report["workflow"]["status"] != "published":
        for item in report["workflow"]["topics"]:
            if item["status"] not in TERMINAL:
                return start_topic(report, item["id"])
    return report


def next_action(report, active_topic=None):
    """Derive the next legal tool from persisted state, including repair results."""
    flow = report["workflow"]
    args = {"run_id": report["report"]["run"]["id"]}
    if flow["status"] == "published":
        return None
    if active_topic:
        item = topic(report, active_topic)
        if item["status"] in {"running", "needs_revision"}:
            return {
                "tool": "save_financial_topic",
                "arguments": dict(
                    args, revision=report["revision"], topic_id=item["id"]
                ),
                "instructions": (
                    "使用当前专题数据修正 findings 后保存；"
                    "只有状态 ready 才表示结论已保存。"
                ),
            }
    for item in flow["topics"]:
        if item["status"] not in TERMINAL:
            return {
                "tool": "get_financial_topic",
                "arguments": dict(args, topic_id=item["id"]),
                "instructions": "继续此专题，不重做已保存专题，不重新解析 PDF。",
            }
    return {
        "tool": (
            "publish_financial_report"
            if flow.get("review")
            else "review_financial_report"
        ),
        "arguments": dict(args, revision=report["revision"]),
        "instructions": (
            "全部专题已处理，请逐项复核并补齐 reviews；"
            "失败和缺数据专题使用 insufficient，"
            "三项 Checked 表示已检查，不表示结论通过。"
            if not flow.get("review")
            else "各专题复核已完成，发布当前版本。"
        ),
    }


def review_report(report, reviews):
    if not isinstance(reviews, list) or any(not isinstance(r, dict) for r in reviews):
        fail("复核记录必须为对象数组。")
    workflow = report.get("workflow")
    if workflow and workflow["status"] == "published":
        fail("当前版本已发布，请先显式重做专题再复核。")
    if not workflow or any(t["status"] not in TERMINAL for t in workflow["topics"]):
        fail("请先逐专题保存结论或明确缺项，再复核。")
    ids = [r.get("topic_id") for r in reviews if isinstance(r, dict)]
    if len(ids) != len(TOPICS) or set(ids) != set(TOPICS):
        fail("复核必须逐项覆盖全部专题，不得遗漏或重复。")
    # Validate every record before changing anything. Review is the agent's
    # explicit assessment, never proof of semantic correctness or human review.
    for review in reviews:
        topic_id = review["topic_id"]
        if review.get("verdict") not in {"pass", "revise", "insufficient"}:
            fail(f"专题 {topic_id} 的 verdict 必须为 pass、revise 或 insufficient。")
        unchecked = [
            k
            for k in ("directionChecked", "scopeChecked", "causalityChecked")
            if review.get(k) is not True
        ]
        if unchecked:
            fail(
                f"专题 {topic_id} 的复核字段 {', '.join(unchecked)} 必须为布尔 true。"
                "这些字段记录该维度及其缺口已检查，不代表结论通过。"
                "失败或缺数据专题检查缺口后也应设为 true，使用 verdict=insufficient，"
                "并在 note 说明限制；不要只修改 note 的格式。"
            )
        item = topic(report, review["topic_id"])
        if review["verdict"] == "pass" and item["status"] in {"failed", "insufficient"}:
            fail("失败或缺数据专题不能标记复核通过。")
        if not isinstance(review.get("note"), str) or not review["note"].strip():
            fail("请说明每个专题的复核依据或需要修订的问题。")
        try:
            _render_text(review["note"], {}, {}, set())
        except ValueError as exc:
            fail(
                f"专题 {topic_id} 的 note 校验失败：{exc}。"
                "note 只写不含数字或占位符的具体复核依据。"
            )
    for review in reviews:
        item = topic(report, review["topic_id"])
        item["review"] = deepcopy(review)
        if review["verdict"] == "revise":
            item.update(status="needs_revision", note=review["note"])
        elif review["verdict"] == "pass":
            item["status"] = "reviewed"
        else:
            if item["status"] not in {"failed", "insufficient"}:
                item.update(
                    status="insufficient",
                    errorCode="REVIEW_INSUFFICIENT",
                    note="智能体复核认为依据不足，详见独立复核意见。",
                )
            # Preserve backend failure codes/details. Model opinion is not cause.
    report["revision"] = report["report"]["run"]["id"] + "-" + uuid4().hex[:12]
    workflow["review"] = {
        "at": stamp(),
        "items": deepcopy(reviews),
        "kind": "agent-review",
    }
    sync(report)
    return report


def publish(report):
    workflow = report.get("workflow")
    if (
        not workflow
        or not workflow.get("review")
        or any(
            t["status"] not in {"reviewed", "insufficient", "failed"}
            for t in workflow["topics"]
        )
    ):
        fail("各专题尚未完成分析与复核，请修订后再发布。")
    if workflow["status"] == "published":
        return report
    complete = all(t["status"] == "reviewed" for t in workflow["topics"])
    report["analysis"].update(
        status="completed" if complete else "partial",
        completedAt=stamp(),
        rejectedCount=sum(t["failures"] for t in workflow["topics"]),
    )
    workflow.update(status="published", publishedAt=stamp())
    report["revision"] = report["report"]["run"]["id"] + "-" + uuid4().hex[:12]
    workflow["history"].append(
        {
            "revision": report["revision"],
            "publishedAt": workflow["publishedAt"],
            "findings": deepcopy(report["findings"]),
            "review": deepcopy(workflow["review"]),
        }
    )
    sync(report)
    return report


def public_snapshot(report):
    """Keep repair drafts private to storage/model tools, including JSON exports."""
    result = deepcopy(report)
    for item in result.get("workflow", {}).get("topics", []):
        item.pop("draftFindings", None)
    return result
