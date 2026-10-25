"""Conversational answers with inline links into the saved financial report."""

import re
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from .analysis import (
    REFERENCE,
    _render_text,
    _validate_fact_wording,
    _validate_interpretation,
    _validate_reference_wording,
    model_context,
)

SUMMARY_INSTRUCTIONS = """报告已生成，请依据 completion_context 直接正常回答用户的问题。
先用一句自然的话告诉用户分析报告已经生成，再衔接值得关注的发现。
例如“这份财报的分析报告已经整理好了，下面说说几个值得关注的变化。”
开场措辞由你结合当前对话组织，不必照抄示例，也不要使用固定开场模板。
用户想知道这份财报最值得关注什么，以及这些变化意味着什么。
对“分析一下财报”这类宽泛问题，选择最重要的两三个发现，写成短而连贯的自然段，
段落之间留空行。每段先说发现或值得关注的变化，再用少量数字解释。
默认正文约三百字，财务数字以四到六处为宜；用户明确要求逐项明细时再展开。
不要把内部专题顺序当成回答结构，不使用“经营表现/盈利质量/现金流/资产负债”
四个固定标题逐栏报数，不单列“整体总结”，也不要每段都以年份和金额起头。
可以加粗一小句关键发现，不把整段、所有数字或引用编号加粗。
优先用增速、差异和利润与现金的关系支撑判断，不重复列出本期金额、上期金额、
同比三套数字。同一数字讲一次即可，具体科目和精确金额放在已有报告里查看。
保留重要反向信息与待核查边界；不要把局部结论扩大为整体经营或偿债判断。
财务数字必须复制 facts/calculations 的 reference；占位符只显示数值与单位，
由你按语境写出指标名称、比较期间及判断，不要省略主语。后端自动在数值旁添加报告引用。
金额自动简写为万元或亿元，精确数值仍在引用对应的报告中；不要自己换算或追加单位。
例如“收入变化不大，但利润承压更明显。归母净利润同比下降{{calculation:复制真实ID}}”。
同一数字再次提及时也必须使用 reference，不写裸数字或自设阈值。
比率使用 calculations.name 中的名称，避免改写分子或分母。
增长或下降的方向必须吻合引用数据，后端会按方向措辞显示增减幅度，避免双重负号。
不要抄写 findings 中的数字，不另算指标，不追加单位，不自行生成引用编号或链接。
不混用归母与扣非、金额与增减额、百分比与百分点、不同期间或报表口径。
扣非利润不等于主营业务利润；比率变化不能直接证明偿债能力增强或资金充足。
仅说明有依据的变化及对应关系，不新增业务原因或管理意图的推断。
不要输出专题数量、失败数量、保存条数等流程统计，不输出内部 ID 或 JSON。
无需再次读取或发布报告。对缺项或依据不足说明对应限制，不需要固定的报告发布套话。
"""


def clean_answer_text(content):
    """Decode escaped Chinese text without turning escaped HTML into markup."""

    def decode(match):
        number = int(match[1], 16) if match[1] else int(match[2])
        return chr(number) if 0x3400 <= number <= 0x9FFF else match[0]

    return re.sub(r"&(?:amp;)?#(?:x([0-9a-fA-F]+)|([0-9]+));", decode, content)


def wants_detailed_answer(query):
    return bool(
        re.search(r"详细|逐项|明细|所有指标|每个指标|完整数据|表格", query or "")
    )


def validate_answer_presentation(content, *, detailed=False):
    text = clean_answer_text(content)
    if not detailed and len(REFERENCE.findall(text)) > 6:
        raise ValueError("too_many_figures_select_key_findings")
    headings = re.findall(
        r"(?m)^\s*(?:#{1,4}\s*|\*\*)?(经营表现|盈利质量|现金流|资产负债)(?:\*\*)?\s*$",
        text,
    )
    if not detailed and len(headings) >= 3:
        raise ValueError("report_outline_is_not_a_conversational_answer")
    if len(REFERENCE.sub("数值", text)) > 300 and "\n\n" not in text:
        raise ValueError("paragraphs_required")


