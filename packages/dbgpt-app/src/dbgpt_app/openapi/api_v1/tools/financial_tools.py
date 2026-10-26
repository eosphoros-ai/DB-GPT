"""Financial report tools owned by the current conversational agent turn."""

import asyncio
import json
import re
from pathlib import Path
from uuid import uuid4

from dbgpt.agent.resource.tool.base import tool
from dbgpt_serve.financial_analysis.analysis import (
    REFERENCE,
    SYSTEM_PROMPT,
    InvalidFindings,
    model_context,
    review_model_context,
)
from dbgpt_serve.financial_analysis.comparison_schema import report_title
from dbgpt_serve.financial_analysis.summary import (
    SUMMARY_INSTRUCTIONS,
    is_published,
    render_cited_answer,
    render_summary,
    report_summary,
    summary_context,
    validate_answer_presentation,
    wants_detailed_answer,
)
from dbgpt_serve.financial_analysis.workflow import next_action, topic_context

FINANCIAL_MAX_STEPS = 40


def is_financial_turn(state):
    """Scope report safeguards to financial requests, including brief follow-ups."""
    if state.get("financial_pending") or "financial_user_query" not in state:
        return True
    query = (state.get("financial_user_query") or "").strip()
    return bool(
        re.search(
            r"财报|年报|年度报告|财务|营收|营业收入|利润|毛利|费用率|负债|资产|"
            r"现金流|偿债|扣非|净利|每股|分红|这家公司|该公司|这份报告|这份年报|"
            r"刚才的(?:报告|分析)|上述(?:报告|分析)|"
            r"\b(?:financial|annual reports?|revenue|profit|margin|cash flow|"
            r"liquidity|balance sheet|earnings|dividends|this company|"
            r"the report|that report|saved report)\b",
            query,
            re.I,
        )
        or re.fullmatch(
            r"(?:继续(?:分析|任务)?|详细(?:说说|解释|一点)?|展开(?:说说)?|"
            r"为什么(?:会这样|下降|上升|增长|减少|增加)?|有什么风险|依据是什么|"
            r"再解释一下|continue|tell me more|why|explain(?: further)?)[？?。.!！]*",
            query,
            re.I,
        )
    )


def has_comparison_intent(query):
    query = query or ""
    if re.search(
        r"不(?:要|需|用)?(?:进行)?(?:对比|比较)|do not compare|no comparison",
        query,
        re.I,
    ):
        return False
    return bool(
        re.search(r"对比|比较|横向|跨年|差异|异同|compar(?:e|ison)", query, re.I)
    )


SECTIONAL_RULES = """本报告采用专题流程，不要一次提交整份报告的 findings。
prepare 默认有界并发生成六专题，返回完整 review_context 时直接逐项复核。
若返回 topic_context 则按串行恢复流程分析；保存成功自动返回下一专题，无需额外 get。
仅显式读取或重做专题时调用 get_financial_topic，
由你分析后调用 save_financial_topic 保存两到三条有依据的发现（数据有限可以减少）。
经营表现、扣非与利润构成、毛利变化、费用变化、现金流、资产负债都要处理。
每条包含判断、引用、反向信息和待核查事项，不能仅重复数字；不得编造变化原因。
仅对 missingRequiredMetrics 非空的专题可用 missing_reason 说明缺项并提交空 findings。
保存失败只修当前专题，使用返回的新 revision；不要重新 prepare 或重算 PDF。
工具的 model_context 是模型专用数据，chunks 仅供界面展示。每次遵循 next_action。
topic_result.saved=false 表示未保存成功，一次处理 issues 中所有 finding_index 和字段。
反向信息和待核查事项中的引用也必须写入同一条发现的 Ids 数组。
修正时直接 save，仅传 patches，格式：
[{"finding_index":错误索引,"changes":{"错误字段":"修正值"}}]，
保留已通过校验的草稿；也支持完整 findings。不要重复 get 或用 retry=true 重置失败计数。
覆盖不全时可仅传 append_findings 追加缺失科目的发现，不重写已有草稿；仍完整校验。
专题连续三次失败后继续其他专题，复核使用 insufficient；不能冒充成功。
全部专题处理后调用 review_financial_report，逐项检查变化方向、期间/口径和原因依据。
复核必须覆盖全部专题，每项给出 topic_id、verdict（pass/revise/insufficient）、
directionChecked:true、scopeChecked:true、causalityChecked:true、note（不含数字的具体核对说明）。
三项 Checked 记录该维度及其缺口已检查，不表示结论通过；
失败或缺数据专题检查缺口后也填 true，verdict 使用 insufficient，并在 note 说明限制。
需要修订就修正对应专题，然后重新复核。明确复核通过后后端原子发布，
workflow.status=published 后按 completion_instructions 分段正常作答并 terminate，
无需再调用 publish。不得在未发布时 terminate。
用户只要求重做某专题时，先 read 当前报告，再 get_financial_topic(retry=true)，
保留其他专题，修订后复核、发布；不重新解析 PDF。普通追问仍直接 read 后回答。
"""

# Reuse the validation rules, not the standalone analyzer's "do not call tools"
# and "return only JSON" instructions. Here the active agent must publish.
PUBLICATION_RULES = (
    "下一步必须在本轮调用 publish_financial_report，不能 terminate 描述下一步计划。"
    "用工具参数 findings 提交结构化发现，通常四条，证据不足可以减少或传空数组。"
    "每条最多六个 calculationIds，超出时按主题拆成多条，整个数组最多六条。"
    "直接复制数据中的 reference 字段；计算引用必须有 calculation: 前缀。"
    "不能把 calc- 开头的计算 ID 直接放进双花括号，必须在 ID 前加 calculation:。"
    "不要写‘低于1倍’，可写‘经营现金流低于归母净利润’并引用相应计算。"
    "section 可为 overview、profitability、cashflow、balance。\n"
    + SYSTEM_PROMPT[SYSTEM_PROMPT.index("每条发现字段") :]
)

