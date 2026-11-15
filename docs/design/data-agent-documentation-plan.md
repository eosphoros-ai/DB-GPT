# Data Agent 文档改版方案

状态：双语文档、导航与真实产品界面截图已实施；构建与浏览器核验记录见
[验收记录](./data-agent-documentation-validation.md)。模型额度不足阻止新增场景成果实跑，
已将入口配方、历史取数成果和待复核看板草稿分别标明。

## 1. 现状与缺口

- 改版前，`docs/docs/overview.mdx` 与 README 定位为通用 agentic AI data assistant，重复罗列 SQL、代码、Skills、报表、沙箱等能力，未解释可信与受控如何贯穿业务任务。
- 改版前，`docs/docs/use_cases.mdx` 以 pi harness 的取数、画像报告与 TaskFlow 为主，不对应当前首页官方插件场景。
- 语义中心已有内部设计稿和只读工具说明，但缺少面向用户的概念、上手、指标治理、引用与故障排查指南。
- 当前 `docs/docs/dbgpts/` 主要介绍单个 Skill；缺少插件与 Skill 的关系、官方插件目录、导入与生命周期指南。
- 现有 Workflow 文档已经包含 Agent 节点、人工确认、运行状态和产物，但定位主要是 pipeline 与节点配置，需要补充 Agentic Workflow 的问题、设计理念、阶段契约与介入机制。审批、Harness 等参考通过链接整合。
- PR 中的 3 张英文截图仅说明界面，不能代替场景实跑与产品使用文档。

## 2. 产品定位与愿景

推荐主标题：

> DB-GPT: Open-Source Data Agents for Trusted, Controlled Data Work

英文介绍：

> DB-GPT helps teams turn business questions into traceable queries, analysis, reports, and dashboards—using governed semantic definitions, reusable plugins, agentic workflows, and controlled tool execution.

中文定义：

> DB-GPT 是面向业务数据工作的开源 Data Agent 平台，将业务问题转化为可追溯的查询、分析、报告与看板，通过可治理的语义定义、可复用的插件、可检查的 Agentic Workflow 和受控的工具执行，降低团队使用 AI 完成数据任务的成本。

愿景：让团队能够在明确的数据、业务口径与执行边界内，委托 Agent 完成数据工作，并核验结果、追溯过程、复用方法。

“可信”强调口径来源、指标版本、真实执行与交付证据；“受控”强调当前选择的数据源、工具权限、审批、隔离执行，以及复杂任务的阶段、任务、产物与 Gate。二者是产品方向和具体机制，不承诺自动消除所有计算错误或提供尚未实现的企业权限体系。

阅读主线：

```text
业务问题
  → 选择数据与场景
  → 读取语义定义
  → 使用插件的方法与工具
  → 复杂任务按 Flow 阶段组织 Agent 协作与检查
  → 在执行规则与审批边界内完成任务
  → 交付查询、报告、看板或专家建议
  → 核验定义、执行记录与结果证据
```

## 3. 信息架构

| 文档入口 | 核心问题 | 建议落点 |
| --- | --- | --- |
| Overview | 是什么、为谁服务、解决什么问题、先试什么 | 改写 `overview.mdx` |
| Quick Start | 如何完成第一次数据任务 | 复用安装指南，新增 `data-agent/quickstart.md` |
| Showcases | 首页场景能交付什么、如何复现 | 改写 `use_cases.mdx` |
| Data Agent Concepts | 语义、插件、Flow、工具、审批与成果如何协作 | 新增 `data-agent/concepts.md` |
| Semantic Center | 如何管理可信业务定义 | 新增 `semantic-center/` |
| Plugins | 如何选择、使用和扩展场景能力 | 新增 `plugins/` |
| Agentic Workflow | 如何组织长程多 Agent 任务，检查阶段产物并介入异常 | 重构现有 `workflow/` 用户指南 |
| Controlled Execution | 哪些控制实际生效、如何配置与检查 | 新增 `data-agent/controlled-execution.md`，链接已有审批、沙箱与 Harness 指南 |
| Developer Reference | 如何扩展工具、插件与执行引擎 | 复用现有开发文档，新增插件格式参考 |

英文为默认文档，中文同步到 `docs/i18n/zh-CN/docusaurus-plugin-content-docs/current/`。调整 `docs/sidebars.js` 与中文导航翻译，将 Semantic Center、Plugins 和 Agentic Workflow 作为用户可见的一等入口，保留 Skills 的独立使用与开发资料。

## 4. Overview 改写结构

