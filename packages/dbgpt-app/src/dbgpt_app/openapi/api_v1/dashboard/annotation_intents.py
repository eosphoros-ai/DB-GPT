"""Resolve a batch of natural-language annotations before persisting any changes."""

import asyncio
import json
from typing import Any, Dict, List, Optional

from pydantic import Field, field_validator

from .assistant_skills import dashboard_collaboration_skill
from .schemas import DashboardAnnotationIntent, DashboardSelectionTarget, StrictModel


class AnnotationIntentInput(StrictModel):
    draft_id: str = Field(min_length=1, max_length=256)
    prompt: str = Field(min_length=1, max_length=8000)
    target: DashboardSelectionTarget


class AnnotationIntentBatch(StrictModel):
    items: List[AnnotationIntentInput] = Field(min_length=1, max_length=20)
    model: Optional[str] = Field(default=None, max_length=256)
    message: str = Field(default="", max_length=8000)
    conversation: str = Field(default="", max_length=20000)
    view_context: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("view_context")
    @classmethod
    def limit_context(cls, value):
        if len(json.dumps(value, ensure_ascii=False)) > 180000:
            raise ValueError("看板上下文过大，请减少结果样本。")
        return value


class AnnotationIntentTask(StrictModel):
    intent: DashboardAnnotationIntent
    prompt: str = Field(min_length=1, max_length=4000)


class AnnotationIntentResult(StrictModel):
    draft_id: str
    tasks: List[AnnotationIntentTask] = Field(default_factory=list, max_length=3)
    question: Optional[str] = Field(default=None, max_length=1000)
    answered: bool = False


class AnnotationIntentResolution(StrictModel):
    items: List[AnnotationIntentResult] = Field(min_length=1, max_length=20)
    reply: Optional[str] = Field(default=None, max_length=12000)
    model: Optional[str] = None


INTENT_PROMPT = (
    "你是当前看板的数据协作助手，兼顾自然对话与执行规"
    "划。只输出 JSON。\n输入包含已保存看板 saved_dashb"
    "oard、当前界面 current_view（可能有未保存修改）"
    "、\n最近对话 conversation、最新消息 message，以及"
    "带完整选择上下文的批注 items。\n理解所有材料后，"
    "统一作答，不要为每条批注重新开启一段无上下文的对"
    "话。\n\n能够根据现有信息回答的建议、讨论、口径说明"
    "等，直接在 reply 中给出有内容的回答，\n对应 item "
    "设置 answered=true、tasks=[]、question=null。建"
    "议需关联实际组件和已知数据，\n不要只承诺“我会检查"
    "”，不要要求用户先选改进方向。简单闲聊也自然回应"
    "。\n需要工具验证或执行时，交给 tasks：\n- modify："
    "用户要求修改/配置图表、指标、SQL、布局或筛选器，"
    "包括沿用上文方案的执行请求。\n- “生成可验证方案，"
    "先不要直接应用”仍是 modify，由后续执行器生成待确"
    "认提案，不是纯建议。\n- 配置目标已明确时，缺少 SQ"
    "L、真实列名、枚举值或参数写法不属于意图歧义；输"
    "出 modify，\n  执行器会读取授权数据源元数据并验证"
    "，不能在本阶段臆造 SQL 或让用户代替系统查字段。\n"
    "- 当前图表 SQL 没有选出某个分类字段，不代表基础"
    "数据源没有该维度；不要据此排除组件或追问。\n  全"
    "局筛选默认联动同源且可合理绑定的组件，同一指标的"
    "卡片与仪表盘保持一致；用户可在方案中审阅范围。\n-"
    " explain：需读取更多查询口径或结果才能准确回答的"
    "解释请求。\n- anomaly：询问变化/下降/异常原因，必"
    "须由执行器依据程序异常证据作答。\n一条包含多个意"
    "图则拆分，例如“改成柱状图，并解释下降原因”拆 mod"
    "ify 和 anomaly。\n任务 prompt 要整合最新要求、目"
    "标与必要历史，成为执行器无需再猜的完整指令；\n不"
    "能新增用户未授权的目标。\n“不要改，只建议”只能回"
    "答，不能生成 modify。只要求刷新数据时告诉用户顶"
    "部刷新入口。\n只有确实缺少影响结果的关键信息时，"
    "设置 question，tasks=[]，answered=false；\nreply "
    "中先给有用的判断，再合并提出一个有针对性的问题。"
    "不要重复泛泛的追问。\n同批明确的任务继续输出 task"
    "s，不因另一条含糊而全部搁置。\n每个 draft_id 恰好"
    "返回一项；tasks 非空、question 非空、answered=tr"
    "ue 三者恰好选一。\nreply 可以在包含任务时补充说明"
    "，但不能声称任务已经执行或验证成功。\ntasks 的每"
    "项只能包含 intent 和 prompt 两个字段；intent 不"
    '是 type。\n回答示例：{"reply":"具体建议","items":'
    '[{"draft_id":"原编号","tasks":[],"answered":true'
    '}]}\n执行示例：{"reply":null,"items":[{"draft_id"'
    ':"原编号",\n"tasks":[{"intent":"modify","prompt":'
    '"将收入标题改为销售总额，口径不变"}],"answered":'
    'false}]}\n追问示例：{"reply":"有用的初步判断和一'
    '个具体问题","items":[{"draft_id":"原编号",\n"task'
    's":[],"question":"缺少的具体信息是什么？","answe'
    'red":false}]}\n若存在 format_repair，只修复上一条'
    "输出的结构，仍依据原始要求与上下文判断意图。\n"
)