FINANCIAL_AGENT_PROMPT = """
用户明确要求比较多份财报时调用 prepare_financial_comparison；
参数 file_ids 为当前附件真实 ID 数组，comparison_kind=peer（同年多公司）
或 trend（同公司跨年），baseline_file_id 可选。多附件本身不表示对比意图。
对比结论必须按工具返回的结构化公司、期间、指标和方向字段保存。
发现身份歧义时调用 resolve_financial_comparison，失败文件可显式 resume，
成功提取不会重跑。不要以重新 prepare 替代局部恢复。
## 财报分析与当前对话中的报告
分析年度报告时，先加载 financial-report-analyzer 技能（已预加载则不重复加载），并使用
prepare_financial_report 提取、计算并有界并发生成专题草稿，
你根据返回的 review_context 逐项复核；复核通过自动发布。
若 next_action 要求修订则仅修指定专题；不要重新生成已保存专题。
prepare_financial_report、get_financial_topic、save_financial_topic、
review_financial_report、publish_financial_report、read_financial_report
都是已注册的后端工具，不是 Skill 脚本或 .py 文件。直接使用它们作为 Action，
不需要 load_tools，不通过 execute_skill_script、execute_skill_script_file
或 execute_tool。
仅有一份 PDF 附件时，准备步骤直接输出：
Action: prepare_financial_report
Action Input: {}
有多份 PDF 时在 Action Input 中指定附件清单里的 file_id。
不能猜测 prepare.py、prepare_financial_report.py 等脚本名，也不使用
code_interpreter、shell_interpreter 或知识库搜索替代财报提取、计算和发布。
如专用工具返回错误，根据实际错误处理；不把工具错误解释成缺少 Skill 脚本。
不使用 generate_report、html_interpreter、旧 HTML 模板或自行编写网页来替代财报组件。
工具返回的财报已显示在当前对话右侧，不要让用户跳转 /financial-analysis。
关于财报的后续追问先调用 read_financial_report 读取当前对话的报告，不重复提取 PDF，
与财报无关的问题正常回答，不要求读取报告，也不套用财报引用或数字校验。
只引用已有事实、计算及原文，缺少数据就明确说明，不自行计算新指标或补造原因。
追问的最终回答必须直接复制 data.facts/data.calculations 中的 reference 字段，
不能抄 displayValue、金额、年份或页码，也不能复制含数字的原文片段或追加单位。
按 read 返回的 answer_format_example 将引用放进 terminate 的 output 字符串；
服务端会替换报告中的真实数值，并添加定位到报告依据的引用。
发布后按 completion_instructions 正常回答用户的问题，按内容分段，不写固定总结。数字复制
completion_context 中的 reference，与右侧报告保持同一期间、指标与单位。
默认选择两三个最值得关注的发现，先解释变化意味着什么，再给少量数字。
不要按内部专题逐栏报数，不重复罗列本期、上期和同比；明细留在报告中。
占位符只显示数值及单位，按语境写清指标名称，后端在数值旁添加可点击的报告引用。
不要用保存条数、失败数量或“部分分析”等流程统计代替回答。
"""


def _service():
    from dbgpt._private.config import Config
    from dbgpt_serve.session_file.serve import SessionFileServe

    component = Config().SYSTEM_APP.get_component(
        SessionFileServe.name, SessionFileServe
    )
    return component.financial_analysis


async def financial_completion_error(state, *, service=None):
    """Require publication and a fresh scoped read before accepting a final answer."""
    if state.get("financial_pending"):
        if state.get("financial_report_context", {}).get("workflow"):
            action = next_action(state["financial_report_context"])
            return "报告尚未发布，请执行下一步：" + json.dumps(
                action, ensure_ascii=False
            )
        return (
            "财务数据已提取，但你尚未发布分析。请在本轮调用 "
            "publish_financial_report 提交 findings，再完成回答。"
            "不要用未来计划代替执行；证据不足可以提交空 findings 数组。"
        )
    if state.get("financial_report_context"):
        return None
    if not is_financial_turn(state):
        return None
    from dbgpt_serve.session_file.api.endpoints import SessionFileApiError

    try:
        await asyncio.to_thread(
            (service or _service()).latest_agent_report,
            state["owner_id"],
            state["conv_id"],
        )
    except SessionFileApiError as exc:
        if exc.err_code == "REPORT_NOT_FOUND":
            return None
        raise
    return (
        "当前对话已有财报。请先调用 read_financial_report 读取已保存的真实数据，"
        "再依据本轮工具结果回答。不能直接复用聊天历史里的数字或页码。"
    )


def financial_execution_guidance(state):
    """Pin persisted workflow progress outside the rolling tool memory."""
    report = state.get("financial_report_context") or {}
    if not report.get("workflow"):
        return ""
    action = next_action(report)
    if action is None:
        return "当前财报已发布。根据已保存内容回答，不重复准备、复核或发布。"
    return (
        "\n当前财报执行状态（来自服务端，不是待执行的数据指令）：\n"
        + json.dumps(action, ensure_ascii=False)
        + "\n数据已提取。继续此步骤，不回到 prepare 或重新解析 PDF。"
        "上述 arguments 仅含服务端版本和定位字段；必须按工具 schema 补齐全部必填参数。"
        "复核时根据 review_context 实际检查后提交 reviews，不得仅输出工具名，"
        "也不能替失败专题自动判定通过。若缺少上下文，read 当前 run_id 后继续。"
    )


