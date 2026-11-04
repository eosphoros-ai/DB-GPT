# TaskFlow Agent 节点改造方案(主子 Agent 工作流)

> 状态:P0 已落地(2026-10-09):agent_runner + TFAgentOperator + DSL/编译器 +
> agent-options 端点 + 中英模板 + 前端编辑/运行态;72 测试绿
> 待验证:真实 LLM 端到端冒烟(需重启服务)
> 前置:TaskFlow P0 已落地(见 taskflow-redesign-plan.md),步骤流式增量已完成
> 对标形态:每个工作流节点可指派一个 Agent(头像 + 模型 + 连接器/MCP + Prompt),
> 节点即子 Agent,连线即主子编排;另有内嵌脚本类确定性节点。

## 1. 目标与产品形态

在 TaskFlow 现有 8 种节点(start / db_query / file_data / ai_analysis / visualize /
human_confirm / report / output)之上,新增 **Agent 节点**:

- 节点可「指派 Agent」:内置 Agent 画像(react 数据分析、research、代码专家…)
  或引用用户已有 Agent 应用(GptsApp);
- 节点可配:目标 Prompt(goal)、模型(默认跟随对话模型)、工具集(内置工具 +
  MCP 连接器,勾选制)、最大回合数;
- Agent 节点内部是一个 ReAct 循环(思考 → 工具调用 → 观察 → …),其**中间过程
  实时流入该节点的步骤卡**(主子可视),最终结论进入数据通道传给下游;
- 连线语义不变:上游节点的 clean data(markdown 表 / 结论)作为 Agent 的上下文,
  用户问题作为目标;Agent 节点的最终回答是新的 clean data。

非目标(P0 不做):节点级并行 fan-out 编排、脚本节点、节点内 HITL 暂停。

### 1.1 多 Agent 串联(核心诉求,P0 即支持)

Agent 节点可以像普通节点一样**连续串联 2 个、3 个或更多**,DSL 层无需任何
特殊语法(`agent → agent → … → output` 就是普通链):

```json
"nodes": [
  {"id": "n1", "kind": "start", "config": {}},
  {"id": "n2", "kind": "agent", "label": "思考并回复",
   "config": {"agent_profile": "react_knowledge", "goal": "…", "tools": ["knowledge_retrieve"]}},
  {"id": "n3", "kind": "agent", "label": "专家审核",
   "config": {"agent_profile": "react_data", "goal": "…", "tools": ["sql_query", "code_interpreter"]}},
  {"id": "n4", "kind": "agent", "label": "发送最终消息",
   "config": {"agent_profile": "react_general", "goal": "…", "tools": []}},
  {"id": "n5", "kind": "output", "config": {}}
],
"edges": [["n1","n2"],["n2","n3"],["n3","n4"],["n4","n5"]]
```

语义(与现有编译器连线规则自然契合,零特殊处理):

- **上下文累积**:编译器已把*所有*前序节点的 clean data 出口接入每个下游
  节点(§compiler `entry_data` 扇出),所以第 3 个 Agent 同时看到原始数据、
  第 1 个 Agent 的结论、第 2 个 Agent 的审核意见;
- **严格串行**:第 i+1 个 Agent 的数据输入依赖第 i 个的输出,AWEL runner
  顺序执行天然保证依次运行,步骤卡逐个渲染(沿用旁路事件队列);
- **步骤卡**:每个 Agent 一个步骤卡,卡内是该 Agent 自己的 ReAct 小步骤
  轨迹(思考/工具/观察),互不干扰(按 step_id 隔离);
- **fan-out(一个上游接 2-3 个并行 Agent)**:拓扑上合法(同上游多下游),
  runner 仍按序执行,P0 可用但非真并行;真并行 + join 汇总 = P1 的
  `lead_agent` 节点(内嵌 dispatch_parallel_tasks,子 Agent 并行,复用
  subagent dispatcher + SubAgentSection 渲染)。

