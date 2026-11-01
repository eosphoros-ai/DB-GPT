"""Dedicated report sub-agent.

The lead agent owns analysis; exactly one child owns the report. The child
shares the lead's ``react_state``, so the rendered presentation, the repair
checkpoint and the artifact sink stay on the turn that persists them, while the
child's own ReAct loop, memory and step budget stay separate.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from pathlib import Path
from typing import Any, Dict, Optional, Sequence

from dbgpt.agent.expand.actions.react_action import Terminate
from dbgpt.agent.resource import ToolPack
from dbgpt.agent.resource.tool.base import tool
from dbgpt.agent.util.llm.llm import LLMConfig, LLMStrategyType
from dbgpt.core import PromptTemplate
from dbgpt.core.interface.report_capture import read_artifact_result

from ..tools.html_interpreter import (
    _validate_requested_knowledge_bindings,
    make_html_interpreter,
    report_template_contract,
)
from ..tools.read_file import make_read_file
from ..tools.report_evidence import make_report_evidence_manifest
from ..tools.report_repair import (
    MAX_DOCUMENT_ATTEMPTS,
    MAX_INVOCATION_FAILURES,
    MAX_PREFLIGHT_ATTEMPTS,
    MAX_RENDER_ATTEMPTS,
    render_saved_report,
)
from ..tools.report_spec import ReportSection

logger = logging.getLogger(__name__)

REPORT_TEMPLATE_PATH = "business-report/templates/business_report.html"
REPORT_AGENT_TIMEOUT = 900
# Rendering is cheap (the spec is small and the template is fixed), so the owner
# gets room to append the sections a completeness gate is still waiting for.
REPORT_AGENT_MAX_RETRY = (
    MAX_DOCUMENT_ATTEMPTS
    + MAX_PREFLIGHT_ATTEMPTS
    + MAX_RENDER_ATTEMPTS
    + MAX_INVOCATION_FAILURES
    + 2
)
REPORT_AGENT_RESULT_MAX_CHARS = 4000

REPORT_AGENT_PROMPT_TEMPLATE = """\
你是本次分析的报告负责人。分析已经完成并已被捕获，绝不重跑分析，绝不手写报告 HTML。

严格按以下流程执行：

1. 先调用 `report_evidence_manifest(artifact_types=["sql","python","chart"])` 拿到
   结果目录，按章节的列名和产物语义选择真实 ID。
   再用 artifact_ids + detail=true 读取所需结果（每次至多十二个产物）；目录不是结果。
   大型嵌套结果用 selectors={"真实ID":{"field":"真实字段","path":["子结果"]}}
   在同一清单工具中定向读取，避免只读到截断预览就误认结果缺失。
   同时读取用于指标口径的知识库切片。没有拿到结果字段和原文就不要猜数字或引用。
   知识库检索不等于正文引用。先用 artifact_types=["reference"] 查看切片目录，
   再选择与当前口径有关的 artifact_ids + detail=true 阅读原文。
   每个实际采用的口径在对应章节增加 note={label:"知识库口径",
   parts:["本章采用的定义或方法"],ref:{artifact_id:"真实 reference ID",quote:"原文中的短句"}}。
   不把所有切片挂到整页，不把知识库 reference 用作计算数值的来源。
   知识库是分析依据，不是报告正文素材清单。只解释本次实际使用、影响解读的口径，
   每个口径仅解释一次；只用简短的章节 note（黄色说明框），全文通常不超过五条。
   不逐条复制治理规则、质量检查清单或工具约束，不添加未分析指标的定义。
   不连续追加“口径提示”段落，不重复已有分析章节。完整原文由引用来源抽屉查看。
   不在 intro 中放置知识库原文、示例口径写法或重复说明；note.ref 提供溯源链接，
   note.parts 用自己的话概括实际采用的口径，不输出整段切片或 Markdown 表格。
   SQL、函数参数和示例常量放在 code 标签中；它们是方法示例，不是观测指标。
   目录或详情出现 persisted-output 时，用 read_file 读取对应文件，不能根据截断
   预览认定某个分析产物不存在。目录缓存不代表新子代理已经读到结果。