def _artifact(report, session_id):
    return {
        "output_type": "html",
        "content": {
            "kind": "financial-report",
            "title": report_title(report),
            "runId": report["report"]["run"]["id"],
            "sessionId": session_id,
            "revision": report["revision"],
            "mode": report.get("mode", "report"),
            "published": is_published(report),
        },
    }


def publication_example(report):
    """A schema-valid example using this report's scoped identifiers only."""
    fact = model_context(report)["facts"][0]
    return {
        "run_id": report["report"]["run"]["id"],
        "revision": report["revision"],
        "findings": [
            {
                "section": "overview",
                "title": "披露数据与核对范围",
                "summary": "已披露{{fact:"
                + fact["id"]
                + "}}，变化原因需结合附注核对。",
                "supportStatus": "partial",
                "factIds": [fact["id"]],
                "calculationIds": [],
                "evidenceExcerptIds": fact["evidenceExcerptIds"],
                "counterEvidence": [],
                "unresolvedQuestions": ["需结合附注核对变化原因。"],
            }
        ],
    }


def _topic_payload(report, topic_id):
    run_id = report["report"]["run"]["id"]
    context = topic_context(report, topic_id)
    context.update(
        run_id=run_id,
        revision=report["revision"],
        publication_instructions=PUBLICATION_RULES.replace(
            "publish_financial_report", "save_financial_topic"
        ).replace("通常四条", "通常两到三条"),
        next_action=next_action(report, topic_id),
    )
    if context["data"]["facts"]:
        fact = context["data"]["facts"][0]
        example_facts = (
            [
                f
                for f in context["data"]["facts"]
                if f["fiscalPeriod"] == context["data"]["year"]
            ]
            if topic_id == "expenses"
            else [fact]
        )
        context["save_example"] = {
            "run_id": run_id,
            "revision": report["revision"],
            "topic_id": topic_id,
            "findings": [
                {
                    "section": context["section"],
                    "title": "披露数据与解释边界",
                    "summary": "、".join(f["reference"] for f in example_facts)
                    + "，变化原因需结合附注核对。",
                    "supportStatus": "partial",
                    "factIds": [f["id"] for f in example_facts],
                    "calculationIds": [],
                    "evidenceExcerptIds": sorted(
                        {e for f in example_facts for e in f["evidenceExcerptIds"]}
                    ),
                    "counterEvidence": [],
                    "unresolvedQuestions": ["需核对附注中的变化原因。"],
                }
            ],
        }
        if report.get("mode") == "comparison":
            example = context["save_example"]["findings"][0]
            scoped_facts = [
                f for f in context["data"]["facts"] if f["id"] in example["factIds"]
            ]
            example.update(
                entityIds=sorted({f["entityId"] for f in scoped_facts}),
                periods=sorted({f["fiscalPeriod"] for f in scoped_facts}),
                metricCodes=sorted({f["metricCode"] for f in scoped_facts}),
                subjectEntityId=fact["entityId"],
                baselineEntityId=None,
                comparisonDirection="none",
            )
    return context


