# Agent 节点

`agent` 节点在工作流内运行一个聚焦的 ReAct Agent。隔离是设计使然：独立记忆、独立会话 id、
看不到主对话也看不到其他节点的工具轨迹——只有你给的目标、用户原问与上游产出。

## 配置参考

| 字段 | 类型 | 作用 |
|---|---|---|
| `agent_profile` | `react_data` / `react_knowledge` / `react_general` | 人设骨架 + 默认工具亲和（分析师 / 知识专家 / 谨慎执行者） |
| `goal` | 文本 | 节点目标。**以 `输出:` 契约行收尾** |
| `tools` | 列表 | 能力边界。未勾选的工具对该节点不存在 |
| `skills` | 列表 | 技能包；挂载 `load_skill` / `execute_skill_script_file` 并在 prompt 列技能清单 |
| `datasources` | 列表 | `sql_query` 可碰的 connector。单库直绑；多库切显式 `db_name` 模式；空 = 无 SQL 工具 |
| `knowledge` | 列表 | `knowledge_retrieve` 与 `kb_ls/kb_glob/kb_grep/kb_cat/semantic_search` 族的知识空间 |
| `mcp` | 列表 | 行内 MCP（`sse:<url>` / `http:<url>`）；连不上的服务跳过不致命 |
| `max_turns` | 1–30 | 本节点 ReAct 循环上限 |
| `model` | 文本 | 覆盖本节点模型（默认会话模型） |

可用工具 id：`sql_query`、`code`、`knowledge_retrieve`、`html_interpreter`、
`bash`、`web_search`、`web_fetch`。

## 写利于组合的 goal

好 goal 三段式：**角色立场** + **行为约束** + **输出契约**。

```text
把用户问题中的业务名词映射到表/字段/口径:用 sql_query 查元数据与有界样例(表结构、
distinct/limit 采样,禁止全表扫描);多口径时列候选并说明默认采纳与理由。
输出查询计划:每步 SQL 草案+预期字段与行数上限。
        └──────────────────────┬──────────────────────┘
                            输出契约
```

内置模板里验证过的模式：

- **先接地后回答**。接地节点以"不要回答用户问题本身"收尾，避免探索过程污染答案节点上下文；
- **禁止粘工具返回值**。报告 goal 以"禁止把工具返回值或 JSON 原样粘贴为答案"收尾——否则模型
  会把最后一次 observation 当 terminate 结果；
- **独立复核**。复核节点写"从口径独立重写重算，不得复用上游 SQL"——否则复核退化为重跑同一条
  查询；
- **约束探查**。"只查元数据与有界聚合，禁止全表扫描"让接地节点在业务库上既便宜又安全。

## 值得知道的运行时行为

- **并行工具调用**（native tool_calls 或文本并联动作）按批执行；轨迹行显示并联工具名与逐调用
  observation；
- **空参守卫**：被截断的回合空参调用工具时快速失败并回可行动 observation（"was called with no
  arguments… retry"），Agent 通常下一回合自愈；卡片打 *缺参数 · 输出被截断* 徽章与重试次数；
- **供应商级错误**（402/401/403、Insufficient Balance）让节点响亮失败，而不是当作"答案"返回；
- **HTML 渲染**：只有 `html_interpreter` 产报告产物；一份报告一次调用，随后用短句总结 terminate。
  渲染的 HTML 写入会话产物目录，以 chip 形式挂在节点卡上；
- **输出上限**：节点模型调用带 16k token 输出预算——足够整份 HTML 报告；老的 4k 上限会把工具
  参数拦腰截断。

## 回合预算

按节点复杂度分配，全链 ≤ 约 40 回合：接地 4–6、计划 4、分析 8–10、复核 6–8、报告 6。经常顶到
上限的节点需要更紧的 goal 或更小的scope，而不是更大的上限。

下一步：[数据入口](./data-entry.md) · [确认门](./human-confirm.md) · [自定义算子](../custom-operator.md)
