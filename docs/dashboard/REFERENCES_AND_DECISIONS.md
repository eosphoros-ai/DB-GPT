# 参考资料、许可证与独立实现说明

本文件区分“借鉴思想”和“复制代码”。本模块代码均在 DB-GPT 代码结构中独立实现；没有从博客或其他 BI 项目复制实现代码。

## 1. 直接依赖与上游

| 来源 | 链接 | 许可证 | 用途 | 是否复制代码 |
|---|---|---|---|---|
| DB-GPT | https://github.com/eosphoros-ai/DB-GPT | MIT | ReAct Agent、SSE、数据源 Connector、Ant Design/AntV、旧 Dashboard 上下文 | 在原仓库内扩展，保留上游历史和许可证 |
| react-grid-layout | https://github.com/react-grid-layout/react-grid-layout | MIT | 12 列拖拽、缩放和容器宽度 | 作为 npm 依赖调用公开 API |
| Ajv | https://github.com/ajv-validator/ajv | MIT | 浏览器 JSON Schema 快速校验 | 作为 npm 依赖调用 |
| sqlglot | https://github.com/tobymao/sqlglot | MIT | SQL AST 解析和方言处理 | 使用现有项目依赖调用 |
| AntV / Ant Design | https://antv.antgroup.com/ / https://ant.design/ | MIT | 图表和界面体系 | 复用 DB-GPT 现有组件和依赖 |

## 2. 设计参考