### 1.2 Agent 之间的衔接上下文(交接协议)

每个 Agent 节点(与 ai_analysis 同构,JoinOperator:`(question, *args)`)
收到的是**三路信息**,而不是上一个 Agent 的全部内部状态:

| 通道 | 内容 | 来源 |
|---|---|---|
| 节点指令 | `goal` 配置(本节点的角色与任务要求) | 节点 config |
| 用户目标 | 终端用户的原始问题(每个节点看到的完全相同) | trigger → entry_question |
| 上游材料 | **所有**前序节点 clean data 出口,按链序 `\n\n` 拼接(step marker 已剥离) | entry_data 扇出 |

各节点类型的 clean data 出口(即下游可见的"材料"):

| 节点 | 出口内容 |
|---|---|
| db_query | 查询结果 markdown 表 |
| file_data | 文件 markdown 表 + 行/列摘要 |
| ai_analysis | 分析结论文本 |
| **agent** | **该 Agent 的最终回答** |
| visualize | 无(图表只进步骤卡,不进数据通道) |

两条核心设计决策:

1. **传递的是"最终回答",不是 ReAct 轨迹**。上一个 Agent 的思考、工具
   调用、观察全部留在它自己的步骤卡里(可视),不进入下游上下文——中间
   过程是 token 噪声,且会让下游 Agent 被上游的推理路径带偏。
2. **原始数据随链传递,不只传摘要**。数据节点的 markdown 表始终在每个下游
   Agent 的材料里,所以「专家审核」可以基于**原始数据**复核「思考并回复」
   的结论,而不是信任链式摘要(避免"传话游戏"式失真)。这也回答了为什么
   串联语义直接用现有 `entry_data` 扇出而无需新协议。

材料总量控制:拼接后整体截断(P0 上限 20k 字符,超出保留头部 + 尾部摘要),
超限与空材料都在 user message 中显式说明。

## 2. 现状基建盘点(调研结论)

### 可直接复用

| 能力 | 位置 |
|---|---|
| 轻量 Agent 执行模板(独立 conv_id + 独立 memory,单轮 generate_reply) | `dbgpt_app/openapi/api_v1/subagent/dispatcher.py::build_sub_react_agent` (L298-399) + `run_one` (L607-676) |
| ToolCallingReActAgent(原生 tool_calls / 文本 ReAct 双模) | `dbgpt/agent/expand/tool_calling_agent.py` |
| Agent 四要素模型(profile/llm/prompt/resources) | `agent/core/plan/awel/agent_operator_resource.py::AWELAgent` |
| AWEL 形式 Agent 算子(可参考) | `agent/core/plan/awel/agent_operator.py::AWELAgentOperator` |
| MCP 客户端(SSE + Streamable HTTP,多 server,header 鉴权) | `agent/util/mcp_utils.py` + `agent/resource/tool/pack.py::MCPToolPack` |
| MCP 资源别名(UI 可配 URL/token) | `dbgpt_serve/agent/resource/mcp.py::MCPSSEToolPack` |
| 内置工具 factory(知识检索/SQL/代码/Shell/HTML/load_skill 等 8 个) | `dbgpt_app/openapi/api_v1/subagent/react_tools.py::make_react_tools` |
| sub-agent 事件协议与前端渲染(agent.start/step/done、历史回放) | `subagent/dispatcher.py` + `web/hooks/use-subagent-stream.ts` + `SubAgentSection` |
| **步骤事件旁路队列(本次新建,直接复用!)** | `dbgpt_app/operators/taskflow.py::register_step_events` + `service.py::_merge_step_events` |
| Agent 模板市场 / 用户 Agent 存储 | `dbgpt_serve/agent/hub/` + `gpts_app/gpts_app_detail` 表 |

### 缺口

1. 无一行调用的 `run_agent(goal, context, tools) -> reply` 入口(dispatcher 的
   build_sub_react_agent 耦合了主 agent 上下文,需要抽取);