def _answer_value(kind, item, *, magnitude=False):
    """Round amounts for reading; never change the stored fact or calculation."""
    canonical = item["displayValue"] if kind == "fact" else item["displayResult"]
    raw = item.get("normalizedValue" if kind == "fact" else "result")
    try:
        value = Decimal(str(raw))
        if not value.is_finite():
            return canonical
        if item["unit"] == "元" and abs(value) >= 10000:
            divisor, unit = (
                (Decimal(100000000), "亿元")
                if abs(value) >= 100000000
                else (Decimal(10000), "万元")
            )
            scaled = value / divisor
            places = Decimal("1") if abs(scaled) >= 1000 else Decimal("0.01")
            rounded = scaled.quantize(places, rounding=ROUND_HALF_UP)
            display = (
                format(rounded, "f").rstrip("0").rstrip(".")
                if places != 1
                else format(rounded, "f")
            )
            return display + unit
        if magnitude and value < 0:
            return f"{abs(value):,.2f}{item['unit']}"
    except (InvalidOperation, ValueError, TypeError):
        pass
    return clean_answer_text(canonical)


def _change_direction(prefix, item):
    if not re.search(r"_(?:yoy|change)-", item["id"]):
        return False
    down = re.search(
        r"(?:下降|下滑|减少|降低|回落|降幅)(?:了|为|达|约|：|:|\s)*$", prefix
    )
    up = re.search(
        r"(?:增长|增加|上升|提高|提升|增幅)(?:了|为|达|约|：|:|\s)*$", prefix
    )
    value = Decimal(str(item["result"]))
    if (down and value > 0) or (up and value < 0):
        raise ValueError("change_direction_mismatch")
    return bool(down)


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
        "periods": context["periods"],
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
    return "\n\n".join(notes)


def _citation(report, kind, ref, indexes, *, title=None):
    key = (kind, ref)
    if key not in indexes:
        indexes[key] = len(indexes) + 1
    run_id = report["report"]["run"]["id"]
    tooltip = (' "' + title.replace('"', '\\"') + '"') if title else ""
    revision = report.get("revision")
    version = "?revision=" + revision if revision else ""
    return (
        f"[{indexes[key]}](#financial-report/{run_id}/{kind}/{ref}{version}{tooltip})"
    )


def _reading_evidence(finding, context, used):
    """Pick a small set of the finding's saved references, never new metrics."""
    calculations = {
        item["id"]: item
        for item in context["calculations"]
        if item["id"] in finding["calculationIds"]
        and ("calculation", item["id"]) not in used
    }
    facts = {
        item["id"]: item
        for item in context["facts"]
        if item["id"] in finding["factIds"] and ("fact", item["id"]) not in used
    }
    if calculations:
        selected = [("calculation", item) for item in calculations.values()][:2]
    else:
        selected = [("fact", item) for item in facts.values()][:2]
    phrases = []
    for kind, item in selected:
        name = item["metricName"] if kind == "fact" else item["name"]
        if kind == "fact" and item["fiscalPeriod"] != context["year"]:
            name = item["fiscalPeriod"] + "年" + name
        if kind == "calculation" and re.search(r"_(?:yoy|change)-", item["id"]):
            value = Decimal(str(item["result"]))
            direction = "下降" if value < 0 else "上升" if value > 0 else "变动为"
            name += direction
        else:
            name += "为"
        phrases.append(name + "{{" + kind + ":" + item["id"] + "}}")
    return (
        "，".join(phrases) + "。" if phrases else "",
        {(kind, item["id"]) for kind, item in selected},
    )


def report_summary(report):
    """A small, readable fallback grounded in retained findings and their sources."""
    if not is_published(report):
        if report.get("analysis", {}).get("status") == "failed":
            return "财务数据与原文依据已整理，当前尚未形成可用的分析结论。"
        return "正在结合已提取的财务数据分析经营表现、盈利质量、现金流与资产负债情况。"
    context = model_context(report)
    sections, paragraphs, used = set(), [], set()
    priority = {"overview": 0, "cashflow": 1, "profitability": 2, "balance": 3}
    findings = sorted(
        _findings(report), key=lambda item: priority.get(item["sectionKey"], 4)
    )
    for finding in findings:
        if finding["sectionKey"] in sections:
            continue
        title = clean_answer_text(finding["title"]).rstrip("。")
        evidence, references = _reading_evidence(finding, context, used)
        if not evidence:
            continue
        try:
            _validate_interpretation(title)
            paragraph = "**" + title + "。** " + evidence
            # Retain one specific missing-evidence note close to its finding.
            for sentence in re.split(
                r"(?<=[。！？])", clean_answer_text(finding["summary"])
            ):
                if not re.search(r"\d", sentence) and re.search(
                    r"缺少|缺乏|未提供|需结合", sentence
                ):
                    _validate_interpretation(sentence)
                    paragraph += sentence.strip()
                    break
            render_cited_answer(paragraph, report, context=context)
        except ValueError:
            continue
        sections.add(finding["sectionKey"])
        used.update(references)
        paragraphs.append(paragraph)
        if len(paragraphs) == 3:
            break
    if paragraphs:
        answer = render_cited_answer("\n\n".join(paragraphs), report, context=context)
    else:
        answer = "财务数据与原文依据已整理，分析结论仍待核对。"
    limitations = _limitations(report)
    return answer + ("\n\n" + limitations if limitations else "")


