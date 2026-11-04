"""TaskFlow node kind registry and manifest.

Each node kind is a *product* capability (e.g. "数据库查询"), not an AWEL
operator. The manifest exposed by ``GET /taskflow/node-kinds`` drives the
editor's node palette and property panel; the compiler
(:mod:`.compiler`) expands every kind into a subgraph of AWEL operators.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# Node groups (palette sections)
GROUP_BOUNDARY = "boundary"
GROUP_SOURCE = "source"
GROUP_ANALYSIS = "analysis"
GROUP_CONTROL = "control"
GROUP_OUTPUT = "output"

_GROUP_LABELS = {
    GROUP_BOUNDARY: {"zh": "边界", "en": "Boundary"},
    GROUP_SOURCE: {"zh": "数据来源", "en": "Data Source"},
    GROUP_ANALYSIS: {"zh": "分析计算", "en": "Analysis"},
    GROUP_CONTROL: {"zh": "流程控制", "en": "Control"},
    GROUP_OUTPUT: {"zh": "结果输出", "en": "Output"},
}


@dataclass
class ConfigField:
    """One business-level config field of a node kind."""

    name: str
    type: str  # text|textarea|number|switch|select|datasource|model
    label: str
    label_en: str
    required: bool = False
    default: Any = None
    options: Optional[List[Dict[str, str]]] = None
    placeholder: Optional[str] = None
    desc: Optional[str] = None
    desc_en: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "type": self.type,
            "label": self.label,
            "label_en": self.label_en,
            "required": self.required,
            "default": self.default,
            "options": self.options,
            "placeholder": self.placeholder,
            "desc": self.desc,
            "desc_en": self.desc_en,
        }


@dataclass
class NodeKindSpec:
    """The product-level specification of a node kind."""

    kind: str
    label: str
    label_en: str
    desc: str
    desc_en: str
    group: str
    icon: str
    config_fields: List[ConfigField] = field(default_factory=list)
    inputs_desc: str = ""
    inputs_desc_en: str = ""
    outputs_desc: str = ""
    outputs_desc_en: str = ""
    unique_in_flow: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "kind": self.kind,
            "label": self.label,
            "label_en": self.label_en,
            "desc": self.desc,
            "desc_en": self.desc_en,
            "group": self.group,
            "group_label": _GROUP_LABELS[self.group]["zh"],
            "group_label_en": _GROUP_LABELS[self.group]["en"],
            "icon": self.icon,
            "config_fields": [f.to_dict() for f in self.config_fields],
            "inputs_desc": self.inputs_desc,
            "inputs_desc_en": self.inputs_desc_en,
            "outputs_desc": self.outputs_desc,
            "outputs_desc_en": self.outputs_desc_en,
            "unique_in_flow": self.unique_in_flow,
        }


NODE_KINDS: Dict[str, NodeKindSpec] = {}


def _register(spec: NodeKindSpec) -> None:
    NODE_KINDS[spec.kind] = spec


_register(
    NodeKindSpec(
        kind="start",
        label="开始",
        label_en="Start",
        desc="读取分析目标与对话上下文（数据库 / 文件）",
        desc_en="Read the analysis objective and chat context (datasource/files)",
        group=GROUP_BOUNDARY,
        icon="▶",
        unique_in_flow=True,
        outputs_desc="分析目标、对话上下文",
        outputs_desc_en="Analysis objective, chat context",
    )
)

_register(
    NodeKindSpec(
        kind="db_query",
        label="数据库查询",
        label_en="Database Query",
        desc="自然语言或 SQL 查询数据源，有界只读",
        desc_en="Query a datasource with natural language, bounded read-only",
        group=GROUP_SOURCE,
        icon="🗄",
        config_fields=[
            ConfigField(
                name="datasource",
                type="datasource",
                label="数据源",
                label_en="Datasource",
                required=True,
                desc="选择要查询的数据库连接",
                desc_en="The database connection to query",
            ),
            ConfigField(
                name="max_rows",
                type="number",
                label="返回行数上限",
                label_en="Max Rows",
                default=1000,
                desc="限制单次查询返回的最大行数",
                desc_en="Limit the max rows returned by one query",
            ),
        ],
        inputs_desc="分析目标",
        inputs_desc_en="Analysis objective",
        outputs_desc="查询结果表（含快捷图表）",
        outputs_desc_en="Query result table (with quick chart)",
    )
)

_register(
    NodeKindSpec(
        kind="file_data",
        label="文件数据",
        label_en="File Data",
        desc="上传 CSV / Excel 作为分析数据集",
        desc_en="Upload a CSV/Excel file as the analysis dataset",
        group=GROUP_SOURCE,
        icon="📄",
        config_fields=[
            ConfigField(
                name="file_name",
                type="file",
                label="数据文件",
                label_en="Data File",
                required=True,
                placeholder="sales_q3.xlsx",
                desc="上传 CSV / Excel 文件，或填写已在服务端的文件名/路径",
                desc_en="Upload a CSV/Excel file, or enter a file name/path "
                "already on the server",
            ),
            ConfigField(
                name="max_rows",
                type="number",
                label="加载行数上限",
                label_en="Max Rows",
                default=1000,
            ),
        ],
        inputs_desc="分析目标",
        inputs_desc_en="Analysis objective",
        outputs_desc="数据集（markdown 表 + 可计算 DataFrame）",
        outputs_desc_en="Dataset (markdown table + computable DataFrame)",
    )
)

_register(
    NodeKindSpec(
        kind="agent",
        label="Agent",
        label_en="Agent",
        desc="指派一个 Agent 自主规划并调用工具完成本步目标",
        desc_en="Assign an agent to plan and call tools for this step's goal",
        group=GROUP_ANALYSIS,
        icon="🤖",
        config_fields=[
            ConfigField(
                name="agent_profile",
                type="agent_profile",
                label="指派 Agent",
                label_en="Agent Profile",
                desc="内置画像,决定系统 Prompt 骨架与默认工具",
                desc_en="Builtin persona: prompt skeleton + default tools",
            ),
            ConfigField(
                name="goal",
                type="textarea",
                label="目标 Prompt",
                label_en="Goal Prompt",
                required=True,
                placeholder="明确本节点要完成什么、输出什么",
                desc="用户问题与全部上游产出会自动作为上下文注入",
                desc_en="User question and all upstream outputs are auto-injected",
            ),
            ConfigField(
                name="model",
                type="model",
                label="模型",
                label_en="Model",
                desc="留空则使用默认模型",
                desc_en="Use the default model if empty",
            ),
            ConfigField(
                name="tools",
                type="checkbox_group",
                label="内置工具",
                label_en="Builtin Tools",
                desc="勾选即能力边界,未选不出现在行动空间",
                desc_en="Selected tools define the action space",
            ),
            ConfigField(
                name="skills",
                type="multiselect",
                label="技能 Skill",
                label_en="Skills",
                desc="选中技能的 SKILL.md 与脚本对本节点可用",
                desc_en="Selected skills' docs and scripts are available",
            ),
            ConfigField(
                name="datasources",
                type="multiselect",
                label="数据源",
                label_en="Datasources",
                desc="SQL 查询工具的可用范围(只读)",
                desc_en="Scope of the sql_query tool (read-only)",
            ),
            ConfigField(
                name="knowledge",
                type="multiselect",
                label="知识库",
                label_en="Knowledge Bases",
                desc="知识库检索工具的可用范围",
                desc_en="Scope of the knowledge_retrieve tool",
            ),
            ConfigField(
                name="mcp",
                type="textarea",
                label="MCP 连接器",
                label_en="MCP Connectors",
                placeholder="sse:https://mcp.example.com/sse(每行一个)",
                desc="每行一个 sse:/http: 开头的 MCP server 地址",
                desc_en="One MCP server URL per line, prefixed sse:/http:",
            ),
            ConfigField(
                name="max_turns",
                type="number",
                label="最大回合数",
                label_en="Max Turns",
                default=10,
                desc="限制「思考 → 工具」循环上限,控制时延与成本",
                desc_en="Cap the think-act loop to bound latency and cost",
            ),
        ],
        inputs_desc="用户目标 + 全部上游产出",
        inputs_desc_en="User goal + all upstream outputs",
        outputs_desc="Agent 最终回答",
        outputs_desc_en="Agent's final answer",
    )
)

_register(
    NodeKindSpec(
        kind="ai_analysis",
        label="智能分析",
        label_en="AI Analysis",
        desc="围绕分析目标对上游数据执行计算与洞察",
        desc_en="Analyze upstream data around the objective",
        group=GROUP_ANALYSIS,
        icon="🧮",
        config_fields=[
            ConfigField(
                name="model",
                type="model",
                label="分析模型",
                label_en="Model",
                desc="留空则使用默认模型",
                desc_en="Use the default model if empty",
            ),
            ConfigField(
                name="analysis_prompt",
                type="textarea",
                label="分析要求",
                label_en="Analysis Requirement",
                placeholder="关注趋势变化与同比 / 环比，识别异常波动并给出可能原因。",
                desc="留空则由模型根据「开始」节点的分析目标自行决定",
                desc_en="Leave empty to let the model decide from the objective",
            ),
        ],
        inputs_desc="上游数据表 · 分析目标",
        inputs_desc_en="Upstream dataset, objective",
        outputs_desc="分析结论",
        outputs_desc_en="Analysis conclusion",
    )
)

_register(
    NodeKindSpec(
        kind="visualize",
        label="可视化生成",
        label_en="Visualization",
        desc="自动选择图表类型，将结果生成图表与仪表盘",
        desc_en="Pick chart types automatically and render a dashboard",
        group=GROUP_ANALYSIS,
        icon="📊",
        config_fields=[
            ConfigField(
                name="datasource",
                type="datasource",
                label="数据源",
                label_en="Datasource",
                desc="选择后图表可重新取数；留空则基于上游数据集绘制",
                desc_en="If set, charts may re-query data; otherwise charts are "
                "built from the upstream dataset",
            ),
            ConfigField(
                name="max_charts",
                type="number",
                label="最多图表数",
                label_en="Max Charts",
                default=4,
            ),
            ConfigField(
                name="model",
                type="model",
                label="可视化模型",
                label_en="Model",
            ),
        ],
        inputs_desc="分析结论 · 上游数据",
        inputs_desc_en="Analysis conclusion, upstream data",
        outputs_desc="图表 / 仪表盘",
        outputs_desc_en="Charts / dashboard",
    )
)

_register(
    NodeKindSpec(
        kind="human_confirm",
        label="人工确认",
        label_en="Human Review",
        desc="暂停等待人工检查后继续（P0 为提示性确认点）",
        desc_en="Pause for human review before continuing (P0: informational)",
        group=GROUP_CONTROL,
        icon="✋",
        config_fields=[
            ConfigField(
                name="message",
                type="text",
                label="确认提示",
                label_en="Confirm Message",
                placeholder="请确认分析结论口径，确认后生成报告",
            ),
        ],
        inputs_desc="上一步结果",
        inputs_desc_en="Previous result",
        outputs_desc="确认后继续",
        outputs_desc_en="Continue after confirmation",
    )
)

_register(
    NodeKindSpec(
        kind="report",
        label="分析报告",
        label_en="Report",
        desc="汇总结论与图表，生成结构化分析报告",
        desc_en="Summarize conclusions into a structured analysis report",
        group=GROUP_OUTPUT,
        icon="📝",
        config_fields=[
            ConfigField(
                name="model",
                type="model",
                label="报告模型",
                label_en="Model",
            ),
        ],
        inputs_desc="分析结论 · 数据表 · 分析目标",
        inputs_desc_en="Conclusions, dataset, objective",
        outputs_desc="markdown 分析报告",
        outputs_desc_en="Markdown analysis report",
    )
)

_register(
    NodeKindSpec(
        kind="output",
        label="输出",
        label_en="Output",
        desc="整理最终结果返回对话",
        desc_en="Assemble the final result and return to the chat",
        group=GROUP_BOUNDARY,
        icon="✓",
        unique_in_flow=True,
        inputs_desc="各节点产出",
        inputs_desc_en="Outputs of upstream nodes",
    )
)


def get_node_kind_manifest() -> List[Dict[str, Any]]:
    """Return the manifest of all registered node kinds (for the editor)."""
    return [spec.to_dict() for spec in NODE_KINDS.values()]