2. TaskFlow DSL 无 agent 节点 kind,编译器无展开规则;
3. Agent 的 ReAct 中间步骤没有桥到 TaskFlow 步骤事件通道;
4. 无"可用 Agent 画像 / 工具 / MCP 连接器"的清单端点供前端下拉;
5. 前端 syncSteps 不支持 marker 的 running 状态(目前只有 done/failed)。

## 3. DSL 设计(taskflow/1 兼容扩展)

新增 kind `agent`,**连线/拓扑规则与现有内容节点完全一致**(单进单出即可,
P0 不引入分支):

```json
{
  "id": "n3",
  "kind": "agent",
  "label": "专家审核",
  "config": {
    "agent_profile": "react_data",        // 内置画像 id;或 "gpts:<app_code>" 引用应用(P1)
    "goal": "复核结论中的关键数字,口径不一致处给出修正",
    "model": "deepseek-v4-pro",            // 可选,缺省跟随请求模型
    "tools": ["sql_query", "code_interpreter"],   // 内置工具 id(多选)
    "skills": ["excel-analyzer", "mysql-dba"],    // 技能包名(多选)
    "datasources": ["sqlite_dbgpt"],              // 数据源 db_name(多选)
    "knowledge": ["space_after_sales"],           // 知识库 space id(多选)
    "mcp": ["sse:https://mcp.example.com/sse"],   // MCP 连接器(URL 内联,P0)
    "max_turns": 10
  }
}
```

- `agent_profile`:内置画像(见 §5.3),决定系统 Prompt 骨架与默认工具;
- `goal`:节点目标,与上游数据一起渲染进 user message;为空时用节点 label;
- `tools`:内置工具 id 白名单(`sql_query` / `code_interpreter` /
  `knowledge_retrieve` / `html_interpreter` / `shell_interpreter`);
- `skills` / `datasources` / `knowledge`:**资源范围**(多选),见 §4.1 的运行时
  语义;资源未选 = 对应工具不出现在 Agent 行动空间;
- `mcp`:`sse:<url>` / `http:<url>` 内联 MCP server(P0,**默认空,无内置
  连接器**,用户自行添加);P1 改为连接器注册表 id 引用;
- 校验:`goal` 必填;`max_turns` 1-30,默认 10。

## 4. 后端改造

### 4.1 抽取轻量 Agent 运行器(核心)

新增 `packages/dbgpt-app/src/dbgpt_app/operators/agent_runner.py`:

```python
async def run_react_agent(
    *, goal: str, context: str, model: str | None,
    profile: AgentProfile, tool_specs: list[str],
    max_turns: int, system_app,
    on_step: Callable[[AgentStepEvent], Awaitable[None]],   # ReAct 中间步骤回调
) -> str:
    """构建一次性 ToolCallingReActAgent 并执行单轮任务,返回最终回答。"""

@dataclass
class AgentStepEvent:
    kind: str        # thinking | action | observation
    title: str       # action 名或摘要
    detail: str      # 截断后的输入/输出
```

实现要点(照搬 `dispatcher.build_sub_react_agent` 的隔离模型,去掉其对主
agent 上下文的依赖):

- `AgentContext(conv_id=f"taskflow_agent_{dag_id}_{node_id}_{uuid4().hex[:8]}")`,
  独立 `GptsMemory`(内存 plans memory + DB message memory,与 dispatcher 一致);
- prompt:`PromptTemplate.from_template`(profile 骨架 + goal 段 +
  `{{action_space}}` 占位),不依赖 prompt 服务,缺省 fallback 同
  `dispatcher._build_sub_prompt`;
- 工具:按 `tool_specs` 从 `make_react_tools` 白名单子集装配(禁止
  `dispatch_parallel_tasks`/`todowrite`,P0 不允许节点内再 dispatch);
  `mcp:*` spec → `MCPToolPack`,沿用只读过滤
  (`_filter_readonly_connector_tools`);
