"""Product summaries grounded in the same saved snapshot as the report."""

import json

from .analysis import LIMITATION, REFERENCE, model_context, validate_findings

SUMMARY_INSTRUCTIONS = """报告已生成。请依据 completion_context 中已保存的结论，
在 terminate 的 output 中写一段简短、连贯的中文整体总结：说明主要经营表现、
盈利质量、现金流或资产负债情况，只概括有依据的内容，不机械逐项列举。
保留重要反向信息与待核查边界；不要把局部结论扩大为整体经营或偿债判断。
数字必须复制 facts/calculations 的 reference，后端按右侧报告同一快照填入
期间、指标名、数值及单位。不要抄写 findings 中的数字，不另算指标，不追加单位，
不混用归母与扣非、金额与增减额、百分比与百分点、不同期间或报表口径。
不要输出专题数量、失败数量、保存条数等流程统计，不输出内部 ID 或 JSON。
无需再次读取或发布报告。数据限制和报告查看入口由后端补充。
"""


def is_published(report):
    if report.get("workflow"):
        return report["workflow"]["status"] == "published"
    analysis = report.get("analysis", {})
    return analysis.get("status") == "completed" or (
        analysis.get("status") == "partial" and bool(analysis.get("completedAt"))
    )


def _findings(report):
    # A review can withhold a previously saved finding. Do not reintroduce it in
    # the completion summary just because its numeric references still exist.
    withheld = {
        ref
        for topic in report.get("workflow", {}).get("topics", [])
        if topic["status"] not in {"ready", "reviewed"}
        for ref in topic["findingIds"]
    }
    return [
        finding
        for finding in report["findings"]
        if finding["id"] not in withheld
        and finding.get("supportStatus") != "unresolved"
    ]


def summary_context(report):
    """Only references used by retained findings, from the current revision."""
    context = model_context(report)
    findings = _findings(report)
    fact_ids = {ref for finding in findings for ref in finding["factIds"]}
    calculation_ids = {ref for finding in findings for ref in finding["calculationIds"]}
    calculations = [
        dict(item, reference="{{calculation:" + item["id"] + "}}")
        for item in context["calculations"]
        if item["id"] in calculation_ids
    ]
    fact_ids.update(ref for item in calculations for ref in item["inputFactIds"])
    facts = [
        dict(item, reference="{{fact:" + item["id"] + "}}")
        for item in context["facts"]
        if item["id"] in fact_ids
    ]
    return {
        "revision": report["revision"],
        "company": context["company"],
        "period": context["year"],
        "statementScope": report["report"]["statementScope"],
        "facts": facts,
        "calculations": calculations,
        "findings": [
            {
                key: finding.get(key)
                for key in (
                    "title",
                    "summary",
                    "counterEvidence",
                    "unresolvedQuestions",
                )
            }
            for finding in findings
        ],
    }


def _limitations(report):
    topics = report.get("workflow", {}).get("topics", [])
    pending = [
        topic["title"]
        for topic in topics
        if topic["status"] not in {"ready", "reviewed", "insufficient"}
    ]
    insufficient = [
        topic["title"] for topic in topics if topic["status"] == "insufficient"
    ]
    notes = []
    if pending:
        notes.append("、".join(pending) + "的分析结论尚待核对。")
    if insufficient:
        notes.append("、".join(insufficient) + "的分析依据不足，具体限制见对应章节。")
    return "".join(notes)


def report_summary(report):
    """Fallback uses saved prose, never an unchecked completion or task counts."""
    if not is_published(report):
        if report.get("analysis", {}).get("status") == "failed":
            return "财务数据与原文依据已整理，当前尚未形成可用的分析结论。"
        return "正在结合已提取的财务数据分析经营表现、盈利质量、现金流与资产负债情况。"
    selected, sections = [], set()
    for finding in _findings(report):
        section = finding["sectionKey"]
        if section in sections:
            continue
        sections.add(section)
        selected.append(" ".join(finding["summary"].splitlines()).strip())
        if len(selected) == 4:
            break
    if not selected:
        return (
            "财务数据与原文依据已整理，当前尚无可用于整体总结的分析结论。"
            + _limitations(report)
        )
    return "".join(selected) + _limitations(report) + LIMITATION


def render_summary(content, report):
    """Validate model prose and resolve numbers using canonical report displays."""
    if not is_published(report):
        return report_summary(report)
    try:
        context = summary_context(report)
        references = set(REFERENCE.findall(content))
        allowed = {("fact", item["id"]) for item in context["facts"]} | {
            ("calculation", item["id"]) for item in context["calculations"]
        }
        if not references or not references <= allowed:
            raise ValueError("Summary references are outside retained findings")
        findings, _ = validate_findings(
            json.dumps(
                {
                    "findings": [
                        {
                            "section": "overview",
                            "title": "整体总结",
                            "summary": " ".join(content.splitlines()).strip(),
                            "supportStatus": "partial",
                            "factIds": sorted(
                                ref for kind, ref in references if kind == "fact"
                            ),
                            "calculationIds": sorted(
                                ref for kind, ref in references if kind == "calculation"
                            ),
                            "evidenceExcerptIds": [],
                        }
                    ]
                },
                ensure_ascii=False,
            ),
            report,
            strict=True,
        )
        return findings[0]["summary"] + _limitations(report) + LIMITATION
    except (ValueError, TypeError):
        return report_summary(report)
