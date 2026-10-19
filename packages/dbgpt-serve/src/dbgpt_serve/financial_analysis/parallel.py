"""Bounded topic generation on private snapshots; only the coordinator persists."""

import asyncio
import json
import os
import time
from copy import deepcopy
from dataclasses import dataclass

from . import workflow
from .analysis import SYSTEM_PROMPT

TOPIC_PROMPT = (
    SYSTEM_PROMPT.replace("通常包含四条发现", "通常包含两到三条发现")
    + "\n只处理当前 topic_id 和 section，不能生成其他专题。"
    "不调用工具，不返回计划或复核意见。首次返回 {findings:[...]}。"
    "修复时只返回 {patches:[{finding_index:索引,changes:{字段:值}}]}，"
    "一次修复全部 issues，保留其他草稿。不要自行用多个引用拼接算式。"
    "不要把比率与它自己比较；缺失判断必须核对提供的全部期间事实。"
    "若 requiredCoverage 存在，必须实质分析全部列出科目，可超过三条发现。"
    "incomplete_topic_coverage 时优先返回 {append_findings:[新增发现]}，"
    "可同时传 patches；无需重写已通过的草稿，仍会对合并结果完整校验。"
)


@dataclass(frozen=True)
class ValidatedTopic:
    """Internal result of full validation against an immutable batch snapshot.

    This type is never populated from tool/HTTP arguments. A commit accepts only
    this topic's fields and findings, not the worker's copy of the whole report.
    """

    batch_id: str
    topic_id: str
    topic: dict
    findings: list
    error: str | None
    metrics: dict


def concurrency_limit():
    try:
        return max(1, min(6, int(os.getenv("DBGPT_FINANCIAL_CONCURRENCY", "3"))))
    except ValueError:
        return 3


class TopicGenerator:
    def __init__(self, client, model, owner, session_id):
        self.client, self.model = client, model
        self.owner, self.session_id = owner, session_id

    async def __call__(self, context):
        from dbgpt.core import ModelMessage, ModelRequest
        from dbgpt.core.interface.llm import ModelRequestContext

        response = await self.client.generate(
            ModelRequest(
                model=self.model,
                messages=[
                    ModelMessage(role="system", content=TOPIC_PROMPT),
                    ModelMessage(
                        role="human", content=json.dumps(context, ensure_ascii=False)
                    ),
                ],
                temperature=0,
                max_new_tokens=4000,
                context=ModelRequestContext(
                    user_name=self.owner, conv_uid=self.session_id, stream=False
                ),
            )
        )
        if not response.success or not response.has_text:
            raise RuntimeError("Topic generation failed")
        return response.text