- **资源范围装配(技能 / 数据源 / 知识库,多选)**:
  - `skills: [name…]` → 从 skill registry(`dbgpt.agent.claude_skill.
    get_registry().list_skills()`)取出选中技能,① 技能清单(名称 + 描述)
    渲染进 system prompt 的「可用技能」段;② 给 Agent 挂 `load_skill` +
    `execute_skill_script_file` 工具(参数说明里限定可选技能名);
  - `datasources: [db_name…]` → `sql_query` 工具的 db 白名单收敛到选中项
    (工具描述列出可选库;未选任何数据源且 tools 含 `sql_query` 时,回退
    对话当前库);只读约束不变;
  - `knowledge: [space_id…]` → `knowledge_retrieve` 的检索范围收敛到选中
    space(工具描述列出可选库名);
  - 任一类资源为空数组/未配置 → 对应能力不出现在行动空间(而非放开到
    全部),保证「连接器勾选 = 能力边界」的产品语义;
- `stream_callback` 适配:`base_agent.generate_reply` 已发
  `thinking_chunk/thinking/act` 三类事件,映射为 `AgentStepEvent` 回调;
- 结果:取最终 `AgentMessage.content`,复用
  `subagent/result.py::extract_subagent_result` 的清洗逻辑。

**上游产出的消费方式(messages 组装)**:上游最终回答**不做角色重放**
(不塞 assistant 轮次),而是作为带来源标签的引用材料嵌进**唯一一条
user message**;Agent 自己的 ReAct 轨迹从第二轮起才以 assistant/tool
轮次追加。结构:

```
[system]  {profile 骨架}
          - 角色定义(如:资深数据分析师,复核导向)
          - ReAct 协议说明 + {{action_space}} 工具清单
          - 「可用技能」段(选中 skills 的名称+描述,如有)
          - 资源边界(可查询库 / 可检索知识库名单,如有)

[user]    {goal}

          用户问题:
          {原始用户问题}

          上游节点产出(按链序):
          <source node="数据库查询" kind="db_query">
          {markdown 数据表}
          </source>
          <source node="思考并回复" kind="agent">
          {上一个 Agent 的最终回答}
          </source>

[assistant] Thought: ... / tool_calls ...   ← ReAct 第 1 回合
[tool]      {观察结果}
[assistant] ...                              ← 后续回合
```

理由:① 上游回答是"证据材料"不是"自己说过的话",放 assistant 轮会
让模型产生"我已回答过"的幻觉并破坏 ReAct 格式纪律;② `<source>` 标签
让模型区分「原始数据」与「某节点的结论」,为后续引用体系
(dbgpt-citation-references-design)留口;③ 单 user 消息首回合,兼容
native tool_calls 与文本 ReAct 双模。

### 4.2 新算子 `TFAgentOperator`

`packages/dbgpt-app/src/dbgpt_app/operators/taskflow_agent.py`:

- metadata:`taskflow_agent_operator`,inputs = [目标 question, 上游数据 data],
  outputs = [结论 str];parameters = agent_profile / goal / model / tools(str 数组)
  / max_turns;
- `map(question, data)`:
  1. 组装 goal = config.goal + "\n\n用户问题:\n" + question +
     "\n\n上游数据:\n" + data(截断上限,如 20k 字符);
  2. **渐进式步骤事件**:读取 share_data 的 conv_uid,取事件队列;
     每个 `AgentStepEvent` → 重新构造 `marker( status:"running",
     summary:当前动作 ) + 已累积的步骤日志(截断保留最近 N 条)` 推入队列;
     前端按 step_id 去重(keep-last)天然实现"同一节点卡片内容实时刷新";
  3. 结束:推 `status:"success"` + 最终回答;异常时推 `status:"failed"` +
     错误摘要,并向上抛出(DAG 失败语义不变);