def render_cited_answer(content, report, *, context=None, include_labels=False):
    """Keep Markdown paragraphs and attach a report link to each resolved value."""
    content = clean_answer_text(content)
    context = context if context is not None else model_context(report)
    facts = {item["id"]: item for item in context["facts"]}
    calculations = {item["id"]: item for item in context["calculations"]}
    content = re.sub(
        r"\{\{(calc-[A-Za-z0-9_-]+)\}\}",
        lambda match: "{{calculation:" + match[1] + "}}"
        if match[1] in calculations
        else match[0],
        content,
    )
    _validate_reference_wording(content, calculations)
    _validate_fact_wording(content, facts)
    _validate_interpretation(content)
    indexes, used = {}, set()
    references = iter(REFERENCE.finditer(content))

    def reference(kind, ref, item):
        match = next(references)
        prefix = re.split(r"[，。；;！？\n]", content[: match.start()])[-1]
        magnitude = _change_direction(prefix, item) if kind == "calculation" else False
        value = _answer_value(kind, item, magnitude=magnitude)
        canonical = item["displayValue"] if kind == "fact" else item["displayResult"]
        title = (
            "原始值：" + clean_answer_text(canonical)
            if item["unit"] == "元" and value != canonical
            else None
        )
        if include_labels:
            value = (
                f"{item['fiscalPeriod']} 年{item['metricName']} {value}"
                if kind == "fact"
                else f"{item['name']} {value}"
            )
        return value + _citation(report, kind, ref, indexes, title=title)

    answer = _render_text(
        content.strip(),
        facts,
        calculations,
        used,
        context.get("periods", ()),
        render_reference=reference,
        metadata_labels=[item["name"] for item in calculations.values()],
    )
    if not used:
        raise ValueError("Answer has no report reference")
    # A conversational answer may discuss more metrics than a short Q&A card,
    # but must retain the same source and document checks.
    fact_ids = {ref for kind, ref in used if kind == "fact"}
    fact_ids.update(
        ref
        for kind, calc in used
        if kind == "calculation"
        for ref in calculations[calc]["inputFactIds"]
    )
    try:
        sources = {
            ref for fact_id in fact_ids for ref in facts[fact_id]["evidenceExcerptIds"]
        }
        evidence = {item["id"]: item for item in report["evidence"]}
        documents = {item["id"] for item in report["documents"]}
        if not sources or any(
            evidence[ref]["sourceDocumentId"] not in documents for ref in sources
        ):
            raise ValueError("Answer has no valid report source")
    except KeyError as exc:
        raise ValueError("Unknown answer source") from exc
    return answer


def render_summary(content, report, *, strict=False, detailed=False):
    """Validate model prose and resolve numbers using canonical report displays."""
    if not is_published(report):
        return report_summary(report)
    content = clean_answer_text(content)
    try:
        validate_answer_presentation(content, detailed=detailed)
        context = summary_context(report)
        references = set(REFERENCE.findall(content))
        allowed = {("fact", item["id"]) for item in context["facts"]} | {
            ("calculation", item["id"]) for item in context["calculations"]
        }
        if not references or not references <= allowed:
            raise ValueError("Summary references are outside retained findings")
        answer = render_cited_answer(content, report, context=context)
        limitations = _limitations(report)
        return answer + ("\n\n" + limitations if limitations else "")
    except (ValueError, TypeError):
        if strict:
            raise
        return report_summary(report)