2. 首次提交：`html_interpreter(template_path="__TEMPLATE_PATH__",
   title=<报告标题>, data={"REPORT_SPEC": {...}})`。`data` 必须是 JSON **对象**，
   不能是转义后的 JSON 字符串。所有展示值都是引用节点
   `{"artifact_id": "<manifest 里的 ID>", "field"/"path": ...}`；表格只写
   `{"artifact_id": ..., "columns": [...]}` 让引擎展开行，绝不要逐个单元格粘贴。
   Python 的嵌套表在 table 中提供真实 field/path，优先选含 rows 和 columns 的对象；
   表格和每个单元格都会保留完整来源路径。
   正文里的每个实际数值都必须是引用节点，不能把记忆里的数值写到普通字符串。
   同一段里别的值有引用，也不能替代这个值的引用。若某个指标不值得单独写，展示
   产物驱动表格并作无数字总结。未捕获的合计/差值不得伪造引用，可先作定性说明。
   标题、scope、KPI 标签、建议标题使用描述性文字，观测数值和门店编号放在支持引用
   的 intro/parts 或表格中，不把这些数值塞进纯文本标签。
   REPORT_TEMPLATE_SPEC_INVALID 会一次列出全部未绑定位置和结果产物目录；全部修好
   后再提交，不能仅增加一个 section/KPI 引用来遮盖未绑定数字。
   选择器按产物类型选：SQL 产物用
   `{"path": ["rows", <i>, "<column>"]}`；`{"field": ...}` 用于 Python 产物
   （字段名抄 manifest 的 `result_selector_examples`）。写错会得到
   `RESULT_SELECTOR_INVALID` 并列出可用字段。
3. 渲染返回错误时只改 spec：`retry_saved=true` + `data`。REPORT_SPEC 只替换给出的
   顶层字段；sections/kpis 是完整替换列表。删除旧的错误顶层字段时将它设为 null。
   添加新片段用 REPORT_SPEC_APPEND。
   错误信息里已给出 artifact、selector 以及 `Available result keys`，直接用这些名字。
   若提示参数被输出上限截断，就把 spec 改小再发。
4. 报告较长时分片构建：先 `data={"REPORT_SPEC": <第一部分>}`，再用
   `append_report_sections(sections=[<一个新章节>])` 追加，避免重发整份报告。
   持续追加直到用户要求的每个部分都存在。
   覆盖检查会列出未写进正文的分析任务及真实产物 ID；必须补充对应解读和表格，
   不能只在建议中引用它们。先写完整分析章节，再写建议。
5. 报告必须覆盖用户明确要求的交付物，尤其是"改进建议"：放在标题含"建议"的章节里，
   用 `recommendations`，条数不少于用户要求的数量（每条一个 `<li>`）。
   REPORT_REQUIREMENT_MISSING 使用独立的文档组装预算，继续追加缺失建议；
   如果仅缺建议，调用 append_report_sections，提交一个标题含“建议”、包含
   recommendations 数组的章节。每条包含 title 和 lines[].parts，不能重发分析章节。
   只有工具返回 retryable=false 时才停止修复，并准确说明未完成。
6. 一旦某次渲染返回 HTML 就立即停止，用一行状态说明 terminate。
7. 结果确实缺少报告所需的合计、差值或比例时，调用 request_report_calculation，
   提交计算名称、明确公式和真实 SQL/Python 输入 ID，然后 terminate。主代理只补算
   这一项，再由你复用已保存 spec 继续；不得编造引用或重做完整分析。
8. 图表产物仅放 sections[].chart，不能放 KPI/intro 数值引用。图片图表只需
   {"refs":["真实 chart ID"],"caption":"标题"}，引擎从产物读取图片地址。
   生产 Python 的 ID 与图片 chart ID 不同，按目录中的 input_artifact_ids 查找对应图表。
   若 Python 已输出完整 ECharts option，可用 chart={refs:["该 Python ID"],caption:"标题"}；
   引擎直接绘制已捕获配置。没有有效图表时保留已有表格和解读，不要猜图片地址或重跑分析。
   SQL/Python 二维结果无需再查询或画图片：章节 table 选择真实产物和列名，
   引擎自动将选中的可绘制结果准备为交互式图表，保留来源、行序和数值。
   趋势、类别对比和数值关系按真实字段类型绘制，各指标使用独立坐标轴。
   按分析目的自由选择完整 ECharts 的图表类型，不限于自动选择的类型。
   用 chart={caption:"标题",producer:{artifact_id:"真实ID",field/path:...},
   option:{...完整 ECharts JSON 配置...}}；不需要重复查询或编写画图 Python。
   option 支持所有内置 series 类型及组合、多坐标系、dataset/encode、dataZoom 等。
   默认 dataset 从 producer 的 rows/columns 注入；用 encode 指定真实列名。
   series.data/nodes/links 或 dataset.source 必须用 {artifact_id,field/path} 引用
   已捕获数据，也可以用引用节点组合结构，禁止手填观测数据。
   树图、桑基图、关系图、箱线图、K线等选择已经捕获的对应结构；缺失转换数据时
   用 request_report_calculation 请求明确转换，不能把它们退化成柱状图。
   地图用 chart.maps={地图名称:{artifact_id,field/path}} 选择捕获的 GeoJSON，
   option 中 map 使用同名。无需 refs，工具自动补齐全部来源和图表 ID。
   JavaScript 函数和第三方扩展不能写进 JSON option；这类可复用分析生成的图片。
   若建议包含人为设定的数值目标，在建议的引用节点增加 proposal 字段；它会显示为
   “建议目标（非观测值）”，artifact_id + field/path 仍指向支持建议的真实依据。