def _result(
    report, session_id, *, include_context=False, reading=False, active_topic=None
):
    workflow_summary = None
    if report.get("workflow"):
        flow = report["workflow"]
        workflow_summary = {
            key: flow.get(key) for key in ("version", "status", "publishedAt")
        }
        workflow_summary["topics"] = [
            {
                key: value
                for key, value in topic.items()
                if key
                in {
                    "id",
                    "title",
                    "section",
                    "status",
                    "findingIds",
                    "errorCode",
                    "failures",
                    "saveAttempts",
                    "reviewRevisionAttempts",
                }
            }
            for topic in flow["topics"]
        ]
    summary = {
        "run_id": report["report"]["run"]["id"],
        "revision": report["revision"],
        "analysis": report.get("analysis"),
        "finding_count": len(report["findings"]),
        "workflow": workflow_summary,
    }
    if reading or not workflow_summary:
        summary["findings"] = report["findings"]
    if workflow_summary:
        current = next(
            (
                t
                for t in report["workflow"]["topics"]
                if t["status"] in {"running", "needs_revision"}
            ),
            None,
        )
        summary["next_action"] = next_action(
            report, current["id"] if current else active_topic
        )
        if current:
            if current["status"] == "needs_revision" and current.get("draftFindings"):
                scoped = topic_context(report, current["id"])["data"]
                summary["repair"] = {
                    "topic_id": current["id"],
                    "section": current["section"],
                    "review": current.get("review"),
                    "draftFindings": current["draftFindings"],
                    "issues": current.get("issues", []),
                    "instructions": (
                        "逐项处理所有 issues，优先采用各项 hint / suggested_changes，"
                        "合并为一次 patches 提交；不要遗漏后面的 finding_index。"
                        "若有 review.verdict=revise，必须同时修正该复核指出的语义问题。"
                    ),
                    "data": scoped,
                }
            else:
                summary["topic_context"] = _topic_payload(report, current["id"])
        elif (
            summary["next_action"]
            and summary["next_action"]["tool"] == "review_financial_report"
        ):
            # Only the explicit review stage needs all narratives and evidence.
            summary["review_context"] = {
                "instructions": (
                    "逐条核对引用名称和句子主语、分子分母是否对应，不能只确认引用存在。"
                    "差额占比不能写为扣非利润占比；扣非利润不等于主营业务利润。"
                    "本上下文没有行业基准、债务期限、受限资金或业务原因证据，"
                    "不能通过行业比较、资金充裕或偿债安全等断言。"
                    "发现错误用 revise 并说明待改字段，不能以通用免责声明代替修订。"
                    "failed/insufficient 专题只能记录 insufficient，不通过复核重开。"
                    "没有原因附注不等于没有财务数据，也不否定有引用的差异观察。"
                    "availableMetrics/availableCalculations 是已提取数据清单，"
                    "不能将未在本次引用依赖中展开的数据说成未提取。"
                ),
                "findings": report["findings"],
                "data": review_model_context(report),
                "topics": [
                    {
                        k: t.get(k)
                        for k in (
                            "id",
                            "status",
                            "note",
                            "errorCode",
                            "issues",
                            "findingIds",
                        )
                    }
                    for t in report["workflow"]["topics"]
                ],
            }
    if active_topic:
        item = next(t for t in report["workflow"]["topics"] if t["id"] == active_topic)
        summary["topic_result"] = {
            "topic_id": active_topic,
            "status": item["status"],
            "saved": item["status"] in {"ready", "insufficient"},
            "issues": item.get("issues", []),
            "repair_instructions": (
                "优先仅传 patches=[{finding_index:索引,changes:{字段:修正值}}]，"
                "不传 findings；"
                "服务端保留其他草稿并完整重验。按 finding_index 和 field 修正后，"
                "使用 next_action 中的新 revision 再保存。"
                "invalid_tokens 列出该字段中必须全部删除或改用已有引用的数值；"
                "未经计算工具提供的差额和数字阈值改为定性比较，不得自行补算。"
                "所有文本字段中的引用都要声明在同一条发现的 factIds/calculationIds，"
                "不能直接写数字或在占位符后追加单位；不得删除校验规则。"
                "unsupported_* 表示超出表格证据的解释：改为有依据的观察，"
                "将原因/行业/偿债判断改为待核查问题，不能追加免责声明保留断言。"
            ),
        }
        if item["status"] in {"failed", "insufficient"}:
            summary["topic_result"]["repair_instructions"] = (
                "此专题已结束本次自动处理，保留有效内容与缺口。"
                "继续 next_action，不重复保存或用复核重启此专题。"
            )
        elif not item.get("issues"):
            summary["topic_result"].pop("repair_instructions")
    if include_context:
        if reading:
            summary["answer_instructions"] = (
                "直接回答当前追问，无需重新发布报告。数字使用 {{fact:真实ID}} 或 "
                "{{calculation:真实ID}} 占位符，服务端会替换真实值。"
                "不要直接写年份、金额、比率或页码，也不要追加单位。"
                "占位符只显示数值和单位，请按语境写清指标名称和期间。"
                "按内容分段，段落间留空行；数值旁的报告引用由服务端添加。"
                "优先回答当前问题，默认用少量关键数字解释，不列整套财务数据；"
                "用户明确要求逐项明细时再展开。"
                "资料不足明确说明，不补造原因。"
            )
        else:
            summary["publication_instructions"] = (
                SECTIONAL_RULES + SYSTEM_PROMPT[SYSTEM_PROMPT.index("每条发现字段") :]
                if report.get("workflow")
                else PUBLICATION_RULES
            )
            if not report.get("workflow"):
                summary["publication_example"] = publication_example(report)
        # Put format instructions before the large data payload, and provide
        # copyable references so the agent does not have to reconstruct syntax.
        # New analyses read scoped data with get_financial_topic. Avoid sending
        # the full report twice before the first topic. Follow-up still needs it.
        if reading or not report.get("workflow"):
            context = model_context(report)
            for kind, key in (("fact", "facts"), ("calculation", "calculations")):
                for item in context[key]:
                    item["reference"] = "{{" + kind + ":" + item["id"] + "}}"
            summary["data"] = context
            if reading and context["facts"]:
                summary["answer_format_example"] = {
                    "Action": "terminate",
                    "Action Input": {
                        "output": "本期"
                        + context["facts"][0]["metricName"]
                        + "为"
                        + context["facts"][0]["reference"]
                        + "。原文依据可在右侧报告中核对。"
                    },
                }
    if not reading and is_published(report):
        summary["completion_instructions"] = SUMMARY_INSTRUCTIONS
        summary["completion_context"] = summary_context(report)
    return json.dumps(
        {
            "chunks": [
                _artifact(report, session_id),
                {
                    "output_type": "text",
                    "content": report_summary(report)
                    if is_published(report)
                    else report["agent"]["summary"],
                },
            ],
            "model_context": summary,
        },
        ensure_ascii=False,
    )