- 资源缓存:同一 (profile, tools) 的 `ResourcePack` 进程内缓存(MCP
  `preload_resource` 非幂等,避免重复 list_tools)。

### 4.3 DSL/编译器

- `taskflow/nodes.py`:注册 `agent` kind,group=ANALYSIS(或新增 GROUP_AGENT),
  icon 🤖;config_fields:
  - `agent_profile`: type `select`(options 由 manifest 静态给出,P0 内置 3 个)
  - `goal`: type `textarea`, required
  - `model`: type `model`
  - `tools`: type `select`, **multi**(新增 multi 支持,见 §5.2),options 静态
    内置工具
  - `skills`: type `multiselect`,options 动态(skill registry)
  - `datasources`: type `multiselect`,options 动态(前端已有 getDbList)
  - `knowledge`: type `multiselect`,options 动态(rag spaces)
  - `mcp`: type `textarea`(P0:每行一个 `sse:/http:` URL;P1 改连接器引用)
  - `max_turns`: type `number`, default 10
- `taskflow/compiler.py::_build_agent`:
  - 展开为 `TFAgentOperator` + `TFStepMarkerOperator`(与 ai_analysis 同构);
  - `entry_question=[agent.in0]`、`entry_data=[agent.in1]`、
    `exit_data=[agent.out0]`、`join_port=marker.out0`;
  - 现有连线语义(数据通道扇出 + join 收集 marker)零改动;
- 模板:新增「Agent 答疑流(多 Agent 串联)」(start → agent·思考并回复 →
  agent·专家审核 → agent·发送最终消息 → output,即 SCREEN 05 的链)、
  「多 Agent 数据分析流(数据库)」与「多 Agent 数据分析流(CSV)」,
  中英各一。后两者采用**四角色模式**:确定性节点取数(db_query/file_data)
  → agent·画像与计划(产出分析计划,不分析)→ agent·分析执行(按计划
  取数计算)→ agent·数字复核(独立重算,确认/修正)→ visualize →
  agent·分析报告;db 版 agent 挂 datasources+sql_query/code_interpreter
  (+mysql-dba skill 可选),csv 版挂 code_interpreter(+excel-analyzer
  skill 可选),体现「计划-执行分离 + 生成-批判分离」的多 Agent 组合范式。

### 4.4 清单端点

`GET /api/v2/serve/awel/taskflow/agent-options` →

```json
{
  "profiles": [{"id":"react_data","label":"数据分析 Agent","label_en":"...","desc":"...","default_tools":[...]}],
  "tools": [{"id":"knowledge_retrieve","label":"知识库检索","label_en":"...","group":"builtin"}],
  "skills": [{"name":"excel-analyzer","label":"Excel 分析","label_en":"...","desc":"..."}]
}
```

- `profiles` / `tools`:P0 静态返回;
- `skills`:从 skill registry 实时枚举(`get_registry().list_skills()`,含内置
  与用户上传的 .skill 包);
- `datasources` / `knowledge` 列表**复用前端已有数据源**(getDbList 与 rag
  spaces 接口),不进本端点;
- P1 接入连接器注册表(用户保存的 MCP server 列表)。

### 4.5 事件协议扩展(小改)

`build_step_marker` 的 `status` 枚举增加 `"running"`(现有 success/failed 不变);
`TFStepMarkerOperator` 无需改动(agent 算子自行构造 marker 推送,不走 marker
算子——marker 算子仍保留用于最终 join,保证历史文本完整)。

## 5. 前端改造

### 5.1 画布(`pages/taskflow/editor.tsx` + `components/taskflow/editor/*`)

- `NodePalette`:新增「Agent」节点条目(🤖,group 色);
- `TaskflowNodeCard`:agent 节点显示 profile 名 + goal 摘要(15 字截断),
  样式与 ai_analysis 一致;