必须使用模板实际支持的结构，不能根据名称猜测字段：
`{"title":"报告标题","kpis":[{"label":"指标","ref":{"artifact_id":"真实ID",
"path":["rows",0,"真实列名"]}}],"sections":[{"heading":"经营表现",
"intro":[["说明文字",{"artifact_id":"真实ID","path":["rows",0,"真实列名"]}]],
"recommendations":[{"title":"具体行动","badge":"优先",
"lines":[{"label":"依据","parts":["说明文字",{"artifact_id":"真实ID",
"path":["rows",0,"真实列名"]}]}]}]}]}`。
KPI 必须用 ref，不能用 value；正文段落用 intro（段落数组，每段是 parts 数组）；
建议必须在 sections[].recommendations，每条使用 title 和 lines[].parts。
禁止 placeholders、sections[].parts、顶层 recommendations，模板不会渲染它们。

禁止调用 sql_query / execute_analysis / python / shell / 技能类工具；禁止传
`html` 或 `file_path`；不要重复已经接受过的片段。
"""  # noqa: E501


def report_agent_prompt(
    template_path: str = REPORT_TEMPLATE_PATH,
    template_text: str | None = None,
    injected_fields: Sequence[str] = (),
    language: str = "zh",
) -> str:
    """Fill the fixed procedure with the template this turn renders from."""
    language_instruction = (
        "\nThe user requested English. Write every user-facing report title, subtitle, "
        "scope, KPI label, section heading, chart caption, note, recommendation, "
        "and narrative in English. Keep source quotations in their original "
        "language. When using REPORT_SPEC, set its language to 'en'. "
        "Write your terminate output and every status message in English too. "
        "Do not translate SQL field "
        "names, artifact IDs, or knowledge-base names.\n"
        if language == "en"
        else "\n报告标题、章节、指标标签、图注、建议和正文使用中文。\n"
    )
    if template_text is not None:
        contract = report_template_contract(template_text)
        if contract["mode"] == "placeholders":
            fields = [
                field
                for field in contract["fields"]
                if not field.startswith("ARTIFACT_ID_") and field not in injected_fields
            ]
            return (
                "你是报告负责人，复用已经完成的分析，补齐报告内容并渲染。\n"
                "当前模板是 "
                f"{template_path}"
                "，使用具名占位符，不使用业务 REPORT_SPEC "
                "结构。\n"
                "模板字段：" + json.dumps(fields, ensure_ascii=False) + "。\n"
                "程序自动注入的字段（不要提交或复制）："
                + json.dumps(list(injected_fields), ensure_ascii=False)
                + "。\n"
                "先调用 report_evidence_manifest 查看产物目录，再用 artifact_ids + "
                "detail=true "
                "读取所需统计结果和真实选择器。Available result keys 是实际结果字段。\n"
                "result_structure 给出真实字段和数组长度；预览截断不代表结果缺失。"
                "用 selectors 定向读取需要的子结果；错误中的 valid_references "
                "是可直接复制的实际路径，"
                "不要盲信主代理提供的路径，更不能因为预览截断而要求重跑分析。\n"
                "JSON 数据可能包在一个字段中；引用必须包含该 field 和内部 "
                "path，不能猜字段。\n"
                "把字段直接放在 data 对象中，调用 html_interpreter(template_path="
                + json.dumps(template_path)
                + ", title=报告标题, data=字段对象)。\n"
                "已有模板时可 retry_saved=true + data 更新占位符；"
                "REPORT_SPEC_APPEND 只用于业务 spec 模板，本模板不使用它。\n"
                "正文可以是 HTML 字符串或段落数组，每段由文字和真实引用节点组成。"
                "引用用 {artifact_id,field,path,format}，引擎读取数值并绑定来源。"
                "不要把段落数组序列化成字符串，不要抄写未经引用的数值。"
                "已捕获的 JSON 图表字段由引擎自动注入，不要重新计算或复制。\n"
                "需要模板预设以外的图表时，在 data 增加 REPORT_CHARTS 数组。"
                "每项用 {caption,producer:{artifact_id,field/path},option:完整ECharts配"
                "置}，"
                "类型不限于模板预设；默认 dataset 注入 producer 的实际 rows/columns。"
                "series.data/nodes/links、dataset.source 用 "
                "{artifact_id,field/path} "
                "引用，"
                "禁止手填观测数据。地图 maps={名称:{artifact_id,field/path}} "
                "选择捕获的 "
                "GeoJSON。"
                "图表缺少数据转换时调用 request_report_calculation，只补算所需结构。\n"
                '有知识库切片时，用 artifact_types=["reference"] 查看目录，再按真实 ID '
                "阅读原文。"
                "每个采用的口径必须在对应正文段落加入 {artifact_id:真实referenc"
                "eID,quote:原文短句} "
                "引用节点。"
                "这是知识库依据的可点击链接；计算数值仍用 SQL/Python "
                "引用。只引用支持该段的切片。\n"
                "仅简要说明本次实际采用且影响解读的口径，同一口径只解释一次，"
                "全文通常不超过五条。不得逐条复制知识库检查清单、工具约束或未分析"
                "指标的定义，不连续追加口径提示或重复分析章节。完整原文在来源抽屉"
                "查看。知识库口径仅放在黄色说明框，不在正文重复输出原文、方法示例"
                "或整段切片。SQL、函数参数和示例常量放在 code 标签中。\n"
                "可以分次提交较短的 data，每次只补充几个正文占位符，程序保留此前内容。"
                "局部无法核验的文字数值会标注缺失；不要为了这类问题重跑分析或重复整份报告。\n"
                "必须补齐各维度解读和结论建议，不只写摘要；分别解释现象、可能原因、"
                "业务影响和建议，区分相关性与因果推断。保留已有内容，建议满足用户要求。\n"
                "禁止调用 sql_query、技能脚本或分析工具，禁止传 html/file_path，"
                "只修改模板 data；停止条件为正式 HTML 已返回或 retryable=false。"
                + language_instruction
            )
    return (
        REPORT_AGENT_PROMPT_TEMPLATE.replace(
            "__TEMPLATE_PATH__", template_path or REPORT_TEMPLATE_PATH
        )
        + language_instruction
    )


REPORT_AGENT_PROMPT = report_agent_prompt()


def _knowledge_binding_error(state: Dict[str, Any]) -> str | None:
    """Check the actual rendered content, not whether retrieval happened."""
    sink = state.get("_report_artifact_sink")
    references = (
        {
            artifact.artifact_id: artifact
            for artifact in sink.snapshot()
            if artifact.status == "succeeded"
            and artifact.type == "reference"
            and artifact.reference_type == "knowledge"
        }
        if sink
        else {}
    )
    html = (state.get("_report_presentation") or {}).get("content") or state.get(
        "_report_pending_html", ""
    )
    return _validate_requested_knowledge_bindings(html, state, references)


def select_report_template(react_state: Dict[str, Any], skills_dir: str) -> str:
    """Reuse the saved template, otherwise prefer the executed skill's template."""
    saved = react_state.get("_report_saved_arguments") or {}
    established = react_state.get("_report_template_path") or saved.get("template_path")
    if established:
        return established
    root = Path(skills_dir).expanduser().resolve()
    sink = react_state.get("_report_artifact_sink")
    for artifact in reversed(sink.snapshot() if sink else []):
        skill_name = artifact.metadata.get("skill_name")
        if artifact.status != "succeeded" or not isinstance(skill_name, str):
            continue
        skill_path = (root / skill_name).resolve()
        if not skill_path.is_relative_to(root):
            continue
        candidates = sorted((skill_path / "templates").glob("*.html"))
        if len(candidates) == 1:
            return candidates[0].relative_to(root).as_posix()
    return REPORT_TEMPLATE_PATH