def financial_answer_error(content, state, *, repair_limit=2):
    """Give the agent bounded feedback before replacing an invalid final answer."""
    if not is_financial_turn(state):
        return None
    report = state.get("financial_report_context")
    if not report or not is_published(report):
        return None
    if not summary_context(report)["facts"]:
        return None
    try:
        detailed = wants_detailed_answer(state.get("financial_user_query"))
        if state.get("financial_read"):
            if not REFERENCE.search(content):
                return None
            render_cited_answer(content, report)
            validate_answer_presentation(content, detailed=detailed)
        else:
            render_summary(content, report, strict=True, detailed=detailed)
    except (ValueError, TypeError) as exc:
        attempts = state.get("financial_answer_repairs", 0)
        if repair_limit is not None and attempts >= repair_limit:
            return None
        state["financial_answer_repairs"] = attempts + 1
        details = str(exc)
        tokens = getattr(exc, "invalid_tokens", None)
        if tokens:
            details += ": " + json.dumps(tokens, ensure_ascii=False)
        style = (
            "按用户要求详细展开。"
            if detailed
            else "默认选两三个重要发现，每段先讲变化意味着什么，再用关键数字支撑；"
            "财务数字控制在四到六处，不重复罗列本期、上期和同比，"
            "不要把经营表现、盈利质量、现金流、资产负债当四个固定栏目。"
        )
        return (
            "最终回答尚未通过校验：" + details + "。只修正 terminate 的 output，"
            "无需读取、重算或重新发布报告。按内容分段，段间留空行。"
            + style
            + "所有财务数字及再次提及的数值都必须复制 completion_context 的 reference；"
            "删除自行计算的数值、裸数字与阈值，不得用中文数词绕过。"
            "占位符只显示数值和单位；比率前使用 calculations.name + 为，"
            "不要以‘占…的’重写分子分母。只保留已有依据的判断，"
            "删除新增的原因、主业利润或偿债能力断言。"
        )
    return None


def finalize_financial_answer(content, state):
    """Render/validate agent references before both SSE final and history save."""
    if not is_financial_turn(state):
        return content
    report = state.get("financial_report_context")
    if not report:
        return content
    detailed = wants_detailed_answer(state.get("financial_user_query"))
    if not state.get("financial_read"):
        return render_summary(content, report, detailed=detailed)
    references = set(REFERENCE.findall(content))
    if not references:
        return "当前报告已提取的数据不足以回答这个问题。请结合原文或补充相关资料核对。"
    context = model_context(report)
    try:
        validate_answer_presentation(content, detailed=detailed)
    except ValueError:
        if is_published(report):
            return report_summary(report)
    try:
        text = render_cited_answer(content, report, context=context)
    except ValueError:
        try:
            # Degraded prose is rebuilt from validated references, never from
            # the rejected explanation or its numbers.
            text = render_cited_answer(
                "以下仅列出可核对的已保存数据：\n\n"
                + "\n\n".join(
                    "{{" + kind + ":" + ref + "}}"
                    for kind, ref in sorted(references)[:6]
                ),
                report,
                context=context,
                include_labels=True,
            )
        except ValueError:
            return "回答未通过数字或引用校验，请在右侧报告查看依据或重新提问。"
    return text


