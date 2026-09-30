"""Financial report tools owned by the current conversational agent turn."""

import asyncio
import json
from pathlib import Path
from uuid import uuid4

from dbgpt.agent.resource.tool.base import tool
from dbgpt_serve.financial_analysis.analysis import (
    REFERENCE,
    SYSTEM_PROMPT,
    InvalidFindings,
    model_context,
)
from dbgpt_serve.financial_analysis.questions import (
    reference_only_answer,
    validate_answer,
)
from dbgpt_serve.financial_analysis.workflow import TOPICS, topic_context

SECTIONAL_RULES = """本报告采用专题流程，不要一次提交整份报告的 findings。
按 workflow.topics 逐一调用 get_financial_topic 读取当前专题的数据，
由你分析后调用 save_financial_topic 保存两到三条有依据的发现（数据有限可以减少）。
经营表现、扣非与利润构成、毛利变化、费用变化、现金流、资产负债都要处理。
每条包含判断、引用、反向信息和待核查事项，不能仅重复数字；不得编造变化原因。
仅对 missingRequiredMetrics 非空的专题可用 missing_reason 说明缺项并提交空 findings。
保存失败只修当前专题，使用返回的新 revision；不要重新 prepare 或重算 PDF。
全部专题处理后调用 review_financial_report，逐项检查变化方向、期间/口径和原因依据。
复核必须覆盖全部专题，每项给出 topic_id、verdict（pass/revise/insufficient）、
directionChecked:true、scopeChecked:true、causalityChecked:true、note（不含数字的具体核对说明）。
需要修订就再次读取/保存对应专题，然后重新复核。最后调用 publish_financial_report，
只传 run_id、最新 revision，不传 findings。不得在未发布时 terminate。
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
## 财报分析与当前对话中的报告
分析年度报告时，先加载 financial-report-analyzer 技能，并使用
prepare_financial_report 提取和计算，然后由你根据返回的事实与计算撰写结论，
按工具返回的专题流程逐一分析、保存、复核，最后调用 publish_financial_report。
不使用 html_interpreter、旧 HTML 模板或自行编写网页来替代财报组件。
工具返回的财报已显示在当前对话右侧，不要让用户跳转 /financial-analysis。
后续追问先调用 read_financial_report 读取当前对话的报告，不重复提取 PDF，
只引用已有事实、计算及原文，缺少数据就明确说明，不自行计算新指标或补造原因。
发布后用简短摘要完成回答，保留“部分分析”和待核对信息。
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
            return SECTIONAL_RULES
        return (
            "财务数据已提取，但你尚未发布分析。请在本轮调用 "
            "publish_financial_report 提交 findings，再完成回答。"
            "不要用未来计划代替执行；证据不足可以提交空 findings 数组。"
        )
    if state.get("financial_report_context"):
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


def _artifact(report, session_id):
    return {
        "output_type": "html",
        "content": {
            "kind": "financial-report",
            "title": report["report"]["companyName"] + "财报分析",
            "runId": report["report"]["run"]["id"],
            "sessionId": session_id,
            "revision": report["revision"],
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


def _result(report, session_id, *, include_context=False, reading=False):
    workflow_summary = None
    if report.get("workflow"):
        flow = report["workflow"]
        workflow_summary = {
            key: flow.get(key)
            for key in ("version", "status", "publishedAt", "review", "dataQuality")
        }
        workflow_summary["topics"] = [
            {key: value for key, value in topic.items() if key != "history"}
            for topic in flow["topics"]
        ]
    summary = {
        "run_id": report["report"]["run"]["id"],
        "revision": report["revision"],
        "analysis": report.get("analysis"),
        "findings": report["findings"],
        "workflow": workflow_summary,
    }
    if include_context:
        if reading:
            summary["answer_instructions"] = (
                "直接回答当前追问，无需重新发布报告。数字使用 {{fact:真实ID}} 或 "
                "{{calculation:真实ID}} 占位符，服务端会替换真实值。"
                "不要直接写年份、金额、比率或页码，也不要追加单位。"
                "可提示用户在右侧报告查看依据；来源页码由服务端补齐。"
                "资料不足明确说明，不补造原因。"
            )
        else:
            summary["publication_instructions"] = (
                SECTIONAL_RULES + SYSTEM_PROMPT[SYSTEM_PROMPT.index("每条发现字段") :]
                if report.get("workflow")
                else PUBLICATION_RULES
            )
            summary["publication_example"] = publication_example(report)
        # Put format instructions before the large data payload, and provide
        # copyable references so the agent does not have to reconstruct syntax.
        context = model_context(report)
        for kind, key in (("fact", "facts"), ("calculation", "calculations")):
            for item in context[key]:
                item["reference"] = "{{" + kind + ":" + item["id"] + "}}"
        summary["data"] = context
    return json.dumps(
        {
            "chunks": [
                _artifact(report, session_id),
                {
                    "output_type": "text",
                    "content": json.dumps(summary, ensure_ascii=False),
                },
            ]
        },
        ensure_ascii=False,
    )


def finalize_financial_answer(content, state):
    """Render/validate agent references before both SSE final and history save."""
    report = state.get("financial_report_context")
    if not report:
        return content
    if not state.get("financial_read"):
        # The narrative lives in validated findings. Completion text reflects
        # persisted status, rather than an unvalidated claim of full coverage.
        partial = report.get("analysis", {}).get("status") != "completed"
        return (
            ("当前为部分分析。" if partial else "分析已完成。")
            + report["agent"]["summary"]
            + "\n\n报告已在当前对话右侧展示，可查看数据、原文依据与下载。"
        )
    references = set(REFERENCE.findall(content))
    raw = json.dumps(
        {
            "answer": content,
            "factIds": [ref for kind, ref in references if kind == "fact"],
            "calculationIds": [
                ref for kind, ref in references if kind == "calculation"
            ],
            "evidenceExcerptIds": [],
            "insufficientEvidence": not references,
        },
        ensure_ascii=False,
    )
    context = model_context(report)
    try:
        answer = validate_answer(raw, context, report)
    except ValueError:
        try:
            answer = reference_only_answer(raw, context, report)
        except ValueError:
            return "回答未通过数字或引用校验，请在右侧报告查看依据或重新提问。"
    pages = sorted(
        {
            e["page"]
            for e in report["evidence"]
            if e["id"] in answer["evidenceExcerptIds"]
        }
    )
    suffix = (
        (
            "\n\n来源：原 PDF 物理第 "
            + "、".join(map(str, pages))
            + " 页，可在右侧报告的证据中查看原文。"
        )
        if pages
        else ""
    )
    return answer["answer"] + suffix


def make_financial_tools(state, *, service=None, stream_callback=None, sectional=True):
    """Bind owner/session to trusted turn state, never to model arguments."""

    def scope():
        owner, session_id = state.get("owner_id"), state.get("conv_id")
        if not owner or not session_id:
            raise ValueError("当前对话身份尚未就绪。")
        return service or _service(), owner, session_id

    async def progress(report=None, stage=None):
        if not sectional:
            return
        tasks = []
        if report:
            for step in report["steps"]:
                status = step["status"]
                tasks.append(
                    {
                        "content": step["title"]
                        + ("：" + step["detail"] if status == "failed" else ""),
                        "status": {
                            "completed": "completed",
                            "failed": "cancelled",
                            "running": "in_progress",
                        }.get(status, "pending"),
                        "priority": "high",
                    }
                )
        else:
            names = [
                ("extract", "读取并提取 PDF 财务数据"),
                ("calculate", "核对口径并计算指标"),
                ("save", "保存财务数据"),
            ]
            current = next((i for i, (key, _) in enumerate(names) if key == stage), 0)
            tasks = [
                {
                    "content": title,
                    "status": "completed"
                    if i < current
                    else "in_progress"
                    if i == current
                    else "pending",
                    "priority": "high",
                }
                for i, (_, title) in enumerate(names)
            ]
            tasks += [
                {"content": values[0], "status": "pending", "priority": "high"}
                for values in TOPICS.values()
            ]
            tasks += [
                {"content": title, "status": "pending", "priority": "high"}
                for title in ("复核方向、口径与解释依据", "汇总发布报告")
            ]
        state["financial_plan"] = tasks
        if stream_callback:
            await stream_callback("financial.progress", {"tasks": tasks})

    async def remember(report, *, pending=True):
        state.update(financial_report_context=report, financial_read=False)
        if pending:
            state.setdefault("financial_pending", set()).add(
                report["report"]["run"]["id"]
            )
        await progress(report)
        return _result(report, state["conv_id"])

    @tool(
        description=(
            "提取当前对话 PDF 年报并执行确定性财务计算。"
            "返回原文引用、数字和待分析报告。"
            "你必须随后用 publish_financial_report 提交自己的结构化结论。"
            "file_id 可省略（仅一个 PDF 时）；多文件时必须指定当前附件的 file_id。"
        )
    )
    async def prepare_financial_report(file_id: str = "") -> str:
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
        )
    )
    async def read_financial_report(run_id: str = "") -> str:
        backend, owner, session_id = scope()
        if run_id:
            report = await asyncio.to_thread(
                backend.get, owner, session_id, run_id, report=True
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
        context = topic_context(report, topic_id)
        context.update(
            run_id=run_id,
            revision=report["revision"],
            publication_instructions=PUBLICATION_RULES.replace(
                "publish_financial_report", "save_financial_topic"
            ).replace("通常四条", "通常两到三条"),
        )
        return json.dumps(
            {
                "chunks": [
                    {
                        "output_type": "text",
                        "content": json.dumps(context, ensure_ascii=False),
                    }
                ]
            },
            ensure_ascii=False,
        )

    @tool(
        description=(
            "保存当前专题的分析 findings，字段及占位符规则与 prepare 相同。"
            "只修改该专题；失败反馈带新 revision，仅重试该专题。"
            "仅缺少必要数据时允许 findings=[] 并提供 missing_reason。"
        )
    )
    async def save_financial_topic(
        run_id: str,
        revision: str,
        topic_id: str,
        findings: list[dict],
        missing_reason: str = "",
    ) -> str:
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
        )
        return await remember(report)

    @tool(
        description=(
            "所有专题保存后逐项复核。reviews 是数组，每项含 topic_id、"
            "verdict(pass/revise/insufficient)、directionChecked、scopeChecked、"
            "causalityChecked（三项均为 true）、note（无数字的具体核对说明）。"
            "检查方向是否吻合数据、期间和口径是否一致、因果解释是否有原文支持；"
            "有问题用 revise，不得机械通过。复核通过仍待人工核对。"
        )
    )
    async def review_financial_report(
        run_id: str, revision: str, reviews: list[dict]
    ) -> str:
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

    legacy = [prepare_financial_report, publish_financial_report, read_financial_report]
    return (
        legacy + [get_financial_topic, save_financial_topic, review_financial_report]
        if sectional
        else legacy
    )