def make_request_report_calculation(react_state: Dict[str, Any]):
    """Hand one missing calculation to the lead, without executing analysis here."""

    @tool(
        description=(
            "报告缺少已捕获结果时，把唯一缺失的计算交回主代理。提供计算名称、公"
            "式或计算步骤、真实 SQL/Python 输入产物 "
            "ID；随后 terminate。不得请求重跑分析。"
        )
    )
    async def request_report_calculation(
        name: str, calculation: str, source_artifact_ids: list[str]
    ) -> str:
        sink = react_state.get("_report_artifact_sink")
        by_id = {item.artifact_id: item for item in sink.snapshot()} if sink else {}
        ids = list(dict.fromkeys(source_artifact_ids))
        if (
            not name.strip()
            or not calculation.strip()
            or not ids
            or any(
                item not in by_id
                or by_id[item].status != "succeeded"
                or by_id[item].type not in {"sql", "python"}
                for item in ids
            )
        ):
            return json.dumps(
                {
                    "status": "invalid",
                    "error": (
                        "Provide a calculation and real succeeded SQL/Python source "
                        "IDs."
                    ),
                }
            )
        pending = react_state.get("_report_missing_calculation")
        if pending and not pending.get("result_artifact_id"):
            return json.dumps(
                {"status": "needs_analysis", "missing_calculation": pending},
                ensure_ascii=False,
            )
        requests = react_state.get("_report_calculation_requests", 0)
        if requests >= 3:
            react_state["_report_calculation_exhausted"] = True
            react_state["_report_html_error"] = (
                "REPORT_CALCULATION_LIMIT_REACHED: preserve the draft and "
                "completed artifacts"
            )
            return json.dumps(
                {
                    "status": "failed",
                    "retryable": False,
                    "error": (
                        "Missing-calculation handoff limit reached; preserve the draft "
                        "and existing "
                        "artifacts."
                    ),
                }
            )
        # Copy immutable captured results; this is input material, not a computed
        # artifact and not a new execution path.
        try:
            inputs = {item: read_artifact_result(by_id[item]) for item in ids}
        except (ValueError, TypeError, OSError) as error:
            return json.dumps({"status": "invalid", "error": str(error)})
        from ..tools.report_repair import _checkpoint_path

        path = _checkpoint_path(react_state.get("conv_id")).with_name(
            "calculation-inputs.json"
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(inputs, ensure_ascii=False, allow_nan=False), encoding="utf-8"
        )
        request = {
            "name": name,
            "calculation": calculation,
            "source_artifact_ids": ids,
            "input_path": str(path),
            "result_artifact_id": None,
        }
        react_state["_report_calculation_requests"] = requests + 1
        react_state["_report_missing_calculation"] = request
        from ..tools.report_repair import save_execution_checkpoint

        save_execution_checkpoint(
            react_state,
            react_state.get("_report_html_error")
            or "REPORT_CALCULATION_REQUIRED: " + name,
        )
        return json.dumps(
            {
                "status": "needs_analysis",
                "missing_calculation": request,
                "instruction": (
                    "terminate now; the lead will capture only this calculation "
                    "using code_interpreter."
                ),
            },
            ensure_ascii=False,
        )

    return request_report_calculation