def validate_intent_resolution(text: str, batch: AnnotationIntentBatch):
    cleaned = text.strip()
    if cleaned.startswith("```") and cleaned.endswith("```"):
        cleaned = cleaned.partition("\n")[2].rsplit("```", 1)[0].strip()
    resolution = AnnotationIntentResolution.model_validate(json.loads(cleaned))
    expected = [item.draft_id for item in batch.items]
    actual = [item.draft_id for item in resolution.items]
    if len(set(expected)) != len(expected) or sorted(actual) != sorted(expected):
        raise ValueError("意图识别未覆盖全部批注，请重试。")
    for item in resolution.items:
        if (
            sum(
                (
                    bool(item.tasks),
                    bool(item.question and item.question.strip()),
                    item.answered,
                )
            )
            != 1
        ):
            raise ValueError("意图识别结果不完整，请重试。")
        if item.answered and not (resolution.reply and resolution.reply.strip()):
            raise ValueError("助手未返回回答，请重试。")
        if any(not task.prompt.strip() for task in item.tasks):
            raise ValueError("意图识别返回了空要求，请重试。")
        intents = [task.intent for task in item.tasks]
        if len(set(intents)) != len(intents):
            raise ValueError("意图识别返回了重复操作，请重试。")
    by_id = {item.draft_id: item for item in resolution.items}
    return resolution.model_copy(update={"items": [by_id[key] for key in expected]})


async def resolve_annotation_intents(
    batch: AnnotationIntentBatch, llm_client=None, *, dashboard_context=None
):
    from dbgpt.core import ModelMessage, ModelRequest

    if llm_client is None:
        from dbgpt._private.config import Config
        from dbgpt.component import ComponentType
        from dbgpt.model.cluster import WorkerManagerFactory
        from dbgpt.model.cluster.client import DefaultLLMClient

        manager = (
            Config()
            .SYSTEM_APP.get_component(
                ComponentType.WORKER_MANAGER_FACTORY, WorkerManagerFactory
            )
            .create()
        )
        llm_client = DefaultLLMClient(manager, auto_convert_message=True)

    async def resolve():
        model = batch.model
        if not model:
            models = await llm_client.models()
            if not models:
                raise ValueError("请先配置可用模型，再发送批注。")
            model = models[0].model
        payload = {
            "saved_dashboard": dashboard_context or {},
            "current_view": batch.view_context,
            "conversation": batch.conversation,
            "message": batch.message,
            "items": [
                {
                    "draft_id": item.draft_id,
                    "prompt": item.prompt,
                    "target": item.target.model_dump(mode="json"),
                }
                for item in batch.items
            ],
        }
        for attempt in range(2):
            output = await llm_client.generate(
                ModelRequest.build_request(
                    model=model,
                    messages=[
                        ModelMessage(
                            role="system",
                            content=dashboard_collaboration_skill()
                            + "\n\n"
                            + INTENT_PROMPT,
                        ),
                        ModelMessage(
                            role="human",
                            content=json.dumps(payload, ensure_ascii=False),
                        ),
                    ],
                    temperature=0,
                    max_new_tokens=8192,
                )
            )
            if output.error_code:
                raise ValueError("模型暂时无法识别批注意图，请重试。")
            try:
                resolution = validate_intent_resolution(output.text, batch)
            except ValueError as error:
                if attempt:
                    raise
                # Planning has no side effects. Repair formatting once, never guess
                # an action locally or retry an already executed modification.
                payload["format_repair"] = {
                    "previous_response": output.text[:16000],
                    "validation_error": str(error)[:600],
                }
                continue
            return resolution.model_copy(update={"model": model})

    return await asyncio.wait_for(resolve(), timeout=45)