1. 一句定义与产品愿景。
2. 业务痛点：数据库有结构但缺业务含义；同名指标口径不一；多步取数容易重复汇总；漂亮报告缺乏证据；执行工具缺边界；专家方法难复用；长程多 Agent 协作流程偏离、任务遗漏、结果难校验、异常后难以继续。
3. 四个产品支柱：Governed Semantics、Reusable Scenario Plugins、Agentic Workflow、Controlled Execution。
4. 首页业务场景：智能取数、智能分析、SQL 优化、元数据与架构、财报分析。
5. 一条完整任务路径：连接数据 → 准备语义 → 选择插件 → 复杂任务用 Flow 组织阶段 → 执行与必要确认 → 核验交付。
6. 首次体验入口与条件：模型、数据源或文件、必要工具环境、示例依赖。
7. 当前能力边界与深入阅读链接。
8. 技术生态 AWEL、RAG、SMMF、Harness 等移至末尾，面向开发者展开。

减少当前 “Why / Product Workflow / Core Capabilities” 重复卡片。README 的定位、场景入口与截图同步更新，文档站 tagline 也同步改写。

## 5. 语义中心文档

建议 5 篇：

- `semantic-center/overview.md`：概念、痛点、术语及与数据源和知识库的关系。重点解释数据空间、元数据、业务语义、指标、指标版本、样例、关系和护栏。
- `semantic-center/quickstart.md`：连接与登记 → 同步元数据 → 激活与采样选项 → 生成草稿 → 审核业务定义 → 发布指标 → 在取数中读取并引用。
- `semantic-center/metrics-and-governance.md`：公式、单位、时间字段、过滤、去重与依赖如何构成指标定义；草稿与发布的区别；历史版本与精确引用。
- `semantic-center/using-with-data-agent.md`：选定数据库后搜索业务含义和已发布指标、读取精确版本、核对元数据、执行只读 SQL、打开引用核验。以首页“净实收”问题为贯穿案例。
- `semantic-center/troubleshooting.md`：未登记、未激活、草稿未发布、别名未命中、版本不存在、元数据过期、空结果和跨库隔离。

核心示例：净实收是否含运费、支付与退款跨月如何归属、明细 JOIN 为什么会放大金额。使用已有 `Semantic_Commerce_Case` 示例时明确它是演示数据，不能作为真实经营结论。

概念关系：数据库提供物理事实；语义中心保存并治理业务定义；知识库用于资料与检索；插件提供任务方法；工具产生真实执行结果。检索索引不等于权威定义，也不等于执行授权。

## 6. 插件中心文档

建议 4 篇：

- `plugins/overview.md`：插件是面向场景的能力包，组合 Skills、提示、快捷命令、工具配置及上下文约定；区分 Plugin、Skill、Tool、Workflow。
- `plugins/using-plugins.md`：官方目录、企业导入、Installed 视图、搜索、详情、启停、卸载、首页选择、快捷命令与所需数据条件。
- `plugins/official-plugins.md`：5 个官方插件的适用问题、输入、交付物、示例与限制；名称与首页保持一致。
- `plugins/package-reference.md`：`.dbgpt-plugin/plugin.json`、`SKILL.md`、资源目录、ZIP 导入和 QwenWork / `suite.yaml` 兼容；区分必要字段、可选字段和实际消费的配置。

必须说明：Market 标签目前是占位；Installed 当前表示 enabled 的插件视图；插件存在或启用不代表任意工具都被授权，也不保证所有依赖已配置。

## 7. Agentic Workflow 文档

推荐名称：**Agentic Workflow**；Flow / TaskFlow 用于说明产品实现名称，AWEL 留在技术参考中。

核心定义：

> Agentic Workflow 以 Agent 为任务节点，用明确的阶段、任务、产物和 Gate 组织协作。Agent 在节点内部自主选择方法并使用工具，Flow 在节点之间管理依赖、进度和检查点，配合状态监控与异常拦截，让复杂任务更稳定、可检查、可介入。

英文定义：

> Agentic Workflow organizes agents around explicit stages, tasks, deliverables, and gates. Agents decide how to complete their assigned work, while the flow coordinates dependencies, exposes progress, and provides checkpoints for review and intervention.

问题陈述采用用户提出的主线：

> 基于 Prompt 或 Skill 的多 Agent 协作约束较弱，在长程、复杂任务中容易出现流程偏离、任务遗漏、结果不可校验和异常无法继续等问题。Flow 通过明确阶段、任务、产物和 Gate，并配合状态监控与异常拦截，让复杂任务的执行过程更稳定、可检查、可介入。