def make_append_report_sections(react_state: Dict[str, Any], renderer: Any):
    """Append small, validated sections through the existing evidence renderer."""

    @tool(
        description=(
            "Append one or two NEW sections to the saved business report, then "
            "validate/render it. Existing sections, charts and evidence are kept. "
            "Use this instead of resending the whole REPORT_SPEC. If only "
            "recommendations are missing, submit one section with heading "
            "改进建议 and recommendations containing title and lines[].parts. "
            "Parts are strings or real artifact reference objects."
        )
    )
    async def append_report_sections(sections: list[dict]) -> str:
        saved = react_state.get("_report_saved_arguments") or {}
        if not saved.get("template_path") or not (saved.get("data") or {}).get(
            "REPORT_SPEC"
        ):
            raise ValueError("Initialize the report template before appending sections")
        if not 1 <= len(sections) <= 2:
            raise ValueError("Append one or two new sections per call")
        validated = [
            ReportSection.model_validate(section).model_dump(exclude_unset=True)
            for section in sections
        ]
        return await renderer(
            retry_saved=True,
            data={"REPORT_SPEC_APPEND": {"sections": validated}},
        )

    return append_report_sections


async def build_report_agent(
    *,
    react_state: Dict[str, Any],
    llm_client: Any,
    skills_dir: str,
    model_name: Optional[str] = None,
):
    """Build the report agent. Its tools write into the lead's ``react_state``."""
    from dbgpt.agent import AgentContext, AgentMemory
    from dbgpt.agent.core.memory.gpts import DefaultGptsPlansMemory, GptsMemory
    from dbgpt.agent.expand.tool_calling_agent import ToolCallingReActAgent
    from dbgpt_serve.agent.agents.db_gpts_memory import MetaDbGptsMessageMemory

    conv_id = str(react_state.get("conv_id") or "report")
    # Each invocation reconstructs its context from the shared checkpoint.
    # Reusing a child's conversation replays stale stop instructions and tool
    # history even though the lead explicitly requested a new repair turn.
    sub_conv_id = f"{conv_id}__report_{uuid.uuid4().hex}"
    template_path = select_report_template(react_state, skills_dir)
    skills_root = Path(skills_dir).expanduser().resolve()
    template_file = (skills_root / template_path).resolve()
    if not template_file.is_relative_to(skills_root):
        raise ValueError("REPORT_TEMPLATE_INVALID: template escapes skills directory")
    template_text = template_file.read_text(encoding="utf-8")
    contract = report_template_contract(template_text)
    spec_mode = contract["mode"] == "spec"
    react_state["_report_template_path"] = template_path
    react_state["_report_template_contract"] = contract
    react_state["_report_lock_after_completion"] = True
    if _knowledge_binding_error(react_state):
        react_state["_report_require_knowledge_bindings"] = True
    from ..tools.html_interpreter import _template_result_sources

    sink = react_state.get("_report_artifact_sink")
    captured_fields = _template_result_sources(sink.snapshot() if sink else [])
    injected_fields = sorted(set(captured_fields).intersection(contract["fields"]))

    sub_gpt_memory = GptsMemory(
        plans_memory=DefaultGptsPlansMemory(),
        message_memory=MetaDbGptsMessageMemory(),
    )
    sub_gpt_memory.init(sub_conv_id, enable_vis_message=False, publish_messages=False)
    sub_agent_memory = AgentMemory(gpts_memory=sub_gpt_memory)

    renderer = make_html_interpreter(
        react_state,
        skills_dir,
        business_spec_only=spec_mode,
        allow_unavailable_references=True,
    )
    tool_pack = ToolPack(
        [
            renderer,
            make_report_evidence_manifest(react_state),
            make_read_file(react_state),
            make_request_report_calculation(react_state),
            Terminate(),
        ]
        + ([make_append_report_sections(react_state, renderer)] if spec_mode else [])
    )

    if model_name:
        llm_config = LLMConfig(
            llm_client=llm_client,
            llm_strategy=LLMStrategyType.Priority,
            strategy_context=json.dumps([model_name]),
        )
    else:
        llm_config = LLMConfig(llm_client=llm_client)

    context = AgentContext(
        conv_id=sub_conv_id,
        gpts_app_code="react_agent_report",
        gpts_app_name="ReAct-Report",
        language=react_state.get("_report_language", "zh"),
        enable_context_management=True,
        enable_native_function_calling=True,
        temperature=0.1,
        max_new_tokens=8192,
    )

    agent = await (
        ToolCallingReActAgent(
            max_retry_count=REPORT_AGENT_MAX_RETRY, report_repair_state=react_state
        )
        .bind(context)
        .bind(sub_agent_memory)
        .bind(llm_config)
        .bind(tool_pack)
        .bind(
            PromptTemplate(
                template=report_agent_prompt(
                    template_path,
                    template_text,
                    injected_fields,
                    language=react_state.get("_report_language", "zh"),
                ),
                input_variables=[],
                template_format="jinja2",
            )
        )
        .build()
    )
    return agent


