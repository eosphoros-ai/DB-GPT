# 自定义算子

自定义分三级。从能表达需求的最低级开始——大多数"新算子"需求其实是配置。

## Level 0——组合 agent 节点（零代码）

新的分析能力通常就是 goal + 工具边界：

```json
{
  "id": "n4",
  "kind": "agent",
  "label": "队列留存",
  "config": {
    "agent_profile": "react_data",
    "goal": "基于上游语义卡计算周队列留存;用独立 SQL 路径复核分母。输出:留存表+三条发现。",
    "tools": ["sql_query", "code"],
    "datasources": ["Walmart_Sales"],
    "max_turns": 8
  }
}
```

在编辑器里加节点、连线、部署。完成——没有 Python、不用重启。

## Level 1——挂技能 / 工具 / MCP

- **技能**：技能包放入技能目录即出现在节点属性面板；勾选后挂载 `load_skill` /
  `execute_skill_script_file` 并在节点 prompt 列清单。技能可带模板（如 HTML 报告骨架），
  `html_interpreter` 可用 `template_path` + `data` 填充；
- **MCP**：在节点 MCP 列表加 `sse:<url>` / `http:<url>`，把外部工具服务仅暴露给该节点；
- **数据源 / 知识库**：绑定 connector 或知识空间，才让 `sql_query` 或 `kb_*` 族在节点内存在。

## Level 2——写 Python 算子

行为必须确定（文件加载、图表渲染、门控）或要直连基础设施时，写算子。内置产品节点的同款模式：

```python
from dbgpt.core.awel import MapOperator
from dbgpt.core.awel.flow import IOField, OperatorCategory, Parameter, ViewMetadata
from dbgpt.util.i18n_utils import _


class HOMyOperator(MapOperator[str, str]):
    """编辑器面板里显示的一句话描述。"""

    metadata = ViewMetadata(
        label=_("我的算子"),
        name="taskflow_my_operator",
        description=_("对上游文本做确定性变换。"),
        category=OperatorCategory.COMMON,
        parameters=[
            Parameter.build_from(_("上限"), "limit", int, optional=True,
                                 default=100, description=_("行数上限。")),
        ],
        inputs=[IOField.build_from(_("上游"), "content", str,
                                   description=_("上游节点产出。"))],
        outputs=[IOField.build_from(_("结果"), "result", str,
                                    description=_("变换后产出。"))],
    )

    def __init__(self, limit: int = 100, **kwargs):
        super().__init__(**kwargs)
        self._limit = limit

    async def map(self, content: str) -> str:
        return content[: self._limit]
```

一个合格产品算子的清单：

1. **`ViewMetadata` 就是 UI**：label/description/parameters 渲染进编辑器面板与属性面板，
   记得用 `_()` 包 i18n；
2. **发步骤 marker**：用 `build_step_marker(...)`（见 `dbgpt_app/operators/taskflow.py`）包裹
   产出，运行卡才会像其他节点一样展示你的节点（含时长与状态）；
3. **strip 协议再传递**：上游文本喂 LLM 或返回前，先 `strip_step_markers` /
   `strip_artifact_fences`；
4. **产物登记而非内联**：大 payload（HTML、表格）落盘到 pilot 产物根目录，以
   `vis-flow-artifact` 元数据 fence 传递；聊天 UI 渲染 chips 并经受限产物端点服务文件；
5. **响亮失败**：基础设施错误 raise；只有**内容级**结果才返回文本。"成功"返回错误串的节点会
   毒化下游所有契约。

算子通过包元数据扫描被 flow 运行时发现——模块放进已加载的 `dbgpt` 包（如
`dbgpt_app/operators/`）并重启服务；kind 随即出现在编辑器面板，也可被 TaskFlow DSL 编译器引用。

## 扩展 TaskFlow DSL 本身

新增一个全新 `kind`（面板入口 + 编译规则 + 配置校验）需要扩展编译器 `NODE_KINDS` 清单与
`dbgpt_serve/flow/taskflow/compiler.py` 的 builder，以及 web 的 kind manifest 与 i18n 标签。
这是产品变更而非用户扩展——按惯例先出 mockup 再动代码。

下一步：[运行与产物](./runs-and-artifacts.md) · [编辑器](./editor.md)