- `PropertyPanel`:
  - `agent_profile` → Select(options 来自 §4.4 端点,useRequest 加载);
  - `goal` → Textarea;
  - `tools` → 内置工具勾选列表(对齐对标形态的连接器 UI);
  - **资源三组多选**(对齐 SCREEN 05 的 chips + 下拉勾选形态):
    `skills`(options 来自 §4.4 端点)、`datasources`(getDbList)、
    `knowledge`(rag spaces 列表);均为「搜索 + 勾选 + 已选 chips 可移除」;
  - `mcp` → URL 列表输入(P0;P1 改连接器勾选);
  - `max_turns` → InputNumber;
  - types/taskflow.ts 的 `ITaskflowConfigField.type` 增加 `'multiselect'`;
- 校验:`missingRequiredFields` 已通用,goal 必填自动生效。

### 5.2 对话步骤卡(`pages/index.tsx` + `ManusLeftPanel.tsx`)

- `syncSteps` 支持 `marker.status === 'running'` → 步骤显示 running(目前只
  映射 failed/done);
- 步骤卡内容区:agent 节点的运行中事件会反复推送 marker+累积日志,前端
  keep-last 去重后自然形成「卡片内实时滚动的小步骤轨迹」;无需新组件;
- (P1)节点内 dispatch 的子 agent 用现有 `SubAgentSection` 渲染,需要把
  sub-agent 事件引入 chat_flow 通道(P2 候选)。

### 5.3 内置 Agent 画像(P0 三个)

| id | 名称 | 系统 Prompt 骨架 | 默认工具 |
|---|---|---|---|
| `react_data` | 数据分析 Agent | 资深数据分析师,目标驱动,允许调 SQL/代码复核 | sql_query, code_interpreter |
| `react_knowledge` | 知识答疑 Agent | 企业知识专家,先检索再回答,引用来源 | knowledge_retrieve |
| `react_general` | 通用任务 Agent | 谨慎的任务执行者,善用可用工具 | (全部内置白名单) |

## 6. 分期

### P0(本方案主体,~3-4d)

1. `agent_runner.py` 抽取 + 单测(事件回调、结果清洗、MCP 只读过滤);
2. `TFAgentOperator` + 渐进步骤事件(复用旁路队列);
3. DSL/compiler/manifest(`agent` kind)+ 中英各 1 模板;
4. agent-options 端点(静态);
5. 前端 palette/panel/card/multiselect + syncSteps running;
6. 端到端冒烟:答疑流、取数复核流。

### P1

- `agent_profile: "gpts:<app_code>"` 引用用户 Agent 应用(复用其
  resources/prompt/llm_strategy);
- 连接器注册表(保存 MCP server 配置,勾选引用,替代 URL 内联);
- Agent 节点失败自动重试(接 `classify_agent_error` 的 retryable 分类);
- lead_agent 节点(节点内 dispatch_parallel_tasks,子 agent 平行执行)。

### P2

- chat_flow SSE 引入 sub_agents 协议,子 agent 用 SubAgentSection 全量渲染;
- 脚本节点(内嵌 Python/JS,沙箱执行);
- Agent 节点间消息线程可视化(AgentBranchOperator 分支编排)。

## 7. 风险与开放问题

1. **时延**:Agent 节点 = 多轮 LLM,单节点 30s-2min;渐进事件必须够"活"
   (每个 ReAct 回合都推),否则用户感知比 ai_analysis 更差 → P0 验收点。
2. **上下文膨胀**:上游 markdown 表 + ReAct 多轮观察,容易爆窗口;goal 组装
   截断 + profile 内上下文管理(init_context_management 已有)。
3. **工具写操作**:MCP 只读过滤是硬约束(P0 节点内禁止写工具与再 dispatch),
   在 runner 层强制,不依赖 prompt。
4. **成本**:画像默认 max_turns=10,模板里收紧;前端属性面板露出。
5. 开放:agent 节点的输出是否带「引用/工件」(citations/artifacts)进
   TaskFlow 的引用体系?(与 dbgpt-citation-references-design 汇合,P1 定)