def _reply_text(reply: Any) -> str:
    if getattr(reply, "success", True) is False:
        context = getattr(reply, "context", None) or {}
        if isinstance(context, dict) and context.get("execution_error"):
            return str(context["execution_error"])
        if isinstance(getattr(reply, "content", None), str) and reply.content.strip():
            return reply.content
    report = getattr(reply, "action_report", None)
    content = getattr(report, "content", None)
    if isinstance(content, str) and content.strip():
        return content
    fallback = getattr(reply, "content", None)
    return fallback if isinstance(fallback, str) else ""


def _missing_calculation_response(state: Dict[str, Any]) -> str | None:
    request = state.get("_report_missing_calculation")
    if not request or request.get("result_artifact_id"):
        return None
    return json.dumps(
        {
            "status": "needs_analysis",
            "retryable": True,
            "artifact_ids": request["source_artifact_ids"],
            "missing_calculation": request,
            "instruction": (
                "Use code_interpreter once to compute only this missing "
                "calculation from REPORT_CALCULATION_INPUTS (JSON keyed by "
                "source artifact ID). Print a JSON object, then resume "
                "generate_report. Preserve the saved spec; do not rerun SQL, KB "
                "retrieval or completed "
                "analysis."
            ),
        },
        ensure_ascii=False,
    )


def _report_status_chunks(state: Dict[str, Any], text: str) -> list[dict]:
    chunks = [{"output_type": "text", "content": text}]
    draft = state.get("_report_draft")
    if draft and draft.get("content"):
        # Existing HTML preview supports this chunk. It is never assigned to
        # _report_presentation, so persistence cannot turn a draft into a report.
        chunks.append(
            {
                "output_type": "html",
                "content": draft["content"],
                "title": draft["title"],
                "draft": True,
            }
        )
    return chunks


def _report_agent_failure(state: Dict[str, Any], reason: str) -> str:
    """Keep child execution failures distinct from the last renderer diagnostic."""
    from ..tools.report_repair import save_execution_checkpoint

    text = "REPORT_AGENT_FAILED: " + reason
    state["_report_agent_failure"] = text
    save_execution_checkpoint(state, text)
    return json.dumps(
        {
            "status": "failed",
            "retryable": False,
            "execution_error": reason,
            "render_error": state.get("_report_html_error"),
            "artifact_ids": [],
            "chunks": _report_status_chunks(state, text),
            "instruction": (
                "The child execution failed; do not keep retrying it in this "
                "turn. Preserve the saved spec and artifacts and resume after "
                "the execution problem is "
                "resolved."
            ),
        },
        ensure_ascii=False,
    )


def _completed_report_response(state: Dict[str, Any]) -> str:
    presentation = state["_report_presentation"]
    return json.dumps(
        {
            "status": "completed",
            "retryable": False,
            "chunks": [
                {"output_type": "text", "content": "已复用现有分析生成报告。"},
                {
                    "output_type": "html",
                    "content": presentation["content"],
                    "title": presentation["title"],
                },
            ],
            "warnings": state.get("_report_warnings", []),
            "artifact_ids": list(
                dict.fromkeys(
                    artifact_id
                    for binding in state.get("_report_presentation_bindings", [])
                    for artifact_id in binding.get("artifact_ids", [])
                )
            ),
        },
        ensure_ascii=False,
    )