与传统工作流的比较应解释不同的建模方式，避免笼统声称传统工作流都死板：

| 维度 | 预设操作式工作流 | 仅靠 Prompt / Skill 约定协作 | Agentic Workflow 的设计方向 |
| --- | --- | --- | --- |
| 建模对象 | 操作、接口、字段和分支 | 角色说明与文字协作规则 | 阶段目标、Agent 任务、产物和 Gate |
| 用户理解 | 需要提前拆解技术步骤和参数 | 描述目标容易，执行路径不够显式 | 先描述业务阶段，再设置责任与交付要求 |
| 阶段内执行 | 依照预设操作执行 | Agent 自主选择方法 | Agent 在资源与工具边界内自主完成任务 |
| 阶段间协作 | 显式连线与数据传递 | 主要靠上下文约定 | Flow 管理依赖与阶段产物传递 |
| 校验与介入 | 可配置规则与人工任务 | 取决于提示遵循与工具支持 | 专门复核 Agent、产物要求和人工 Gate |
| 异常处理 | 取决于引擎的重试与恢复机制 | 恢复位置和完成项可能不明确 | 展示失败阶段和原因，阻止无效下游，并明确可用恢复操作 |

“每个节点代表一个 Agent”作为业务任务层的核心心智模型：一个任务节点承担一项明确责任。实际图中仍有 start、output、data entry、human_confirm 等辅助节点，文档区分任务节点与控制节点。

每个任务节点围绕以下字段讲解，界面名与执行约束逐项核对：

- **阶段与目标**：该 Agent 负责什么，不负责什么。
- **输入与依赖**：原始问题、上游产物以及允许访问的数据。
- **方法与资源**：Prompt、Skill、工具、模型与预算。
- **产物契约**：下游需要哪些结果、格式与证据，什么算完成。
- **Gate**：哪个检查点由复核 Agent 或人决定是否继续。
- **运行与异常**：状态、工具证据、失败原因以及修复后如何处理。

推荐文档改造：

1. 改写 `workflow/introduction.md`：理念、适用任务、三种协作方式比较及与插件和 Skill 的关系。
2. 改写 `workflow/quickstart.md`：用销售分析模板完成一次多 Agent 任务，先理解阶段与产物，再讲编辑器操作。
3. 补充 `workflow/editor.md` 与 `workflow/nodes/agent.md`：如何定义责任、资源、产物与预算；简单用户先用模板，高级用户再看字段。
4. 新增 `workflow/contracts-and-gates.md`：产物契约、独立复核、人工 Gate、业务确认与工具审批的区别。
5. 更新 `workflow/runs-and-artifacts.md` 与 `workflow/troubleshooting.md`：状态监控、产物检查、错误定位、介入与真实可用的恢复路径。
6. 新增 `workflow/examples.md`：销售分析、财报比较、SQL 诊断等复杂任务如何分阶段组织。

贯穿示例：

```text
语义与需求 Agent：确定指标定义、范围与时间
  → 计划确认 Gate：用户确认分析范围
  → 取数 Agent：执行查询并交付结果
  → 分析 Agent：计算、比较、解释变化
  → 复核 Agent：独立检查数字、口径与证据
  → 报告 Agent：生成可核验的业务交付物
```

产物示例包括口径清单、取数计划、执行结果、分析结果、复核意见和最终报告。示例图表达目标流程，内置模板的实际节点与自动检查能力须另行核实。

需要明确的边界：

- `Output:` 提示约定不等于执行层自动校验；区分模型遵循、复核 Agent、确定性验证和人工确认。
- 工作流阶段 Gate 与单次高风险工具审批是两种不同控制。
- 异常定位与拦截不等于断点续跑。分别核对重新运行、局部重试、复用成功产物、刷新后重新连接、服务重启恢复的实际支持。
- 现有运行与排查文档对历史回放的表述不一致，实施时必须以最新代码与浏览器验证为准。
- 降低理解成本通过模板、业务阶段命名、清晰产物与渐进展示实现，不宣称所有复杂任务都无需配置。

## 8. Showcases 与重新截图

首页已启用官方插件是场景清单来源，固定文章顺序与当前首页一致：