async def generate_topic(snapshot, topic_id, generate, timeout=120, activity=None):
    """No shared mutable report or database access. Whole-topic deadline, 3 tries."""
    local = deepcopy(snapshot)
    context = workflow.topic_context(local, topic_id)
    if topic_id == "expenses":
        scoped_ids = {f["id"] for f in context["data"]["facts"]}
        context["requiredCoverage"] = [
            {
                "metricCode": f["metricCode"],
                "metricName": f["metricName"],
                "reference": "{{fact:" + f["id"] + "}}",
            }
            for f in snapshot["facts"]
            if f["id"] in scoped_ids
            and f["metricCode"] != "revenue"
            and f["fiscalPeriod"] == context["data"]["year"]
        ]
    metrics = {"modelCalls": 0, "inputChars": 0, "outputChars": 0, "validationMs": 0}
    started = time.monotonic()
    error = None
    try:
        for _ in range(3):
            if activity:
                await activity("repairing" if metrics["modelCalls"] else "generating")
            metrics["modelCalls"] += 1
            metrics["inputChars"] += len(TOPIC_PROMPT) + len(
                json.dumps(context, ensure_ascii=False)
            )
            raw = await asyncio.wait_for(
                generate(context), max(0.001, timeout - (time.monotonic() - started))
            )
            metrics["outputChars"] += len(raw)
            try:
                if len(raw) > 24000:
                    raise ValueError("Response too long")
                # Accept an otherwise exact JSON response in a code fence.
                text = raw.strip()
                if text.startswith("```json\n") and text.endswith("```"):
                    text = text[8:-3].strip()
                payload = json.loads(text)
                if (
                    not isinstance(payload, dict)
                    or not set(payload)
                    <= {"findings", "patches", "missing_reason", "append_findings"}
                    or not payload
                ):
                    raise ValueError("Invalid topic envelope")
                # Section is deterministic routing owned by the coordinator,
                # not a financial claim for the model to choose. Facts,
                # calculations and narratives still undergo full scoped checks.
                for finding in (payload.get("findings") or []) + (
                    payload.get("append_findings") or []
                ):
                    if isinstance(finding, dict):
                        finding["section"] = context["section"]
                for patch in payload.get("patches") or []:
                    if isinstance(patch, dict) and isinstance(
                        patch.get("changes"), dict
                    ):
                        if "section" in patch["changes"]:
                            patch["changes"]["section"] = context["section"]
                validation_start = time.monotonic()
                if activity:
                    await activity("validating")
                # Independent reports and bounded worker slots; no service lock.
                candidate = await asyncio.to_thread(
                    workflow.save_topic, deepcopy(local), topic_id, **payload
                )
                metrics["validationMs"] += round(
                    (time.monotonic() - validation_start) * 1000
                )
            except (ValueError, TypeError, workflow.SessionFileApiError):
                previous = workflow.topic(local, topic_id)
                context["repair"] = {
                    "code": "INVALID_TOPIC_RESPONSE",
                    "draftFindings": previous.get("draftFindings"),
                    "issues": previous.get("issues", []),
                    "instructions": "返回合法 findings 或 patches JSON；保留真实引用。",
                }
                error = "INVALID_TOPIC_RESPONSE"
                continue
            local = candidate
            item = workflow.topic(local, topic_id)
            error = None
            if item["status"] in workflow.TERMINAL:
                break
            context["repair"] = {
                "draftFindings": item.get("draftFindings"),
                "issues": item.get("issues", []),
                "instructions": (
                    "逐项处理所有 finding_index 和 field，采用 hint/suggested_changes。"
                    "一般仅返回 patches；缺少科目覆盖时用 append_findings 追加发现。"
                    "unsupported_* 的核查问题放入 unresolvedQuestions，"
                    "summary 保留有依据的观察，不能仅添加‘可能’来保留原因推断。"
                    "invalid_tokens 是该字段仍未通过校验的数字："
                    "年份用下面 periodReferences，"
                    "其他数值改成输入中的真实引用，不自行计算。"
                    "未知或未声明引用须使用数据中存在的 ID 并写入同一发现的 Ids。"
                    "不能构造一个不存在的引用再标注‘未提供’。保留其他已通过字段。"
                ),
                "periodReferences": [
                    "{{period:" + p + "}}" for p in context["data"]["periods"]
                ],
            }
    except (TimeoutError, asyncio.TimeoutError):
        error = "MODEL_TIMEOUT"
    except asyncio.CancelledError:
        raise
    except Exception:
        # Never persist provider exceptions, credentials or raw reasoning.
        error = "MODEL_REQUEST_FAILED"
    metrics["elapsedMs"] = round((time.monotonic() - started) * 1000)
    item = workflow.topic(local, topic_id)
    return ValidatedTopic(
        snapshot["workflow"]["parallelBatch"]["id"],
        topic_id,
        item,
        [f for f in local["findings"] if f["id"] in item["findingIds"]],
        error,
        metrics,
    )


async def analyze_topics(
    backend,
    owner,
    session_id,
    report,
    generate,
    progress=None,
    concurrency=None,
    timeout=120,
    activity=None,
):
    limit = concurrency or concurrency_limit()
    limit = max(1, min(6, limit))
    run_id = report["report"]["run"]["id"]
    # These short synchronous mutations deliberately cannot outlive cancellation
    # in an executor thread. All model work awaits outside the service lock.
    snapshot = backend.begin_parallel_topics(
        owner, session_id, run_id, report["revision"], limit
    )
    batch_id = snapshot["workflow"]["parallelBatch"]["id"]
    semaphore = asyncio.Semaphore(limit)
    active = {}

    async def notify(topic_id, phase):
        if phase:
            active[topic_id] = phase
        else:
            active.pop(topic_id, None)
        if activity:
            await activity(
                {
                    key: list(active.values()).count(key)
                    for key in ("generating", "validating", "repairing")
                }
            )

    async def worker(topic_id):
        async with semaphore, backend.parallel_topic_slots:
            try:
                return await generate_topic(
                    snapshot,
                    topic_id,
                    generate,
                    timeout,
                    activity=lambda phase: notify(topic_id, phase),
                )
            finally:
                await notify(topic_id, None)

    tasks = []
    try:
        if progress:
            await progress(snapshot)
        tasks = [asyncio.create_task(worker(t)) for t in workflow.TOPICS]
        for task in asyncio.as_completed(tasks):
            result = await task
            report = backend.merge_parallel_topic(owner, session_id, run_id, result)
            if progress:
                await progress(report)
        return report
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        backend.abort_parallel_topics(owner, session_id, run_id, batch_id)