def make_generate_report_tool(
    *,
    react_state: Dict[str, Any],
    skills_dir: str,
    llm_client: Any,
    model_name: Optional[str] = None,
    timeout: int = REPORT_AGENT_TIMEOUT,
):
    """Expose the dedicated report agent as one tool for the lead agent."""

    @tool(
        description=(
            "把【生成/修复分析报告】交给专职报告子代理，独占模板与证据绑定流程，"
            "返回报告状态。分析完成后调用一次；报告渲染失败时也用本工具继续"
            "（在 instructions 里说明按最新错误清单修正 spec）。"
            "needs_analysis 需主代理仅补算缺失项。草稿 HTML 不表示完成，只有 "
            "status=completed "
            "表示正式报告完成。"
            '参数: {"instructions": "报告标题、必须包含的章节与建议条数"}'
        )
    )
    async def generate_report(
        instructions: str = "", intention: str = "", thought: str = ""
    ) -> str:
        from dbgpt.agent import AgentMessage

        from ..tools.report_charts import analysis_groups, selected_chart_gaps

        sink = react_state.get("_report_artifact_sink")
        artifacts = list(sink.snapshot()) if sink else []
        react_state["_report_generation_requested"] = True
        data_artifacts = [
            item
            for item in artifacts
            if item.status == "succeeded" and item.type in {"sql", "python"}
        ]
        if data_artifacts and not any(
            item.result is not None for item in data_artifacts
        ):
            react_state["_report_html_error"] = (
                "REPORT_RESULT_REQUIRED: analysis produced only printed text, "
                "without structured results for report bindings"
            )
            return json.dumps(
                {
                    "status": "needs_analysis",
                    "error": react_state["_report_html_error"],
                    "artifact_ids": [item.artifact_id for item in data_artifacts],
                    "instruction": (
                        "Capture the report's missing structured results with "
                        "code_interpreter: assign REPORT_RESULT to a JSON-compatible "
                        "dict/list of computed metrics and tables. Printed text alone "
                        "cannot be bound. Then call generate_report again. "
                        "Do not write report HTML yourself."
                    ),
                },
                ensure_ascii=False,
            )
        react_state["_report_analysis_groups"] = analysis_groups(artifacts)
        saved_spec = (
            (react_state.get("_report_saved_arguments") or {}).get("data") or {}
        ).get("REPORT_SPEC")
        presentation_html = (react_state.get("_report_presentation") or {}).get(
            "content", ""
        )
        if (
            isinstance(saved_spec, dict)
            and presentation_html
            and selected_chart_gaps(saved_spec, artifacts, presentation_html)
        ):
            react_state["_report_html_error"] = (
                "REPORT_REQUIREMENT_MISSING: selected result charts must be prepared"
            )
            react_state.pop("_report_success_response", None)

        knowledge_error = _knowledge_binding_error(react_state)
        if knowledge_error and not react_state.get("_report_agent_failure"):
            # Existing reports without links also need the author to select the
            # supporting slice; never guess by keywords or attach all results.
            react_state["_report_require_knowledge_bindings"] = True
            react_state["_report_html_error"] = knowledge_error
            react_state.pop("_report_success_response", None)
        else:
            if await render_saved_report(react_state, skills_dir):
                return _completed_report_response(react_state)
            if await render_saved_report(
                react_state, skills_dir, allow_unavailable_references=True
            ):
                return _completed_report_response(react_state)

        if react_state.get("_report_agent_failure"):
            if await render_saved_report(
                react_state, skills_dir, allow_unavailable_references=True
            ):
                return _completed_report_response(react_state)
            return json.dumps(
                {
                    "status": "failed",
                    "retryable": False,
                    "chunks": _report_status_chunks(
                        react_state, react_state["_report_agent_failure"]
                    ),
                },
                ensure_ascii=False,
            )

        if react_state.get("_report_calculation_exhausted"):
            return json.dumps(
                {
                    "status": "failed",
                    "retryable": False,
                    "chunks": _report_status_chunks(
                        react_state,
                        react_state.get("_report_html_error")
                        or "REPORT_CALCULATION_LIMIT_REACHED",
                    ),
                },
                ensure_ascii=False,
            )

        message = (
            instructions.strip()
            if isinstance(instructions, str) and instructions.strip()
            else "请生成可追溯的分析报告。"
        )
        missing = react_state.get("_report_missing_calculation")
        handoff = _missing_calculation_response(react_state)
        if handoff:
            return handoff
        if missing:
            message += "\n已补算缺失结果，读取并绑定此真实产物：" + str(
                missing["result_artifact_id"]
            )
        saved = react_state.get("_report_saved_arguments")
        if (
            isinstance(saved, dict)
            and saved.get("template_path")
            and isinstance(saved.get("data"), dict)
            and saved["data"].get("REPORT_SPEC")
            and (react_state.get("_report_template_contract") or {}).get("mode", "spec")
            == "spec"
        ):
            # Revalidate in code before constructing the recovery prompt. Asking
            # the model to submit the same empty update can exhaust the repeated
            # candidate guard without adding any of the missing content.
            if await render_saved_report(
                react_state, skills_dir, allow_unavailable_references=True
            ):
                return _completed_report_response(react_state)
            message += (
                "\n这是已保存 spec 的恢复，引擎已重新校验原始完整 spec。"
                "直接按最新错误追加缺失内容，不要用空 REPORT_SPEC 再次提交相同候选。"
                "保留已有章节、建议、样式和绑定，不能重写为部分章节。"
                "先前 REPORT_REPAIR_STOPPED "
                "属于已结束的旧轮预算；本轮以工具返回 retryable "
                "为准。"
            )
            sections = saved["data"]["REPORT_SPEC"].get("sections", [])
            message += (
                "\n已保存章节摘要（完整内容仍保存在引擎内，不必读取 checkpoint）："
                + json.dumps(
                    [
                        {
                            "heading": section.get("heading"),
                            "recommendations": len(
                                section.get("recommendations") or []
                            ),
                        }
                        for section in sections
                    ],
                    ensure_ascii=False,
                )
                + "。校验后仅追加缺失章节。不要读取完整 checkpoint 或重发已有章节；"
                "建议依据可用 report_evidence_manifest 定向读取少量真实 SQL 结果。"
            )
        requirement = react_state.get("_report_required_recommendation_count")
        if requirement:
            message += f"\n用户要求至少 {requirement} 条具体建议，必须渲染到建议章节。"
        if react_state["_report_analysis_groups"]:
            message += (
                "\n必须在正文覆盖的已完成分析任务（选择各任务相关结果，不要重跑）："
                + json.dumps(react_state["_report_analysis_groups"], ensure_ascii=False)
            )
        latest_error = react_state.get("_report_html_error") or react_state.get(
            "_report_last_render_error"
        )
        if latest_error:
            message += (
                "\n最新引擎错误（优先修复，复用已完成产物）：\n"
                + str(latest_error)[:REPORT_AGENT_RESULT_MAX_CHARS]
            )
        if react_state.get("_report_language") == "en":
            message += (
                "\nThe user's report language is English. Write the entire report "
                "in English, including headings, KPI labels, captions, "
                "and recommendations."
            )
        try:
            agent = await build_report_agent(
                react_state=react_state,
                llm_client=llm_client,
                skills_dir=skills_dir,
                model_name=model_name,
            )
            reply = await asyncio.wait_for(
                agent.generate_reply(
                    received_message=AgentMessage(content=message), sender=agent
                ),
                timeout=timeout,
            )
        except Exception as error:  # one failed report must not break the turn
            logger.warning("report agent failed: %s", error, exc_info=True)
            if await render_saved_report(
                react_state, skills_dir, allow_unavailable_references=True
            ):
                return _completed_report_response(react_state)
            return _report_agent_failure(react_state, str(error))
        if react_state.get("_report_html_error") and await render_saved_report(
            react_state,
            skills_dir,
            allow_unavailable_references=True,
        ):
            return _completed_report_response(react_state)
        error = react_state.get("_report_html_error")
        context = getattr(reply, "context", None) or {}
        if (
            not (react_state.get("_report_presentation") or {}).get("content")
            and getattr(reply, "success", True) is False
            and isinstance(context, dict)
            and context.get("execution_error")
        ):
            return _report_agent_failure(react_state, _reply_text(reply))
        handoff = _missing_calculation_response(react_state)
        if handoff:
            return handoff
        presentation = react_state.get("_report_presentation") or {}
        completed = bool(presentation.get("content")) and not error
        if completed:
            return _completed_report_response(react_state)
        text = (str(error) if error else _reply_text(reply))[
            :REPORT_AGENT_RESULT_MAX_CHARS
        ]
        if not completed and not error:
            text = "REPORT_AGENT_INCOMPLETE: 引擎未产生报告 HTML；" + text
        if not text:
            text = "报告子代理未返回状态；请检查渲染错误后重试。"
        bound_ids = (
            list(
                dict.fromkeys(
                    artifact_id
                    for binding in react_state.get("_report_presentation_bindings", [])
                    for artifact_id in binding.get("artifact_ids", [])
                )
            )
            if completed
            else []
        )
        return json.dumps(
            {
                "chunks": _report_status_chunks(react_state, text),
                "status": "completed"
                if completed
                else "failed"
                if react_state.get("_report_retry_exhausted")
                else "partial",
                "retryable": not completed
                and not bool(react_state.get("_report_retry_exhausted")),
                "artifact_ids": bound_ids,
                "draft_path": react_state.get("_report_draft_path")
                if not completed
                else None,
            },
            ensure_ascii=False,
        )

    return generate_report


__all__ = [
    "REPORT_AGENT_PROMPT",
    "REPORT_TEMPLATE_PATH",
    "build_report_agent",
    "make_generate_report_tool",
]
