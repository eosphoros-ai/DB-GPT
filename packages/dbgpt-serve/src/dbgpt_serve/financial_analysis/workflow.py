"""Sectional analysis over one saved extraction; no additional model or PDF run."""

import json
from copy import deepcopy
from datetime import datetime, timezone
from uuid import uuid4

from dbgpt_serve.session_file.api.endpoints import SessionFileApiError

from .analysis import (
    InvalidFindings,
    _render_text,
    apply_findings,
    model_context,
    validate_findings,
)

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
    counts = {
        s: sum(t["status"] == s for t in workflow["topics"])
        for s in {t["status"] for t in workflow["topics"]}
    }
    report["agent"]["summary"] = (
        f"已保存 {len(report['findings'])} 条专题发现；"
        f"{counts.get('ready', 0) + counts.get('reviewed', 0)} 个专题有分析，"
        f"{counts.get('insufficient', 0)} 个专题缺数据，"
        f"{counts.get('failed', 0)} 个专题失败。"
        + (
            "报告已发布，结论仍需人工核对。"
            if workflow["status"] == "published"
            else "报告尚未完成复核发布，可继续当前任务。"
        )
    )


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


def save_topic(report, topic_id, findings, missing_reason=""):
    item = topic(report, topic_id)
    if item["status"] not in {"running", "needs_revision"}:
        fail("请先读取该专题；重做已完成专题时显式指定 retry=true。")
    scoped = topic_context(report, topic_id)
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
            )
            allowed = {f["id"] for f in scoped["data"]["facts"]}
            if any(
                f["sectionKey"] != item["section"] or not set(f["factIds"]) <= allowed
                for f in accepted
            ):
                raise InvalidFindings(
                    ["结论必须属于当前专题并仅引用当前专题的数据"],
                    [{"field": "section/factIds", "code": "cross_topic_reference"}],
                )
        except (InvalidFindings, ValueError) as exc:
            item["failures"] += 1
            item.update(
                status="failed" if item["failures"] >= 3 else "needs_revision",
                note="本专题结论校验失败，其他专题已保存；可单独重试。",
                issues=getattr(exc, "details", None) or [{"code": str(exc)}],
                completedAt=stamp() if item["failures"] >= 3 else None,
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
    )
    report = apply_findings(report, kept + accepted)
    return changed(report)


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
        if review.get("verdict") not in {"pass", "revise", "insufficient"} or not all(
            review.get(k) is True
            for k in ("directionChecked", "scopeChecked", "causalityChecked")
        ):
            fail("每项复核需检查变化方向、期间口径和原因依据，并给出结论。")
        item = topic(report, review["topic_id"])
        if review["verdict"] == "pass" and item["status"] in {"failed", "insufficient"}:
            fail("失败或缺数据专题不能标记复核通过。")
        if not isinstance(review.get("note"), str) or not review["note"].strip():
            fail("请说明每个专题的复核依据或需要修订的问题。")
        _render_text(review["note"], {}, {}, set())
    for review in reviews:
        item = topic(report, review["topic_id"])
        item["review"] = deepcopy(review)
        if review["verdict"] == "revise":
            item.update(status="needs_revision", note=review["note"])
        elif review["verdict"] == "pass":
            item["status"] = "reviewed"
        else:
            item.update(
                status="failed" if item["status"] == "failed" else "insufficient",
                note=review["note"],
            )
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