| 场景 | 推荐案例 | 要展示的交付与可信证据 |
| --- | --- | --- |
| Smart Data Query | 净实收取数或跨月归属 | 已执行 SQL、金额与单位、指标版本引用 |
| Smart Data Analysis | Walmart 销售分析与经营看板 | 报告或看板、关键图表、对应执行证据、规划确认 |
| SQL Optimization Expert | 当前首页 SQL 诊断示例 | 原 SQL、诊断证据、改写或索引建议；明确是否实际执行变更 |
| Metadata and Architecture Expert | 当前首页数据字典或 ER 示例 | 数据字典、ER 或结构文档；区分真实约束与推断关系 |
| Financial Report Analysis | 解读年报或比较财报 | 文件来源、指标与报告引用；明确期间和单位 |

SQL 与元数据案例的具体提示词以重拍时首页实际推荐项为准。

每个案例统一模板：业务问题 → 前提与数据 → 首页场景及推荐问题 → 实际操作 → 交付物 → 证据与边界 → 如何复现。

在首页场景之后增加一个 Agentic Workflow 深入案例：展示同类复杂任务如何拆成有交付要求的 Agent 阶段，以及人工确认、独立复核与失败定位。

建议新拍 9 张：1 张英文首页场景全景、5 张场景交付、1 张分析看板补充、1 张工作流阶段图、1 张运行状态与 Gate。功能指南可复用之前的 3 张语义与插件截图，并在必要时补充指标引用详情；PR 仍只保留此前约定的 3 张图。各场景文章按需使用图片，避免在 overview 堆叠全部截图。

截图规范：

- 通过正常语言切换使用英文界面，统一主题与桌面尺寸，真实浏览器截图。
- 首页是操作入口，成果页是结果证据；不能只截输入框就声称任务完成。
- 保留可复现提示、数据来源、运行状态和成果对应关系。
- 现存历史仅在执行证据与成果完整时复用，并明确是历史运行；不足则实跑，失败如实记录。
- 不通过修改 DOM、替换内容或伪造数据制作成功截图。
- 演示数据库注明来源；用户资料、凭据及无关历史不进入公开图片。
- 新文档资源按语言放 `docs/static/img/data-agent/en/` 与 `docs/static/img/data-agent/zh-CN/`，MDX 引用对应目录。英文文档使用英文界面截图，中文文档使用中文界面截图，不跨语言复用。

## 9. 实现边界核验

语义中心当前只读工具说明明确：

- 四个数据库绑定工具读取元数据、已发布业务释义、指标搜索与精确版本快照。
- 搜索以结构化关键词与已保存别名为主，不应宣称向量发布器已接通。
- 草稿不作为已发布指标返回；精确版本缺失不自动切换版本。
- 规则、关系、样例消费、执行前 SQL 口径校验、持久化会话 pin 与语义权限强制执行，不能仅因 UI 或设计稿存在就宣称已实现。

实施时还需核对最新服务代码。将能力分为“界面可维护”“Agent 已消费”“执行层强制”“设计目标”，逐项写清。元数据快照不是实时结构保证；展示 tenant 规则不等于执行层已强制隔离。

引用链说明其实际覆盖范围；避免声称所有结论、所有图表都有自动完整溯源。

## 10. 执行次序与验收

1. 核对 UI、API、工具注册、插件 manifest 与现有证据，形成能力边界表。
2. 改写 Overview / README / tagline，建立用户文档导航。
3. 补齐语义中心、插件与 Agentic Workflow 指南，复用已有技术参考。
4. 根据首页示例验证场景及工作流案例并重拍英文截图，替换 Showcases。
5. 同步中文，检查术语、链接、图片、步骤与演示数据说明。
6. 构建英文和中文文档并浏览器检查导航与核心页面。

验收标准：读者能理解“为什么可信与受控”，按步骤完成一次语义支持的取数，选择并使用一个插件，理解一个多 Agent Flow 的阶段责任、产物和 Gate，并能查看状态、定位失败与核验交付；所有 showcase 的成功描述都有相应实跑或完整历史证据；未实现能力与失败案例不被写成成功。

## 11. 本轮核对依据

- `docs/docs/overview.mdx`、`docs/docs/use_cases.mdx`、`docs/docs/dbgpts/introduction.md`
- `docs/docs/application/high_risk_tool_approval.md`
- `docs/docs/workflow/introduction.md`、`nodes/agent.md`、`nodes/human-confirm.md`、`runs-and-artifacts.md`、`troubleshooting.md`
- `docs/design/semantic-center-impl-plan.md`、`docs/design/semantic-center-read-tools.md`
- `web/pages/index.tsx`、`web/utils/suite-routing.ts`
- `web/pages/construct/semantic.tsx`、`web/pages/construct/suites/index.tsx`
- `assets/suites/*/.dbgpt-plugin/plugin.json`