def make_financial_tools(
    state, *, service=None, stream_callback=None, sectional=True, topic_generator=None
):
    """Bind owner/session to trusted turn state, never to model arguments."""

    def scope():
        owner, session_id = state.get("owner_id"), state.get("conv_id")
        if not owner or not session_id:
            raise ValueError("当前对话身份尚未就绪。")
        return service or _service(), owner, session_id

    latest_progress_report = None
    activity = {}
    observed_findings = set()
    observed_runs = set()

    async def execution_started(action, action_input, message):
        if sectional and stream_callback:
            await stream_callback(
                "financial.execution",
                {
                    "action": action,
                    "action_input": action_input,
                    "message": message,
                },
            )

    async def progress(report=None, stage=None, error=False):
        nonlocal latest_progress_report
        if not sectional:
            return
        from dbgpt_serve.financial_analysis.progress import public_progress

        latest_progress_report = report
        tasks = public_progress(
            report,
            stage=stage,
            previous=state.get("financial_plan", []),
            activity=activity,
            error=error,
        )
        state["financial_plan"] = tasks
        if stream_callback:
            observations = []
            if report:
                run_id = report["report"]["run"]["id"]
                if run_id not in observed_runs:
                    observed_runs.add(run_id)
                    names = list(
                        dict.fromkeys(
                            f["metricName"]
                            for f in report.get("facts", [])
                            if f.get("normalizedValue") is not None
                            and f.get("metricName")
                        )
                    )
                    if names:
                        observations.append(
                            "已读取财务科目：" + "、".join(names[:12]) + "。"
                        )
                for finding in report.get("findings", []):
                    summary = finding.get("summary", "")
                    key = (run_id, finding.get("id"), summary)
                    if summary and key not in observed_findings:
                        observed_findings.add(key)
                        observations.append(
                            "已校验的分析发现（待最终复核）：" + summary
                        )
            await stream_callback(
                "financial.progress", {"tasks": tasks, "observations": observations}
            )

    async def activity_progress(value):
        nonlocal activity
        activity = value
        await progress(latest_progress_report)

    async def remember(report, *, pending=True, active_topic=None):
        state.update(financial_report_context=report, financial_read=False)
        run_id = report["report"]["run"]["id"]
        if report.get("workflow", {}).get("status") == "published":
            state.setdefault("financial_pending", set()).discard(run_id)
        elif pending:
            state.setdefault("financial_pending", set()).add(run_id)
        await progress(report)
        return _result(report, state["conv_id"], active_topic=active_topic)

    @tool(
        description=(
            "仅用户明确要求对比时准备多财报：file_ids 为当前对话的两到五份 PDF，"
            "comparison_kind=peer 同年度多公司，trend 同公司跨年；"
            "可指定 baseline_file_id。"
            "数据先持久化，然后复用专题保存、复核和发布工具。多附件但无比较意图不能调用。"
        )
    )
    async def prepare_financial_comparison(
        file_ids: list[str], comparison_kind: str, baseline_file_id: str = ""
    ) -> str:
        if not 2 <= len(file_ids) <= 5:
            raise ValueError("对比需要两到五份 PDF。")
        if not has_comparison_intent(state.get("financial_user_query")):
            raise ValueError("当前请求未明确要求比较，请按单报告或普通附件处理。")
        backend, owner, session_id = scope()
        allowed = {
            m.file_id
            for m in state.get("session_files", [])
            if m.name.lower().endswith(".pdf")
        }
        if not set(file_ids) <= allowed:
            raise ValueError("只能选择当前对话已授权的 PDF 附件。")
        config = {
            "kind": comparison_kind,
            "baseline_file_id": baseline_file_id or file_ids[0],
        }
        key = json.dumps([file_ids, config], sort_keys=True)
        run_id = state.setdefault("financial_comparison_runs", {}).setdefault(
            key, str(uuid4())
        )
        await asyncio.to_thread(
            backend.comparisons.create,
            owner,
            session_id,
            file_ids,
            run_id,
            config,
            agent_model=state.get("model_name") or "conversation-agent",
        )
        await execution_started(
            "prepare_financial_comparison",
            {"file_ids": file_ids},
            "正在逐份提取财报并对齐比较口径。",
        )
        await progress()
        deadline = asyncio.get_running_loop().time() + 650
        while True:
            run = await asyncio.to_thread(backend.get, owner, session_id, run_id)
            if run["status"] == "failed":
                raise ValueError(run.get("error") or "对比任务已中断，可显式继续。")
            if run.get("report_ready") and run["status"] == "completed":
                report = await asyncio.to_thread(
                    backend.get, owner, session_id, run_id, report=True
                )
                if report["comparison"]["ready"]:
                    from dbgpt_serve.financial_analysis.parallel import (
                        TopicGenerator,
                        analyze_topics,
                    )

                    generator = topic_generator
                    if (
                        generator is None
                        and state.get("financial_llm_client")
                        and state.get("model_name")
                    ):
                        generator = TopicGenerator(
                            state["financial_llm_client"],
                            state["model_name"],
                            owner,
                            session_id,
                        )
                    if generator and all(
                        t["status"] == "pending" for t in report["workflow"]["topics"]
                    ):
                        report = await analyze_topics(
                            backend,
                            owner,
                            session_id,
                            report,
                            generator,
                            progress,
                            activity=activity_progress,
                        )
                    else:
                        report = await asyncio.to_thread(
                            backend.update_agent_workflow,
                            owner,
                            session_id,
                            run_id,
                            report["revision"],
                            "advance",
                        )
                else:
                    state.update(financial_report_context=report, financial_read=True)
                    state.setdefault("financial_pending", set()).discard(run_id)
                    return json.dumps(
                        {
                            "chunks": [_artifact(report, session_id)],
                            "model_context": {
                                "run_id": run_id,
                                "revision": report["revision"],
                                "clarifications": report["comparison"][
                                    "clarifications"
                                ],
                                "members": report["members"],
                                "instructions": (
                                    "已保存提取内容，尚未形成有效对比；"
                                    "请澄清或补充对象，不能声称完成对比。"
                                ),
                            },
                        },
                        ensure_ascii=False,
                    )
                return await remember(report)
            if asyncio.get_running_loop().time() >= deadline:
                raise TimeoutError("提取仍在后台运行；读取已保存任务，不要重新创建。")
            await asyncio.sleep(0.3)

    @tool(
        description=(
            "显式继续对比任务或确认元信息；run_id/revision 来自当前对比。"
            "resolutions 为 file_id 到 {company_name,report_year} 的映射，"
            "必须来自用户确认。"
            "不传 resolutions 只重试失败文件，成功提取不重跑。"
        )
    )
    async def resolve_financial_comparison(
        run_id: str, revision: str = "", resolutions: dict = None
    ) -> str:
        backend, owner, session_id = scope()
        if resolutions:
            from dbgpt_serve.financial_analysis.api import IdentityResolution

            resolutions = {
                key: IdentityResolution.model_validate(value).model_dump()
                for key, value in resolutions.items()
            }
        result = await asyncio.to_thread(
            backend.comparisons.resume,
            owner,
            session_id,
            run_id,
            revision or None,
            resolutions,
        )
        return json.dumps({"model_context": result}, ensure_ascii=False)

    @tool(
        description=(
            "提取当前对话 PDF 年报并执行确定性财务计算。"
            "返回原文引用、数字和待分析报告。"
            "默认并发生成六专题并完整校验，返回 review_context 后直接 review；"
            "恢复任务时按 next_action 继续；"
            "六专题完成并显式 review 后自动发布。"
            "file_id 可省略（仅一个 PDF 时）；多文件时必须指定当前附件的 file_id。"
        )
    )
    async def prepare_financial_report(file_id: str = "") -> str:
        await execution_started(
            "prepare_financial_report",
            {"file_id": file_id},
            "开始读取财报，提取财务数据和原文依据。",
        )
        await progress(stage="extract")
        try:
            return await prepare(file_id)
        except (Exception, asyncio.CancelledError):
            await progress(latest_progress_report, error=True)
            raise

    async def prepare(file_id):
        backend, owner, session_id = scope()
        manifests = state.get("session_files", [])
        if manifests:
            candidates = [m for m in manifests if m.name.lower().endswith(".pdf")]
            if file_id:
                candidates = [m for m in candidates if m.file_id == file_id]
            if len(candidates) != 1:
                raise ValueError("请选择当前附件中的一份 PDF 年报。")
            selected_id = candidates[0].file_id
        else:
            if file_id:
                raise ValueError(
                    "当前选择的是首页示例文件，没有 file_id。"
                    "请省略 file_id，直接以空参数调用 prepare_financial_report。"
                )
            if not state.get("file_path"):
                raise ValueError("请先在当前对话上传或选择一份 PDF 年报。")
            # Legacy homepage examples are revalidated and registered durably;
            # no model-supplied path is accepted by this tool.
            selected_id = state.get("financial_legacy_file_id")
            if not selected_id:
                from dbgpt_app.openapi.api_v1.agentic_data_api import (
                    _legacy_upload_base_dir,
                )
                from dbgpt_app.openapi.api_v1.attachment_react_adapter import (
                    resolve_legacy_chat_file_path,
                )

                path = Path(
                    resolve_legacy_chat_file_path(
                        file_path=Path(state["file_path"]).as_posix(),
                        owner_id=owner,
                        base_dir=_legacy_upload_base_dir(),
                    )
                )
                if path.suffix.lower() != ".pdf":
                    raise ValueError("财报分析需要 PDF 年度报告。")

                def register():
                    with path.open("rb") as stream:
                        return backend.registry.ingest(
                            owner_id=owner,
                            session_id=session_id,
                            display_name=path.name,
                            media_type="application/pdf",
                            stream=stream,
                            size_bytes=path.stat().st_size,
                        ).file_id

                selected_id = await asyncio.to_thread(register)
                state["financial_legacy_file_id"] = selected_id

        attempts = state.setdefault("financial_runs", {})
        run_id = attempts.setdefault(selected_id, str(uuid4()))
        await asyncio.to_thread(
            backend.create,
            owner,
            session_id,
            selected_id,
            run_id,
            agent_model=state.get("model_name") or "conversation-agent",
            sectional=sectional,
        )
        deadline = asyncio.get_running_loop().time() + 150
        last_stage = None
        while True:
            run = await asyncio.to_thread(backend.get, owner, session_id, run_id)
            if run.get("stage") != last_stage:
                last_stage = run.get("stage")
                await progress(stage=last_stage)
            if run["status"] == "failed":
                raise ValueError(run["error"] or "财报提取失败。")
            if run.get("report_ready"):
                report = await asyncio.to_thread(
                    backend.get, owner, session_id, run_id, report=True
                )
                if report.get("analysis", {}).get("completedAt") is None:
                    state.setdefault("financial_pending", set()).add(run_id)
                if report.get("workflow"):
                    from dbgpt_serve.financial_analysis.parallel import (
                        TopicGenerator,
                        analyze_topics,
                    )

                    generator = topic_generator
                    if (
                        generator is None
                        and state.get("financial_llm_client")
                        and state.get("model_name")
                    ):
                        generator = TopicGenerator(
                            state["financial_llm_client"],
                            state["model_name"],
                            owner,
                            session_id,
                        )
                    if generator and all(
                        t["status"] == "pending" for t in report["workflow"]["topics"]
                    ):
                        report = await analyze_topics(
                            backend,
                            owner,
                            session_id,
                            report,
                            generator,
                            progress,
                            activity=activity_progress,
                        )
                    else:
                        report = await asyncio.to_thread(
                            backend.update_agent_workflow,
                            owner,
                            session_id,
                            run_id,
                            report["revision"],
                            "advance",
                        )
                state.update(financial_report_context=report, financial_read=False)
                await progress(report)
                return _result(report, session_id, include_context=True)
            if asyncio.get_running_loop().time() >= deadline:
                raise TimeoutError("提取仍在后台执行，请稍后读取当前对话的报告。")
            await asyncio.sleep(0.3)

    @tool(
        description=(
            "提交当前智能体撰写的财报结论，校验数字和引用并在当前对话展示报告。"
            "参数 run_id、revision 来自 prepare_financial_report；"
            "专题报告须先逐专题保存并调用 review_financial_report；"
            "发布时省略 findings。"
            "旧版报告 findings 为结构化发现数组。"
            "使用 prepare 返回的占位符规则，不能提供 HTML 或修改事实。"
            "证据不足可传空数组保存数据报告；校验失败应修正后再提交。"
        )
    )
    async def publish_financial_report(
        run_id: str, revision: str, findings: list[dict] = None
    ) -> str:
        await execution_started(
            "publish_financial_report",
            {"run_id": run_id, "revision": revision},
            "正在核对已保存版本并生成报告。",
        )
        backend, owner, session_id = scope()
        try:
            report = await asyncio.to_thread(
                backend.publish_agent_report,
                owner,
                session_id,
                run_id,
                revision,
                findings or [],
            )
        except InvalidFindings as exc:
            attempts = state.setdefault("financial_publish_failures", {})
            attempts[run_id] = attempts.get(run_id, 0) + 1
            if attempts[run_id] < 3:
                report = await asyncio.to_thread(
                    backend.get, owner, session_id, run_id, report=True
                )
                return json.dumps(
                    {
                        "chunks": [
                            {
                                "output_type": "text",
                                "content": (
                                    "财报数据已保存，正在自动修正结论的引用与格式。"
                                ),
                            }
                        ],
                        # Agent-only repair details are outside display chunks.
                        "repair": {
                            "attempt": attempts[run_id],
                            "issues": exc.details,
                            "instructions": PUBLICATION_RULES,
                            "example": publication_example(report),
                        },
                    },
                    ensure_ascii=False,
                )
            # Bound repeated failures; preserve facts and disclose that no
            # narrative passed instead of looping until the agent exhausts.
            report = await asyncio.to_thread(
                backend.publish_agent_report,
                owner,
                session_id,
                run_id,
                revision,
                [],
                rejected_count=exc.rejected_count,
            )
        state.setdefault("financial_pending", set()).discard(run_id)
        state.update(financial_report_context=report, financial_read=False)
        await progress(report)
        return _result(report, session_id)

    @tool(
        description=(
            "读取当前对话已保存的财报、真实数据及原文引用，用于继续追问或重新展示。"
            "run_id 可省略以读取当前对话最近报告；不能读取其他对话。"
            "最终回答按 answer_format_example 复制数据的 reference 字段，"
            "不直接写数字、年份、页码或带数字的原文；服务端会补齐数值和来源。"
        )
    )
    async def read_financial_report(run_id: str = "", revision: str = "") -> str:
        await execution_started(
            "read_financial_report",
            {"run_id": run_id},
            "正在读取已保存报告、财务数据和原文引用。",
        )
        backend, owner, session_id = scope()
        if run_id:
            report = await asyncio.to_thread(
                backend.get,
                owner,
                session_id,
                run_id,
                report=True,
                revision=revision or None,
            )
        else:
            report = await asyncio.to_thread(
                backend.latest_agent_report, owner, session_id
            )
        state.update(financial_report_context=report, financial_read=True)
        return _result(report, session_id, include_context=True, reading=True)

    @tool(
        description=(
            "读取一个财报专题的限定数据和任务。topic_id 来自 workflow.topics。"
            "重做已完成专题传 retry=true；不重新提取 PDF。返回保存需要的 revision。"
        )
    )
    async def get_financial_topic(
        run_id: str, topic_id: str, retry: bool = False
    ) -> str:
        await execution_started(
            "get_financial_topic",
            {"run_id": run_id, "topic_id": topic_id, "retry": retry},
            "正在读取本次分析所需的数据与原文依据。",
        )
        backend, owner, session_id = scope()
        report = await asyncio.to_thread(
            backend.get, owner, session_id, run_id, report=True
        )
        report = await asyncio.to_thread(
            backend.update_agent_workflow,
            owner,
            session_id,
            run_id,
            report["revision"],
            "start",
            topic_id=topic_id,
            retry=retry,
        )
        await remember(report)
        context = _topic_payload(report, topic_id)
        return json.dumps(
            {
                "chunks": [
                    {
                        "output_type": "text",
                        "content": "已读取专题：" + context["title"],
                    }
                ],
                "model_context": context,
            },
            ensure_ascii=False,
        )

    @tool(
        description=(
            "保存当前专题的分析 findings，字段及占位符规则与 prepare 相同。"
            "成功后直接返回下一专题数据；失败带新 revision，"
            "优先只传 patches 修正错误字段。"
            "patches=[{finding_index:索引,changes:{字段:修正值}}]，不同时传 findings。"
            "覆盖不全可用 append_findings 追加缺少的发现，可与 patches 合用。"
            "仅缺少必要数据时允许 findings=[] 并提供 missing_reason。"
        )
    )
    async def save_financial_topic(
        run_id: str,
        revision: str,
        topic_id: str,
        findings: list[dict] = None,
        missing_reason: str = "",
        patches: list[dict] = None,
        append_findings: list[dict] = None,
    ) -> str:
        await execution_started(
            "save_financial_topic",
            {"run_id": run_id, "topic_id": topic_id, "revision": revision},
            "正在校验分析中的数字、引用和解释边界，保存通过校验的内容。",
        )
        backend, owner, session_id = scope()
        report = await asyncio.to_thread(
            backend.update_agent_workflow,
            owner,
            session_id,
            run_id,
            revision,
            "save",
            topic_id=topic_id,
            findings=findings,
            missing_reason=missing_reason,
            patches=patches,
            append_findings=append_findings,
        )
        return await remember(report, active_topic=topic_id)

    @tool(
        description=(
            "所有专题保存后逐项复核。reviews 是数组，每项含 topic_id、"
            "verdict(pass/revise/insufficient)、directionChecked、scopeChecked、"
            "causalityChecked（三项均为 true）、note（无数字的具体核对说明）。"
            "Checked 表示该维度及缺口已检查，不代表结论通过；"
            "失败或缺数据专题检查缺口后也填 true，verdict 使用 insufficient。"
            "检查方向是否吻合数据、期间和口径是否一致、因果解释是否有原文支持；"
            "有问题用 revise，不得机械通过。所有专题复核通过/明确不足后后端自动发布，"
            "无需再调用 publish；仍待人工核对。"
        )
    )
    async def review_financial_report(
        run_id: str, revision: str, reviews: list[dict]
    ) -> str:
        await execution_started(
            "review_financial_report",
            {"run_id": run_id, "revision": revision},
            "正在核对结论方向、期间口径与解释依据；完成后汇总发布。",
        )
        backend, owner, session_id = scope()
        report = await asyncio.to_thread(
            backend.update_agent_workflow,
            owner,
            session_id,
            run_id,
            revision,
            "review",
            reviews=reviews,
        )
        return await remember(report)

    legacy = [
        prepare_financial_report,
        prepare_financial_comparison,
        resolve_financial_comparison,
        publish_financial_report,
        read_financial_report,
    ]
    return (
        legacy + [get_financial_topic, save_financial_topic, review_financial_report]
        if sectional
        else legacy
    )