| 来源 | 链接 | 采用的思想 | 未直接照搬的部分 |
|---|---|---|---|
| v0 Dashboards / SalesOps | [模板目录](https://v0.app/templates/dashboards) · [具体模板](https://v0.app/templates/9q2Mfgu6cDi) | KPI 摘要、8:4 主趋势与辅助图表、下层明细，落地为“趋势聚焦” | 用现有网格、AntV 和主题独立实现；不导入模板代码或截图资产 |
| Tremor Templates / Overview | [模板目录](https://blocks.tremor.so/templates) · [具体页面](https://dashboard.tremor.so/overview) | 规则的指标比较、等宽图表、克制的边界，落地为“指标概览” | 不添加 Tremor 依赖；是否显示周期比较仍取决于真实查询口径 |
| Tabler Admin | [模板介绍](https://tabler.io/admin-template) · [实际预览](https://preview.tabler.io/) | 紧凑指标、操作性明细、辅助诊断图，落地为“运营明细” | 不引入 Bootstrap 或原站组件；保留 DB-GPT 原有操作和权限流程 |
| Apache Superset | https://github.com/apache/superset | 编辑态与展示态分离、筛选器作用范围、图表元数据 | 未复制 Apache-2.0 代码或数据库模型 |
| JSON Schema 2020-12 | https://json-schema.org/draft/2020-12 | 版本化结构合同和跨语言校验 | 跨字段/SQL 规则仍由后端实现 |
| OWASP SQL Injection Prevention Cheat Sheet | https://cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.html | 参数化查询、允许列表、最小权限 | 没有把关键词过滤当作唯一防线 |
| ReAct 论文 | https://arxiv.org/abs/2210.03629 | 推理—行动—观察的 Agent 工具流程 | Dashboard 采用确定性服务端校验，不让推理文本决定安全 |
| SEC EDGAR | https://www.sec.gov/edgar | 公开、可追溯财务演示数据 | 不批量再分发原始申报文档，只保存少量结构化事实和来源 |
| Wren AI GenBI | https://docs.getwren.ai/oss/guides/genbi | 上下文层、自然语言迭代、预览后发布，以及快照/实时数据边界 | 未复制其 CLI、MDL、WASM 或应用代码 |
| Vanna AI 2.0 | https://vanna.ai/docs/ | 用户感知 Agent、受权限约束的数据库工具、工具记忆 | 未采用其运行时、工具注册或记忆实现 |
| Tableau Agent | https://help.tableau.com/current/pro/desktop/en-us/desktop_einstein.htm | 对话式分析与传统可视编辑共存 | 未复制 Tableau 交互或专有实现 |
| Power BI Copilot | https://learn.microsoft.com/en-us/power-bi/create-reports/copilot-create-reports | 通过自然语言增删改可视对象，保留撤销/重做和人工保存 | 未复制 Power BI 代码或专有视觉组件 |
| Kaggle Olist 数据集 | https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce | 真实电商多表关系、订单/履约/支付/评价分析案例 | 未提交原始 CSV；下载版本、许可证和校验值单独固定 |

## 3. 财务案例来源

- Apple 2024 Form 10-K：
  https://www.sec.gov/Archives/edgar/data/320193/000032019324000123/aapl-20240928.htm
- Apple 2023 Form 10-K：
  https://www.sec.gov/Archives/edgar/data/320193/000032019323000106/aapl-20230930.htm
- 本地来源清单：`examples/dashboard/sources/apple-sec-sources.json`
- 口径：财政年度，金额为百万美元；提取值用于产品功能演示，不构成投资建议。

Walmart 案例是确定性合成数据，字段形状接近常见门店周销售数据，但不声称来自 Walmart 官方或 Kaggle 原始数据。

Olist 案例使用 Kaggle 上由 Olist 发布的 Brazilian E-Commerce Public Dataset，
许可证为 CC BY-NC-SA 4.0。仓库只保存下载清单、加载与校验代码、Schema
和聚合标准答案，不再分发原始 CSV。固定版本与 SHA-256 见
`examples/dashboard/olist/source-manifest.json`。

## 4. 关键决策记录

### D1：统一 Schema，不让前端解析自然语言

- 决策：Agent 只产生结构化计划和查询草稿，前端只渲染 Schema。
- 原因：减少模型表述变化导致的脆弱解析。

### D2：计划和 SQL 分两阶段

- 决策：先确认业务问题，再生成 SQL。
- 原因：便于检查指标/维度合理性，也能精确修复失败组件。

### D3：模型不能提交数据源 ID

- 决策：`DashboardWidgetQueryDraft` 不含数据源；服务端注入当前选择。
- 原因：防止模型通过工具参数换到其他连接。

### D4：分享固定快照

- 决策：匿名页不实时查询数据库。
- 原因：隔离权限、保证可复现、避免分享链接变成查询 API。

### D5：局部失败而非全有或全无

- 决策：失败组件保存错误，成功组件保留。
- 原因：模型生成成本高，用户应该能利用已有成果。

### D6：旧版只做单向适配

- 决策：导入时创建新草稿，不原地改旧记录。
- 原因：降低已有功能回归风险，便于回滚。

### D7：CSDN/博客只做线索

- 决策：安全、接口、许可证和架构结论必须回到官方文档、源码或论文核对。
- 原因：二手文章可能过期、缺少上下文或授权不明。

### D8：AI 修改先形成提案，再由用户应用

- 决策：批注只生成受限变更方案；服务端校验完成后展示差异，用户确认才写回草稿。
- 原因：参考成熟 BI 产品“对话辅助 + 人工编辑”的共同方向，同时避免模型静默覆盖已保存成果。

### D9：批注目标使用稳定 ID，不使用数组下标

- 决策：组件、系列和数据点通过稳定标识进入 Agent 上下文，服务端再映射到真实 Schema 路径。
- 原因：布局、排序或新增组件后数组位置会变化；稳定标识可以降低误改其他组件的风险。

### D10：手工筛选器必须同时具备值域与 SQL 绑定

- 决策：从当前已验证查询结果提取候选值，并且只把筛选器绑定到确实使用对应命名参数的组件。
- 原因：只有下拉选项而没有 SQL 参数映射时，筛选器只是界面装饰；自动绑定也不能猜测不存在的查询参数。

### D11：多表案例必须用同一份源数据对拍 SQLite 与 MySQL

- 决策：Olist 的八张核心 CSV 由同一加载器写入 SQLite/MySQL，并由同一组业务查询与 `gold_answers.json` 核验。
- 原因：分别制作两套演示库会掩盖方言、类型和联接差异，无法证明实现具有可迁移性。
- 约束：支付、订单项和评价先聚合到订单粒度再联接，禁止直接把多个一对多明细同时联接后汇总金额。
- 证据：`examples/dashboard/olist/verify_olist.py` 会逐字段比较查询结果；SQLite/MySQL 任一路径不一致即失败。

### D12：参考模板是确定性的组件布局，不是演示数据

- 决策：新增 `trend-focus`、`metric-overview`、`operations-detail` 三个布局族，前后端读取同一份 `schema/dashboard-layout-templates.json`；用共享验收案例核对两端布局结果。
- 新建：三张业务模板卡片在规划提示中携带 `layout_template`，确认后服务端排列真实组件并应用配套样式。该字段可省略；省略时继续使用原有逐组件布局。计划修订时，省略保留上次选择，显式 `null` 恢复自定义。
- 编辑：工具栏“布局模板”先用当前快照预览；应用只调整桌面坐标与用户勾选的配套样式，保留明暗模式、查询、指标口径、筛选器及组件标识，一步撤销。保存和发布沿用 Schema 1.4 的现有协议，未发布的布局不会改变历史快照。
- 布局：指标优先；趋势页优先展示折线/面积/双轴图，运营页优先展示表格；缺少某类组件时自然收拢，数量较多时均衡分行，不添加占位指标。仪表盘保留图表高度。手机端按桌面坐标顺序堆叠，键盘与视觉阅读顺序一致。
- 视觉：沿用系统中文无衬线字体和四套现有主题，通过圆角、边界、密度和表格样式形成区别。原生 SVG 只用于标明“布局示意”的缩略图，实际预览始终使用当前组件和快照。
- 取舍：模板控制结构与配套样式，不覆盖已有组件的颜色、格式和查询配置；应用后仍可拖拽、缩放或通过主题面板继续调整。

## 5. 独立实现部分

以下为本项目新增设计和代码，不是从上述项目复制：

- Dashboard Schema v1 的字段与跨字段规则；
- 两表草稿/不可变发布修订模型；
- SQL 安全层与筛选器数组参数扩展；
- 两阶段 Agent Planner、局部错误草稿和同 ID 修复；
- Dashboard 专用 SSE 事件和新建页生成卡；
- Schema 驱动编辑器与分享页；
- 旧 `ReportData` 适配器；
- 两个可复现 Demo 构建脚本、Schema 和自动查询测试；
- 本目录设计、安全、测试和业务演示文档。
- 未保存组件的自动草稿持久化、独立看板到来源任务的批注交接；
- 从真实结果列导入筛选选项并按命名参数绑定兼容组件。
- Olist 八表关系模型、CSV 流式加载器、跨方言标准查询、结果对拍器与 Schema 1.3 多表案例。
