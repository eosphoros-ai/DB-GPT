# 财报智能分析工作台 · 产品设计方案稿

> 版本 v0.1 · 2026-10-19 · 作者：产品/架构组
> 交付形态：Markdown 方案稿 + 单文件 HTML 高保真 mockup（`docs/design/financial-report-analysis-mockup.html`）
> Case 载体：`examples/pdf/2020-01-23__浙江海翔药业股份有限公司__002099__海翔药业__2019年__年度报告.pdf`（204 页，含合并三大表、分季度、分板块、费用与研发披露）

---

## 0. TL;DR — 一句话产品定义

在 DB-GPT 现有 `FinancialReport` 领域能力之上，做一个 **对话式财报分析工作台**：以「文档→章节→段落→原句→PDF 坐标高亮」四级证据链为核心心智，用 **工作流做数据处理骨架、ReAct Agent 做自然语言分析血肉、确定性事实账本（Fact Ledger）+ 对抗式复核器（Verifier）兜住数字幻觉**。首批落地在 A 股年报场景，直接复用仓库已有的 `DOMAIN_TYPE_FINANCIAL_REPORT`、`PDFKnowledge`、`ToolCallingReActAgent`、`chat_with_domain_flow`、`agentic_data_api` SSE 事件、AntV S2/G2 前端栈，不做推倒重来。

**核心决策一句话：** 数据处理 = 工作流；NL 分析 = 骨架工作流 + 血肉 ReAct Agent（Router 分诊）；数字一律走 Fact Ledger 或 abstain，不让 LLM 心算。

---

## 1. 产品定位

### 1.1 目标用户与 JTBD

| 角色 | JTBD（Jobs To Be Done） | 现有痛点 |
|---|---|---|
| 券商行研分析师 | 快速读懂一份新出的年报，找出关键变化点、异常科目、管理层叙事与数字是否一致 | 200+ 页 PDF 人工翻阅 3-4 小时；跨期对比手工建 Excel |
| 一级投资经理 | 尽调阶段批量筛财报，标记红旗（应收账款异动、经营现金流与利润背离、非经常性损益占比高） | 每份报告要看 30+ 项指标，容易漏 |
| 上市公司 IR/财务 | 编制年报解读、路演材料，快速回答投资人提问 | 数字与叙事的一致性人工核对成本高 |
| 财经媒体/自媒体 | 抓热点公司的年报亮点，快速产出解读稿 | 缺乏可追溯的引用，容易被质疑数据来源 |

### 1.2 差异化定位（对标业界）

| 维度 | 主流产品做法 | 我们的取舍 |
|---|---|---|
| **交互形态** | Wind Alice / 通义点金 / AlphaSense：偏"结构化流水线一键出报告"；Perplexity Finance / Hebbia：偏"对话式" | **对话式分析工作台**（用户已选定）：以对话为主入口，报告/图表/对比作为可复用产物侧挂，用户随时"追问"下钻 |
| **数据基础** | 大部分产品用 Wind/Choice/巨潮 XBRL 结构化库；Rogo/Hebbia 更依赖 raw PDF | **双轨**：raw PDF（可追溯）+ Fact Ledger（可计算），两者互相锚定；对未结构化数据（管理层讨论、异常项说明）走 raw，对数字走 ledger |
| **推理引擎** | 问财/Alice：NL2SQL 为主，工作流固化；支小宝/点金：多智能体；Rogo：plan-and-execute + per-clause citation | **Router + ReAct + Verifier 混合**：事实查询/指标计算走确定性 SQL；归因/对比/评估走 ReAct；所有数字出口过 Verifier |
| **证据链** | Rogo：per-clause citation；PageIndex/Mafin：树导航 + 句级引用；国内产品多数只到段落级 | **四级下钻 + PDF bbox 高亮**（用户已选定最高粒度）：文档→章节→段落→原句→坐标高亮，配计算过程展开 |
| **数字幻觉防御** | 大多数产品未公开；FinLongDocAgent/VeNRA：论文级 | **Fact Ledger + Abstention + Adversarial Verifier** 三重闸：LLM 从不心算数字，找不到就 abstain |

### 1.3 与 DB-GPT 已有能力的关系

DB-GPT 仓库已经把「财报」列为一级领域：

- `packages/dbgpt-core/src/dbgpt/configs/__init__.py:16` 已定义 `DOMAIN_TYPE_FINANCIAL_REPORT = "FinancialReport"`
- `packages/dbgpt-app/src/dbgpt_app/openapi/api_v1/api_v1.py:832-900` 已实现 `chat_with_domain_flow` 按 `domain_type` 路由到 tagged AWEL DAG，并期望一个 `{space}_fin_report` SQLite DB（说明「已解析表格落成可查询 DB」这个思路早已埋点）
- `packages/dbgpt-ext/src/dbgpt_ext/rag/knowledge/pdf.py` 的 `PDFKnowledge` 用 pdfplumber，已经写了中文年报 header/footer 正则、"单位：人民币元"识别、表格转 markdown
- `docker/examples/fin_report/pdf/` 已经带了 5 份 A 股 2019 年报样本
- `packages/dbgpt-serve/src/dbgpt_serve/agent/agents/expand/` 已有 `anomaly_detection_agent`、`volatility_analysis_agent`、`report_generation_agent`、`metric_info_agent`
- `packages/dbgpt-core/src/dbgpt/vis/tags/` 已有 `vis_report_generation`、`vis_anomaly_detection`、`vis_volatility_analysis` 三个 finance 味道的 vis tag
- `packages/dbgpt-serve/src/dbgpt_serve/rag/domain/factory.py` 的 `DomainKnowledgeIndexFactory` 是干净的扩展点

**结论：这不是从零起步，是把已经打了地基、埋了管线但没盖楼的"财报领域"补齐并做到生产可用。**

---

## 2. 用户旅程（以海翔药业 2019 年报为 case）

### 场景 A：单份年报快速阅读（分析师视角，10 分钟）

```
1. 用户从"财报分析"入口进入 → 上传/选择 PDF（或从已入库的知识空间选择）
2. 系统显示解析进度条：解析 → 章节识别 → 表格抽取 → Fact Ledger 落库 → 向量化
   （预计 3-8 分钟/200 页；进度可视化，允许后台跑）
3. 解析完成 → 默认首屏："关键指标速览"卡片
   ┌────────────────────────────────────────────────────────┐
   │ 海翔药业 (002099) 2019 年报                             │
   │ 营业收入   29.41 亿   ▲ +8.20%  [P.7 · 可点击]         │
   │ 归母净利润  7.71 亿   ▲ +27.40% [P.7]                  │
   │ 经营现金流  6.12 亿   ▼ -22.62% [P.7] ⚠ 与利润背离     │
   │ 加权 ROE   14.07%    ▲ +2.72pct [P.7]                  │
   │ 研发费用    1.23 亿   ▲ +10.10% [P.19]                 │
   │                                                         │
   │ 🚩 3 个自动红旗：Q4 净利骤降 / 现金流-利润背离 / 应收异动 │
   │ [追问] [生成解读报告] [跨期对比]                        │
   └────────────────────────────────────────────────────────┘
4. 用户在对话框输入自然语言问题（例："为什么经营现金流同比下滑 22% 而净利润却增长 27%？"）
5. Agent 流式返回：
   - 意图行："归因分析 · 涉及现金流表 + 利润表 + 应收/存货科目"
   - 计划树（可折叠）：查 Fact Ledger → 拉现金流量表附注 → 对比应收账款/存货变动 → 生成图表
   - 结论段落，每个数字后挂 [P.xx] 证据 chip
   - 侧栏滑出：现金流量表主表（AntV S2 pivot）+ 应收账款账龄表 + 计算过程
6. 用户点击任一 [P.xx] chip → 右侧 PDF 预览器打开对应页并高亮原句 bbox
7. 用户继续追问："那应收账款前五大客户集中度是多少？" → Agent 直接跳到附注表格
```

### 场景 B：跨期/跨公司对比（投资经理视角）

```
1. 用户在"文件柜"选中 3 份年报（海翔 2017/2018/2019）
2. 点击"跨期对比" → 系统进入 Hebbia Matrix 风格视图
   行：预设指标（营收/净利/毛利/研发/现金流/ROE/应收/存货 ...）
   列：3 个年份
   每格：数值 + 同比 + 证据 chip
3. 用户在 Matrix 中选中一格 → 追问"这个数为什么这样"→ 回到对话工作台，自动带上上下文
```

### 场景 C：一键生成解读报告（IR/自媒体视角）

```
1. 用户："帮我生成一份海翔药业 2019 年报解读，1500 字，重点讲医药和染料两个板块"
2. Agent 走"报告生成"专用工作流（骨架固定：概述→财务亮点→分板块→风险→展望）
3. 每一段仍走 ReAct 内核 + Verifier，段落级引用
4. 产物：vis-report-generation 卡片，右侧滑出可复制/可导出 md 的报告面板
```

---

## 3. 业界范式抽取与关键取舍

（详细调研见附录 A；此处只列影响架构的 5 条硬结论）

| # | 硬结论 | 出处 | 对本设计的影响 |
|---|---|---|---|
| 1 | 财报问答失败的 62% 是**检索未命中**，而非推理错误；BGE-M3 在年报上 Recall@30 只有 62% | FinLongDocQA (arxiv 2604.03664) | 必须多路检索：Fact Ledger 精确匹配 → 章节树导航 → dense RAG 兜底 |
| 2 | **GraphRAG 在年报上反而退化 2.7×**（12.14 vs 33.03 EM），比 page-level dense RAG 差 | FinLongDocQA 消融实验 | **不做 KG-first**；TuGraph 只用于章节树/实体关系轻量存储，不做主检索路径 |
| 3 | 领域 SFT 反而把数字幻觉从 5.4% 拉到 98%（模板注入效应） | arxiv 2609.04806 | **不做财报 SFT**；用确定性 Fact Ledger + abstention + 通用大模型 |
| 4 | Docling 中文近乎全崩（OmniDocBench Overall ZH 0.909）；MinerU (0.310) / PP-StructureV3 (0.206) 是仅有的可用开源方案 | OmniDocBench + MinerU 4.0 报告 | **PDF 解析器换成 MinerU**，替换现有 pdfplumber 路径；保留 pdfplumber 作 fallback |
| 5 | 证监会年报章节骨架法定但**编号在不同发行人间不稳定**（英洛华"第八节可转债"→"第十二节财务报告"；\*ST 湘电"第一节释义"→"第十一节财务报告"） | 证监会准则第 2 号 + 多个 2019 年报交叉验证 | 章节路由**按标题不按序号**，配一张跨版本别名表（2017/2021/2025 三版准则） |

**借鉴的具体产物：**

- **MinerU 4.0 的 `doc:/tier:/page:/block:` 定位契约**：直接作为我们证据链的 URI 规范
- **FinLongDocAgent 的 Expansion / Solving / Evaluation 三阶段循环**：作为 ReAct 内核的骨架
- **蚂蚁 agentUniverse 的 DOE 模式**（Data-Opinion-Evidence）：作为「数字-叙事-证据」三元组的数据结构
- **VeNRA 的对抗式 3B auditor**：作为 Verifier 的实现路线（我们先用 rule + LLM 双通道，后期上小模型）
- **Rogo 的 per-clause citation + refuse-without-source**：作为答案生成的硬约束
- **Hebbia Matrix View**：作为跨期/跨公司对比 UI 范式
- **PageIndex/Mafin 的树导航 + 可拒答**：作为章节树交互范式

---

## 4. 整体架构

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                         财报智能分析工作台 · 三层架构                          │
└──────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│  L3 · 表达层  Conversation Workbench                                        │
│  ┌──────────────┬───────────────────────┬─────────────────────────────────┐ │
│  │ 左：意图/计划 │ 中：答案 + 证据 chip   │ 右：Evidence Viewer (可切换)     │ │
│  │ (timelineSlot)│ (final.chunk 流式)    │ · PDF Previewer (bbox 高亮)      │ │
│  │              │                        │ · Fact Ledger Inspector          │ │
│  │              │                        │ · Section Tree Navigator         │ │
│  │              │                        │ · Computation Trace              │ │
│  │              │                        │ · Chart / Pivot (AntV G2/S2)     │ │
│  └──────────────┴───────────────────────┴─────────────────────────────────┘ │
│  复用：ManusLeftPanel.timelineSlot / ArtifactRail / RightPanel 查看器        │
└─────────────────────────────────────────────────────────────────────────────┘
                                     ▲
                                     │ SSE (step.chunk / final.chunk / evidence.*)
                                     │
┌─────────────────────────────────────────────────────────────────────────────┐
│  L2 · 推理层  Hybrid Router + ReAct + Verifier                              │
│                                                                              │
│  ┌─────────────┐   意图分类     ┌────────────────────────────────────────┐  │
│  │ NL Question │───────────────▶│ Router (fast LLM, ~200ms)              │  │
│  └─────────────┘                 │  → 事实查询 / 指标计算 / 归因 / 对比    │  │
│                                  │  → 综合评估 / 报告生成 / 闲聊           │  │
│                                  └────────────────┬───────────────────────┘  │
│                                                   │                          │
│                    ┌──────────────────────────────┼──────────────────────┐   │
│                    ▼                              ▼                      ▼   │
│         ┌──────────────────┐         ┌────────────────────┐   ┌────────────┐ │
│         │ Deterministic    │         │ ReAct Agent        │   │ Report     │ │
│         │ Path             │         │ (ToolCalling)      │   │ Workflow   │ │
│         │ NL2SQL over      │         │ Expansion/Solving/ │   │ (TaskFlow) │ │
│         │ Fact Ledger      │         │ Evaluation loop    │   │ 骨架固定    │ │
│         │ + abstention     │         │ + 6 类工具          │   │ 段内 ReAct  │ │
│         └────────┬─────────┘         └──────────┬─────────┘   └─────┬──────┘ │
│                  │                              │                    │       │
│                  └──────────────┬───────────────┴────────────────────┘       │
│                                 ▼                                            │
│                    ┌────────────────────────┐                                │
│                    │ Verifier (双层)         │                                │
│                    │ Rule: 数字必须能匹配     │                                │
│                    │      Fact Ledger 或     │                                │
│                    │      bbox 原文          │                                │
│                    │ LLM:  对抗式审计         │                                │
│                    │      (claim vs evidence) │                               │
│                    │ → pass / revise / abstain│                               │
│                    └────────────┬───────────┘                                │
│                                 ▼                                            │
│                    Final answer + Evidence Bundle                            │
└─────────────────────────────────────────────────────────────────────────────┘
                                     ▲
                                     │ 查询/检索接口
                                     │
┌─────────────────────────────────────────────────────────────────────────────┐
│  L1 · 数据层  Ingestion Pipeline (AWEL Flow, 一次性)                        │
│                                                                              │
│  PDF Upload → MinerU Parser → Section Router → ┬─► Chunker (page+layout)    │
│           (doc:/tier:/page:/block:)  (标题+别名表)  │   → Vector Store        │
│                                                    │   → ES Full-text        │
│                                                    │                          │
│                                                    └─► Table Extractor       │
│                                                        → Fact Ledger (SQLite)│
│                                                        → 附注实体表          │
│                                                                              │
│  产物：KnowledgeSpace(domain_type=FinancialReport)                           │
│        + {space}_fin_report.db (SQLite Fact Ledger)                          │
│        + section_tree.json (导航)                                            │
│        + chunks with bbox metadata                                           │
│                                                                              │
│  复用：DomainKnowledgeIndexFactory / PDFKnowledge / AWEL operators           │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 5. L1 数据处理层 · 为什么是工作流

### 5.1 决策依据

数据处理阶段的所有子任务都是**确定性、幂等、无需推理**的：

| 子任务 | 是否需要 LLM 推理 | 是否幂等 | 失败重试策略 |
|---|---|---|---|
| PDF 解析 (MinerU) | 否 | 是 | 分块重试 |
| 章节路由 | 少量（标题匹配 + 别名表兜底可用 LLM） | 是 | 整节重试 |
| 表格抽取 | 否（模型内嵌于 MinerU） | 是 | 单表重试 |
| Fact Ledger 落库 | 少量（指标映射，可用规则+小模型） | 是 | 事务回滚 |
| 向量化 / 索引 | 否 | 是 | 批重试 |

**结论：清一色 AWEL 工作流。** ReAct Agent 在这里没有任何价值——不需要工具选择、不需要循环、不需要反思。

### 5.2 AWEL DAG 设计

复用 `packages/dbgpt-core/src/dbgpt/core/awel/` 已有的 operator 框架，新增以下 operator（放在 `packages/dbgpt-ext/src/dbgpt_ext/rag/operators/financial_report/`）：

```
[HTTP Trigger: /api/v1/knowledge/{space}/document/upload]
        │
        ▼
┌────────────────────────┐
│ MinerUParseOperator    │  → 输出 MinerUDocument{ blocks:[{type,bbox,text,page}] }
└───────────┬────────────┘
            │
            ▼
┌────────────────────────┐
│ SectionRouteOperator   │  → 用 CSRC 别名表把 blocks 归到十大节 + 附注
└───────────┬────────────┘
            │
    ┌───────┴──────────────┐
    ▼                      ▼
┌──────────────┐    ┌────────────────────┐
│ ChunkOperator │    │ TableExtractOperator│
│ (page+layout) │    │ (跨页合并 + 表头识别)│
└──────┬───────┘    └────────┬───────────┘
       │                     │
       ▼                     ▼
┌──────────────┐    ┌────────────────────┐
│ EmbeddingOp  │    │ FactLedgerLoadOp    │
│ + VectorStore│    │ (指标字典映射)      │
│ + ESFullText │    │ → SQLite {space}_fin│
└──────────────┘    └────────────────────┘
```

**注册为 tagged DAG：** 参考 `api_v1.py:832-900` 的 `chat_with_domain_flow` 路径，用 `TAG_KEY_KNOWLEDGE_FACTORY_DOMAIN_TYPE=FinancialReport` 打标，`KnowledgeSpace.domain_type` 匹配后自动走这条流水线。

### 5.3 PDF 解析器选型

**首选：MinerU 4.0**（`opendatalab/MinerU`）
- 输出契约天然带 `doc:/tier:/page:/block:` URI，直接作为证据链定位符
- OmniDocBench ZH Overall 0.310（Docling 是 0.909，越低越好）
- 支持跨页表格（MinerU-Popo 后处理）
- 保留 bbox 坐标
- 缺点：GPU 依赖较重，CPU 慢；作为服务端服务部署，非 pip 依赖

**次选：PP-StructureV3**（PaddleOCR）
- OmniDocBench ZH 0.206，中文更强
- 有 MCP Server，便于集成
- 缺点：产线稳定性弱于 MinerU

**Fallback：pdfplumber**（仓库现有 `PDFKnowledge`）
- 保留作为无 GPU 环境的降级路径
- 已内置中文年报 header/footer 正则
- 缺点：无 bbox 输出、无跨页表格

**集成方式：** 新建 `packages/dbgpt-ext/src/dbgpt_ext/rag/knowledge/financial_report_pdf.py` 继承 `Knowledge`，通过 `KnowledgeFactory.register` 挂到 `DocumentType.FINANCIAL_REPORT_PDF`；MinerU 作为独立 HTTP 服务，operator 走 `httpx` 调用，超时/失败自动降级到 pdfplumber。

### 5.4 章节路由（应对编号不稳定）

**CSRC 年报十大节标题别名表**（存 `configs/financial_report_sections.yaml`）：

```yaml
sections:
  - canonical: important_notice       # 重要提示
    aliases: [重要提示, 重要风险提示, 重大风险提示]
  - canonical: company_profile         # 公司简介和主要财务指标
    aliases: [公司简介, 公司简介和主要财务指标, 公司基本情况]
  - canonical: mdna                    # 经营情况讨论与分析
    aliases: [经营情况讨论与分析, 管理层讨论与分析, 董事会报告]
  - canonical: corporate_governance
    aliases: [公司治理, 公司治理情况]
  - canonical: significant_events
    aliases: [重要事项, 重大事项]
  - canonical: shareholders
    aliases: [股东情况, 股份变动及股东情况]
  - canonical: directors_supervisors
    aliases: [董事、监事、高级管理人员和员工情况]
  - canonical: financial_report        # 财务报告（含三大表 + 附注）
    aliases: [财务报告, 财务报表, 财务会计报告]
  - canonical: supplementary
    aliases: [备查文件目录, 备查文件]
```

**路由算法：**
1. MinerU 输出标题层级 → 归一化去空白标点
2. 别名表精确匹配 → 命中率约 70%
3. 剩余用 embedding 相似度匹配（阈值 0.85）→ 补 25%
4. 最后 5% 用 fast LLM 分类（一次调用分完所有未命中标题）
5. 全部失败：挂到 `unknown` 节点，仍参与检索

**跨版本兼容：** 2017/2021/2025 三版准则的编号不同，但标题措辞高度稳定，别名表通吃。

### 5.5 表格抽取与 Fact Ledger 落库

**表格抽取：**
- MinerU 已把表格转 markdown + bbox
- 新增 `TableNormalizer`：识别表头（多行合并表头常见）、单位（"元"/"万元"/"亿元"）、期间列（"2019年"/"2018年"/"本年比上年增减"）
- 跨页表格：MinerU-Popo 后处理合并

**Fact Ledger 结构：** 见 §6

**指标映射策略：**
1. **规则表**（覆盖 80%）：一张"表头文本 → 标准指标 code"映射表（存 `configs/financial_metrics_aliases.yaml`），如"营业收入" / "营业总收入" / "主营业务收入" → `revenue`
2. **上下文推断**（15%）：同一表格的相邻行/列可推断（如"分行业营业收入"表下的"医药"行 → `revenue.segment.医药`）
3. **小模型分类**（5%）：剩余的走一次 fast LLM 批量分类

**落库事务性：** 一个表格作为一个事务单元；失败回滚不影响其他表格；所有 fact 带 `source_ref`（`doc:/page/12/block/3/row/5/col/2`）。

### 5.6 分块策略（Chunk）

**混合策略：**
- **正文段落**：按 layout 段落切，`max_chunk_size=800`，overlap=100，metadata 带 `{page, bbox, section_canonical, section_path:["第四节","二、主营业务分析","2、收入与成本"]}`
- **表格**：整表作为一个 chunk（哪怕超 800 字），markdown 形式，metadata 带 `type=table`，`table_id`，`headers`
- **附注条目**：按附注编号切（"（一）货币资金"作为独立 chunk）

**metadata 存储：** 现有 `DocumentChunkEntity.meta_info` 是 String(500)，不够——扩展方案：
1. 新建 `packages/dbgpt-serve/src/dbgpt_serve/rag/models/chunk_evidence_db.py` 存 `chunk_id → {page, bbox_json, section_path_json, table_id}`，主表只存 chunk_id 引用
2. 或者：把 `meta_info` 从 String(500) 迁到 Text（alembic 迁移）

推荐方案 1，向后兼容，不改动主表。

### 5.7 索引策略

- **Vector Store**：page-level dense RAG（业界硬结论 #2），复用现有 chromadb/milvus 后端
- **ES Full-text**：BM25 检索，尤其对表格数字（"2,941,412,770.30" 精确匹配）
- **Section Tree**：SQLite 存 `section_tree.json`（节点：`{id, canonical, title, page_start, page_end, parent_id}`），用于导航式检索
- **不做 GraphRAG/KG-first**（业界硬结论 #2）；TuGraph 只用于「实体-关系」轻量存储（如"公司-子公司"、"客户-销售额"），不作为主检索路径

---

## 6. 语义层 · Fact Ledger + 指标字典

### 6.1 为什么要独立的语义层

现有 DB-GPT 没有语义层——`MetricInfoAgent` 只是 prompt 工程。但财报场景的**核心特征是数字密集 + 跨期可比 + 需要计算**，让 LLM 心算数字 = 幻觉温床（业界硬结论 #3：领域 SFT 把幻觉从 5.4% 拉到 98%）。

**语义层的职责：把「非结构化文本中的数字」升格为「结构化可计算的事实」，让所有数字出口都是 SQL 而非 LLM 生成。**

### 6.2 数据模型

**指标字典（`metric_definitions` 表）：**

```sql
CREATE TABLE metric_definitions (
    code            TEXT PRIMARY KEY,      -- 'revenue', 'net_profit_attr', 'gross_margin'
    name_zh         TEXT NOT NULL,          -- '营业收入'
    name_en         TEXT,                   -- 'Revenue'
    category        TEXT NOT NULL,          -- 'income' | 'balance' | 'cashflow' | 'ratio' | 'segment'
    unit            TEXT NOT NULL,          -- 'CNY' | '%' | 'ratio' | 'count'
    formula         TEXT,                   -- 'gross_margin = (revenue - cogs) / revenue'
    formula_deps    TEXT,                   -- JSON: ['revenue', 'cogs']
    statement       TEXT,                   -- 'income_statement' | 'balance_sheet' | 'cashflow' | 'derived'
    xbrl_tag        TEXT,                   -- 财办会〔2011〕2号 通用分类标准 tag
    aliases         TEXT,                   -- JSON list: ['营业总收入', '主营业务收入']
    description     TEXT,
    higher_is_better INTEGER               -- 1/0/-1(未知)
);
```

**首批预置指标（60 个核心 + 20 个衍生）：**
- 三大表主科目：营业收入、营业成本、销售/管理/研发/财务费用、营业利润、利润总额、所得税、净利润、归母净利润、扣非归母净利润、经营/投资/筹资现金流净额、货币资金、应收账款、存货、固定资产、无形资产、商誉、短期/长期借款、应付账款、预收账款、股本、资本公积、未分配利润、归母净资产、总资产、总负债 …（40+）
- 衍生比率：毛利率、净利率、归母净利率、加权 ROE、总资产收益率 ROA、资产负债率、流动比率、速动比率、应收账款周转率、存货周转率、总资产周转率、经营现金流/净利润、研发费用/营收、销售费用率、管理费用率 …（20+）
- 分板块：`revenue.segment.<name>`、`gross_margin.segment.<name>` …（动态生成）

**事实表（`facts` 表）：**

```sql
CREATE TABLE facts (
    fact_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    space_id        TEXT NOT NULL,           -- knowledge space
    entity_id       TEXT NOT NULL,           -- '海翔药业_002099'
    metric_code     TEXT NOT NULL,           -- FK → metric_definitions
    period_type     TEXT NOT NULL,           -- 'year' | 'quarter' | 'ytd' | 'point_in_time'
    period_value    TEXT NOT NULL,           -- '2019' | '2019Q1' | '2019-12-31'
    segment         TEXT,                    -- NULL(合并) | '医药' | '染料' | '国内' | '国外'
    value           REAL NOT NULL,
    unit            TEXT NOT NULL,           -- 'CNY' | '%' | ...
    yoy_change      REAL,                    -- 若原表已披露则直接存
    source_doc_id   INTEGER NOT NULL,
    source_ref      TEXT NOT NULL,           -- 'doc:/page/7/block/12/row/3/col/2'
    source_text     TEXT NOT NULL,           -- 原句：'营业收入（元） 2,941,412,770.30 ...'
    extraction_rule TEXT,                    -- 'rule:main_accounting_data' | 'model:qwen2.5-14b'
    confidence      REAL,                    -- 0-1
    verified        INTEGER DEFAULT 0,       -- 是否人工/规则复核
    created_at      DATETIME
);

CREATE INDEX idx_facts_lookup ON facts(space_id, entity_id, metric_code, period_value);
CREATE INDEX idx_facts_segment ON facts(space_id, entity_id, metric_code, segment, period_value);
```

**证据锚点表（`evidence_anchors`）：**

```sql
CREATE TABLE evidence_anchors (
    anchor_id       TEXT PRIMARY KEY,        -- 'doc:hisoar2019:page:7:block:12'
    doc_id          INTEGER,
    page            INTEGER,
    bbox_json       TEXT,                    -- [x0,y0,x1,y1]
    text            TEXT,
    section_path    TEXT                     -- JSON: ["第二节","六、主要会计数据和财务指标"]
);
```

### 6.3 指标计算引擎

**原则：所有衍生指标（比率、YoY、CAGR）由引擎计算，绝不让 LLM 心算。**

```python
# packages/dbgpt-core/src/dbgpt/agent/expand/actions/metric_calc_action.py
class MetricCalcEngine:
    def calc(self, metric_code: str, entity: str, period: str,
             segment: Optional[str] = None) -> MetricResult:
        defn = self.dict.get(metric_code)
        if defn.statement == 'derived':
            # 递归取依赖
            inputs = {dep: self.calc(dep, entity, period, segment).value
                      for dep in defn.formula_deps}
            value = eval_formula(defn.formula, inputs)  # 安全的 AST eval
            return MetricResult(
                value=value,
                computation={
                    'formula': defn.formula,
                    'inputs': [
                        {'code': k, 'value': v,
                         'source_ref': self.calc(k, entity, period, segment).source_ref}
                        for k, v in inputs.items()
                    ],
                    'result': value
                }
            )
        else:
            row = self.db.query_one(
                "SELECT value, source_ref, source_text FROM facts "
                "WHERE entity_id=? AND metric_code=? AND period_value=? AND segment IS ?",
                (entity, metric_code, period, segment))
            if not row:
                return MetricResult(value=None, abstain_reason='fact_not_found')
            return MetricResult(value=row.value, source_ref=row.source_ref,
                                source_text=row.source_text)
```

### 6.4 NL2Metric 映射

用户问"海翔药业 2019 年的毛利率是多少"→

1. 实体识别：`entity = "海翔药业_002099"`（用知识库空间绑定 + NER 兜底）
2. 时间识别：`period = "2019"`
3. 指标识别：`metric_code = "gross_margin"`（走向量匹配 `metric_definitions.aliases`）
4. 段识别：`segment = NULL`（合并报表）
5. 计算：`MetricCalcEngine.calc("gross_margin", ...)` 递归展开为 `(revenue - cogs) / revenue`，各取数走 SQL
6. 组装答案 + 计算过程 + 数据源 ref

**关键：整个过程 LLM 只做「文本 → 结构化查询参数」，不做数字运算。**

---

## 7. L2 推理层 · Router + ReAct + Verifier

### 7.1 工作流 vs ReAct Agent 决策矩阵

**这是本方案最重要的架构决策，逐项论证：**

| 用户意图 | 走工作流还是 ReAct | 理由 |
|---|---|---|
| 事实查询（"2019 年营收多少"） | **工作流**（NL2Metric → SQL → 模板回复） | 单跳、确定性、无需推理；ReAct 反而增加延迟和幻觉风险 |
| 指标计算（"毛利率是多少"） | **工作流**（同上，走 MetricCalcEngine） | 同上 |
| 归因分析（"为什么经营现金流下滑"） | **ReAct Agent** | 需要多跳：查现金流表 → 查应收账款 → 查存货 → 综合；工具选择依赖上下文 |
| 跨期对比（"近三年营收趋势"） | **工作流**（骨架固定：取数 → 图表 → 模板解读）+ ReAct 生成解读段 | 取数和图表是确定的，解读需要推理 |
| 跨公司对比（"海翔 vs 华海"） | **ReAct Agent**（工具：`cross_entity_query`） | 需要动态选择对比维度和指标 |
| 综合评估（"这家公司值得投资吗"） | **ReAct Agent** + 强 Verifier | 开放性最高，需多轮工具调用 |
| 报告生成 | **工作流骨架 + 段内 ReAct**（TaskFlow DSL 的 `report` 节点已就位） | 结构固定，段落内容动态 |
| 异常检测 | **工作流**（预设 20 条红旗规则批量跑） | 规则化，无需推理 |
| 闲聊/元问题（"你能做什么"） | **工作流**（模板回复） | 无需检索 |

**总结："骨架是工作流，血肉是 ReAct"。** Router 决定骨架，骨架内某些节点跑 ReAct。

### 7.2 Router 设计

**位置：** `packages/dbgpt-app/src/dbgpt_app/openapi/api_v1/financial_report_api.py`（新建），复用 `agentic_data_api.py` 的 SSE 事件框架。

**实现：**
- Fast LLM（qwen-turbo/glm-4-flash 级别），单次调用 <200ms
- Prompt：给 9 类意图 + few-shot 示例，输出 `{intent, entities, periods, metrics, segments}` JSON
- 失败降级：默认走 ReAct（保守策略）

**Router 输出契约：**

```json
{
  "intent": "attribution_analysis",
  "confidence": 0.92,
  "entities": [{"code": "002099", "name": "海翔药业", "role": "primary"}],
  "periods": [{"value": "2019", "type": "year"}],
  "metrics": [
    {"code": "operating_cashflow", "role": "target"},
    {"code": "net_profit_attr", "role": "context"}
  ],
  "segments": [],
  "retrieval_hints": ["现金流量表", "应收账款", "存货"],
  "suggested_tools": ["fact_ledger_query", "section_retrieve", "chart_render"]
}
```

### 7.3 ReAct Agent 工具集

复用现有 `ToolCallingReActAgent`（`packages/dbgpt-core/src/dbgpt/agent/expand/tool_calling_agent.py:318`），新增以下 6 个工具（`packages/dbgpt-app/src/dbgpt_app/openapi/api_v1/tools/financial_report_tools.py`）：

| 工具名 | 输入 | 输出 | 用途 |
|---|---|---|---|
| `fact_ledger_query` | `{entity, metric_code, period, segment?}` | `{value, unit, source_ref, source_text}` 或 `{abstain: true}` | 所有数字查询的唯一入口 |
| `metric_calc` | `{metric_code, entity, period, segment?}` | 同上 + `computation_trace` | 衍生指标计算（带公式展开） |
| `section_retrieve` | `{doc_id, section_canonical, sub_path?, query?}` | 段落 chunks + bbox | 章节内精确检索（避开 dense RAG 的 62% miss） |
| `table_lookup` | `{doc_id, table_hint}` | markdown 表格 + 表头 + bbox | 定位特定表格（如"应收账款账龄"） |
| `cross_year_compare` | `{entity, metric_codes[], periods[]}` | 对比矩阵 + 每格 source_ref | 跨期对比 |
| `chart_render` | `{chart_type, data, title, source_refs[]}` | vis-chart 标签 | 图表产物 |

**同时复用现有工具：** `code_interpreter`（Python 沙箱，用于复杂计算）、`knowledge_retrieve`（兜底 dense RAG）、`question`（human-in-loop）、`todowrite`（计划追踪）。

### 7.4 ReAct 内核：Expansion / Solving / Evaluation

借鉴 FinLongDocAgent：

```
Expansion（扩展）：
  - Router 结果 + 用户 query → 生成子问题列表
  - 例："为什么经营现金流下滑" →
    ["2019 vs 2018 经营现金流净额分别是多少",
     "现金流量表补充资料中哪些科目变动最大",
     "应收账款 2019 vs 2018 变动",
     "存货 2019 vs 2018 变动",
     "应付账款 2019 vs 2018 变动"]
  - 用 todowrite 工具落地成 plan（前端 timelineSlot 显示）

Solving（求解）：
  - 逐个子问题调用工具（fact_ledger_query / section_retrieve / ...）
  - 每个子问题结果带 source_ref
  - 流式推 step.chunk 事件

Evaluation（评估）：
  - 汇总子答案 → Verifier 复核 → 生成最终答案
  - 若 Verifier 拒答，返回 abstain + 原因
```

### 7.5 Verifier（对抗式复核器）

**双层：**

**Layer 1 · Rule-based（快，覆盖 80%）：**
```python
def rule_verify(claim: str, evidence: EvidenceBundle) -> Verdict:
    # 抽出 claim 中的所有数字
    numbers = extract_numbers(claim)  # 用正则 + NER
    for n in numbers:
        # 每个数字必须能匹配到 evidence.facts 或 evidence.pdf_spans 里的一个数字
        if not any(matches(n, f.value) or matches(n, s.text)
                   for f in evidence.facts for s in evidence.pdf_spans):
            return Verdict.REVISE, f"数字 {n} 未在证据中找到"
    return Verdict.PASS
```

**Layer 2 · LLM Auditor（慢，覆盖剩余 20%）：**
- Prompt：给 claim + evidence bundle，问"证据是否充分支撑结论？如果不充分，指出具体缺什么"
- 输出：`{verdict: pass|revise|abstain, reason, missing_evidence[]}`
- 未来可训练一个 3B 小模型（VeNRA 路线）替代

**Verifier 失败策略：**
- `pass` → 直接输出
- `revise` → 回到 ReAct，追加提示"以下断言缺证据，请补检索或删除"
- `abstain` → 输出"未在报告中找到充分证据"，附最近似的候选（Rogo 的 refuse-without-source 范式）

**Verifier 最大重试次数：2**（防止死循环）

### 7.6 SSE 事件契约

**复用现有事件（`agentic_data_api.py:1505-1542`）：** `step.start / step.output / step.chunk / step.done / step.meta / final.chunk / plan.update / task.preview / context.status`

**新增财报专属事件：**

| 事件 | payload | 用途 |
|---|---|---|
| `evidence.fact` | `{fact_id, metric_code, period, value, unit, source_ref}` | 数字证据 chip |
| `evidence.span` | `{doc_id, page, bbox, text}` | PDF 原文证据 |
| `evidence.computation` | `{formula, inputs[], steps[], result}` | 计算过程展开 |
| `evidence.verifier` | `{verdict, reason, missing_evidence[]}` | 复核结果 |
| `evidence.abstain` | `{reason, candidates[]}` | 拒答 |

**前端 `react-sse-parser.ts` 白名单必须同步扩展**（记忆：新事件类型不加白名单会被静默丢弃）。

---

## 8. 证据链展示 · 四级下钻契约

### 8.1 数据契约

```typescript
// web/types/financial-report-evidence.ts
export interface EvidenceBundle {
  claim_id: string;
  claim_text: string;
  evidences: Evidence[];
  computation?: ComputationTrace;
  verifier: { verdict: 'pass' | 'revise' | 'abstain'; reason?: string };
  confidence: 'high' | 'medium' | 'low';
}

export type Evidence =
  | FactEvidence
  | SpanEvidence
  | TableEvidence
  | CrossDocEvidence;

export interface FactEvidence {
  type: 'fact';
  fact_id: number;
  metric: { code: string; name_zh: string; unit: string };
  entity: { id: string; name: string };
  period: { type: string; value: string };
  segment?: string;
  value: number;
  source_ref: string;   // 'doc:hisoar2019:page:7:block:12:row:3:col:2'
  source_text: string;  // 原句
  pdf_locator: {
    doc_id: string;
    page: number;
    bbox: [number, number, number, number];
  };
}

export interface SpanEvidence {
  type: 'span';
  doc_id: string;
  page: number;
  bbox: [number, number, number, number];
  text: string;
  section_path: string[];
}

export interface TableEvidence {
  type: 'table';
  doc_id: string;
  page: number;
  bbox: [number, number, number, number];
  table_id: string;
  markdown: string;
  highlight_cells?: Array<[number, number]>;  // [row, col]
}

export interface ComputationTrace {
  formula: string;                    // '(revenue - cogs) / revenue'
  inputs: Array<{
    code: string;
    name_zh: string;
    value: number;
    unit: string;
    source_ref: string;
  }>;
  steps: Array<{ expr: string; result: number }>;
  result: number;
}
```

### 8.2 UI 布局

**主界面三栏（复用现有 `ManusLeftPanel` + 中央对话 + `ArtifactRail` 右侧查看器）：**

```
┌──────────────────┬─────────────────────────────────┬──────────────────────┐
│ 左：意图 & 计划   │ 中：对话流                       │ 右：Evidence Viewer  │
│                  │                                  │  (Tab 切换)          │
│ ▸ 意图行         │ 用户: 为什么经营现金流下滑 22%   │  [PDF] [Ledger]      │
│   "归因分析"     │                                  │  [Tree] [Trace]      │
│                  │ Agent (streaming):               │                      │
│ ▸ 计划树         │ 海翔药业 2019 年经营现金流净额    │ ┌──────────────────┐ │
│   ✓ 查现金流表   │ 6.12 亿 [P.7 · ①]，同比下降       │ │ PDF Previewer    │ │
│   ✓ 查应收账款   │ 22.62%。主要原因：              │ │ (pdf.js)         │ │
│   ● 查存货       │                                  │ │  ┌────────────┐  │ │
│   ○ 综合分析     │ 1. 应收账款大幅增加 3.85 亿      │ │  │ 高亮 bbox  │  │ │
│                  │    [P.112 · ②]                  │ │  │ (黄色蒙版) │  │ │
│ ▸ 工具调用       │ 2. 存货增加 1.20 亿 [P.98 · ③]  │ │  └────────────┘  │ │
│   fact_ledger×3 │ 3. 但净利润增长 27.4% [P.7 · ④]  │ │  页码: 7 / 204   │ │
│   section_retr×1│    → 利润含金量下降              │ └──────────────────┘ │
│   chart_render×1│                                  │                      │
│                  │ [展开计算过程] [查看现金流量表]  │ 点击 ① chip 自动跳转  │
│ ▸ 复核状态       │                                  │ 并高亮              │
│   ✓ Rule: pass  │ 🚩 Verifier: PASS               │                      │
│   ✓ LLM: pass   │                                  │                      │
└──────────────────┴─────────────────────────────────┴──────────────────────┘
```

**Evidence Chip 视觉规范：**
- `[P.7 · ①]` 形式，右上角小圆圈数字对应右侧 Evidence 列表编号
- 颜色编码：绿=Fact Ledger 精确匹配、蓝=PDF 原文引用、橙=计算得出、灰=兜底检索
- 悬停显示 tooltip：原句摘要 + 置信度
- 点击：右侧 Viewer 切换到对应 tab 并高亮

**PDF Viewer 关键实现：**
- `pdf.js` 渲染（web/public/pdfjs/，Next.js 静态资源）
- bbox 归一化坐标（相对页面 0-1）→ 转像素坐标
- 高亮蒙版：绝对定位 div + `background: rgba(255,215,0,0.35)` + 圆角
- 支持"上一个/下一个"证据跳转

**Computation Trace 面板：**
```
毛利率 = (营业收入 - 营业成本) / 营业收入

  营业收入        2,941,412,770.30 元     [P.7 · 主要会计数据]
- 营业成本        1,447,159,361.03 元     [P.85 · 合并利润表]
─────────────────────────────────────
= 毛利            1,494,253,409.27 元

÷ 营业收入        2,941,412,770.30 元
─────────────────────────────────────
= 毛利率          50.80%

数据源快照：2020-01-23 披露的 2019 年报（未经追溯调整）
```

---

## 9. 复用 DB-GPT 现有资产清单

| 现有资产 | 位置 | 复用方式 |
|---|---|---|
| `DOMAIN_TYPE_FINANCIAL_REPORT` | `configs/__init__.py:16` | 直接用 |
| `chat_with_domain_flow` 路由 | `api_v1.py:832-900` | 直接用 |
| `DomainKnowledgeIndexFactory` | `dbgpt_serve/rag/domain/factory.py:11` | 新建 `FinancialReportIndex` 注册 |
| `PDFKnowledge` (pdfplumber) | `dbgpt_ext/rag/knowledge/pdf.py` | Fallback；新建 MinerU 版本 |
| AWEL operators (Chunk/Embedding/VectorStorage/FullTextStorage) | `dbgpt_ext/rag/operators/` | 直接接入 DAG |
| `KnowledgeSpaceRetriever` (semantic/keyword/hybrid) | `dbgpt_serve/rag/retriever/knowledge_space.py` | 直接用 |
| Reranker (`CrossEncoderRerankEmbeddings`, `QwenRerankEmbeddings`) | `dbgpt_core/rag/embedding/rerank.py` | 直接用 |
| `ToolCallingReActAgent` | `dbgpt_core/agent/expand/tool_calling_agent.py:318` | 直接扩展工具集 |
| ReAct 工具（`code_interpreter`, `sql_query`, `knowledge_retrieve`, `question`, `todowrite`） | `dbgpt_app/openapi/api_v1/tools/` | 直接接入 |
| `agentic_data_api` SSE 端点 | `dbgpt_app/openapi/api_v1/agentic_data_api.py:4160` | 新建平行端点 `/v1/chat/financial-report` |
| TaskFlow DSL (`report`, `db_query`, `ai_analysis`, `visualize` 节点) | `dbgpt_serve/flow/taskflow/nodes.py` | 报告生成流用 TaskFlow 编排 |
| Vis tags (`vis-chart`, `vis-dashboard`, `vis-report-generation`, `vis-anomaly-detection`) | `dbgpt_core/vis/tags/` | 直接用 |
| AntV G2 / S2 / G6 / AVA / GPT-Vis | `web/package.json:30-36` | S2 做三大表 pivot，G2 做趋势图 |
| `ManusLeftPanel.timelineSlot` | `web/new-components/chat/content/ManusLeftPanel.tsx` | 意图/计划/工具行渲染 |
| `ArtifactRail` + 右侧查看器 | `web/new-components/chat/content/ArtifactRail.tsx` | Evidence Viewer 承载 |
| `InlineCitation` / `ReferencesContent` | `web/components/chat/chat-content/` | 升级支持 bbox 跳转 |
| Finance agents (`anomaly_detection`, `volatility_analysis`, `report_generation`, `metric_info`) | `dbgpt_serve/agent/agents/expand/` | 参考实现，重构接入新架构 |

**新增代码量估算：** 后端约 6-8k 行（含 MinerU 集成、Fact Ledger、指标字典、6 个新工具、Verifier、SSE 事件），前端约 4-5k 行（Evidence Viewer、PDF Previewer、Computation Trace、Matrix View），配置约 1k 行（指标字典、章节别名表）。

---

## 10. 分阶段落地

### P0 · 打通闭环（2 周）
**目标：** 上传海翔药业 PDF → 能问"2019 年营收多少"→ 返回带段落级引用的答案

- 复用现有 `PDFKnowledge`（不换 MinerU），加章节路由（别名表）
- 建 Fact Ledger schema，指标字典首批 20 个核心指标，规则表映射
- 新建 `financial_report_api.py`，Router 只做 3 类意图（事实查询/闲聊/其他）
- Deterministic path 走通（NL2Metric → SQL → 模板回复）
- 前端：Evidence Viewer 简版（段落级引用，不做 bbox 高亮）
- **验收：** 海翔药业 2019 年报，10 个事实类问题准确率 ≥ 90%

### P1 · 证据链升级（3 周）
**目标：** 四级证据链下钻 + PDF bbox 高亮 + 计算过程展开

- 接入 MinerU 服务，替换 pdfplumber（保留 fallback）
- 扩展 `chunk_evidence_db` 存 bbox/section_path
- 指标字典扩到 60 个 + 20 个衍生指标；上线 `MetricCalcEngine`
- SSE 新增 `evidence.*` 事件；前端 parser 白名单同步
- 前端 PDF Previewer（pdf.js + bbox 蒙版）、Computation Trace 面板、Fact Ledger Inspector
- **验收：** 用户点击任一数字 chip 都能在 500ms 内看到 PDF 高亮

### P2 · ReAct + Verifier（3 周）
**目标：** 归因分析、跨期对比、综合评估能力

- 实现 6 个新工具（fact_ledger_query, metric_calc, section_retrieve, table_lookup, cross_year_compare, chart_render）
- Router 扩到 9 类意图；ReAct 内核（Expansion/Solving/Evaluation）
- Verifier 双层（Rule + LLM）；abstention 机制
- 前端：计划树、工具调用行、复核状态显示
- **验收：** FinGAIA / FinanceBench 中文子集抽取 50 题，端到端准确率 ≥ 75%，幻觉率 ≤ 5%

### P3 · 报告生成 + Matrix 对比（2 周）
**目标：** 一键生成解读报告；Hebbia 风格跨期/跨公司对比

- TaskFlow 模板 `financial-report-analysis-template.json`（骨架固定，段内 ReAct）
- vis-report-generation 升级，支持段落级引用 + 导出 md/docx
- Matrix View（AntV S2 pivot 复用）
- **验收：** 海翔药业 2019 年报生成 1500 字解读报告，人工评审 ≥ 4/5

### P4 · 生产化（2 周）
**目标：** 批量处理、监控、评测

- 批量上传 + 后台异步解析（celery/arq）
- 观测：Prometheus 指标（解析耗时、Fact Ledger 覆盖率、Verifier 通过率、abstention 率）
- 评测集：自建 `FinReport-CN-Eval`（100 题，覆盖 6 类意图），CI 集成
- 用户反馈：答案点赞/踩，用于持续调优
- **验收：** 单份 200 页年报端到端解析 ≤ 5 分钟，问答 P95 ≤ 8s

**总工期估算：** 12 周（3 个月）到生产可用。

---

## 11. 关键失败模式与防御

| 失败模式 | 表现 | 防御 |
|---|---|---|
| **表格跨页断裂** | 现金流量表跨 3 页，抽取后行错位 | MinerU-Popo 跨页合并；表格拼接后做「表头一致性 + 行数合理性」校验 |
| **数字单位混淆** | 表头写"万元"但数据是"元"，或不同表混用 | 每个 fact 强制带 `unit`；表格抽取时识别"单位：xx"标注；跨表计算前统一转换 |
| **章节编号不稳定** | 财务报告在不同公司是第八/十/十二节 | 按标题路由（§5.4），别名表 + embedding + fast LLM 三级兜底 |
| **数字幻觉** | LLM 心算"约 30 亿"，实际 29.41 亿 | Fact Ledger + Verifier Rule Layer + 数字必须精确匹配 source_text |
| **检索未命中（62%）** | 用户问"前五大客户集中度"，dense RAG 找不到附注 | 多路：Fact Ledger → Section Tree 导航 → BM25 全文 → dense RAG；Section Tree 尤其对附注有效 |
| **管理层叙事与数字矛盾** | MD&A 说"营收大幅增长"，实际只增 8% | Verifier 加"叙事-数字一致性"检查（LLM Auditor 层） |
| **非经常性损益迷惑** | 归母净利润高增长但主要靠政府补助 | Fact Ledger 强制同时抽 `net_profit_attr` 和 `net_profit_attr_deducted`；差异 >10% 时自动挂红旗 |
| **追溯调整** | 上年数被追溯调整，直接对比原披露会错 | 抽 `restated_flag`；对比时优先用当年报告中的上年数（已追溯） |
| **多准则差异** | A+H 股双上市，境内外准则净利润不同 | Fact 表加 `standard` 字段（CAS/IFRS）；用户询问时明确 |
| **PDF 扫描件（无文本层）** | 老年报只有扫描图片 | P0-P3 拒绝，明确告知用户；P4 视需求接 OCR（PaddleOCR） |
| **恶意/敏感问题** | 用户问"帮我做假账" | Router 加安全分类；命中直接拒答 |

---

## 12. 评测与验收

### 12.1 评测集

**自建 `FinReport-CN-Eval`（内部）：**
- 100 题，覆盖 6 类意图（事实查询 30 / 指标计算 20 / 归因 15 / 对比 15 / 综合评估 10 / 报告 10）
- 每题带标准答案 + 证据锚点 + 评分维度（数字准确性、证据充分性、表达清晰度）
- 数据源：`docker/examples/fin_report/pdf/` 5 份年报 + 补充 5 份不同行业

**公开评测集（对齐）：**
- FinGAIA（arxiv 2507.17186，中文金融 agent benchmark）
- FinanceBench（arxiv 2311.11944，英文但方法论通用）
- FinEval（arxiv 2308.09975，中文金融知识）

### 12.2 关键指标

| 指标 | 目标 | 测量方式 |
|---|---|---|
| 数字准确率 | ≥ 98% | Fact Ledger 命中且与原文完全一致 |
| 幻觉率 | ≤ 2% | Verifier REVISE 次数 / 总次数 |
| 证据充分率 | ≥ 95% | 每个 claim 至少 1 条 evidence |
| 检索命中率 | ≥ 85% | Router 分诊后 top-3 检索包含正确证据 |
| Abstention 合理率 | ≥ 90% | 人工评审拒答是否合理 |
| 端到端延迟 P95 | ≤ 8s | 事实类 ≤ 3s，归因类 ≤ 15s |
| PDF 解析耗时 P95 | ≤ 5min/200页 | MinerU 服务侧监控 |

### 12.3 灰度策略

- 内部 alpha：产品/研发团队 20 人 × 2 周
- 封闭 beta：邀请 50 名分析师 × 4 周，收集 bad case
- 公开 GA：v1.0 发布，配合 5 份样例年报 demo

---

## 13. 风险与开放问题

1. **MinerU 部署成本**：需要 GPU 才能达到生产延迟；无 GPU 环境退化到 pdfplumber 会失去 bbox。**待评估：** CPU 版 MinerU 延迟能否接受？或考虑 PP-StructureV3 CPU 版本。
2. **指标字典覆盖率**：60 个核心指标能覆盖多少用户问题？**待验证：** P0 阶段收集 100 个真实 query，统计未命中比例。
3. **附注表格复杂度**：应收账款账龄、金融工具公允价值等附注表格结构复杂，Fact Ledger 建模是否够用？**待设计：** 附注实体的独立建模（可能引入 `note_entities` 表）。
4. **跨公司对比的实体对齐**：不同公司的"医药板块"定义不同，如何可比？**待设计：** 引入行业分类标准（申万/中信）+ 板块映射规则。
5. **多期报告的时间线**：同一公司多年年报并存时，追溯调整如何处理？**待设计：** Fact 表加 `as_of_doc_id`，查询时明确"以哪份报告为准"。
6. **实时数据接入**：用户可能问"最新股价"、"同行业对比"，超出年报范围。**待定：** P4+ 决策是否接入 Wind/Choice/东财数据源。

---

## 附录 A · 业界调研摘要

### A.1 国内产品

- **蚂蚁支小宝/蚂小财**：百灵大模型 + Finix 金融大模型，72 技能，支付宝折叠入口。偏 C 端理财助手，非专业投研
- **同花顺问财 HithinkGPT**：日活 500 万+，17 考试体系 + 15 业务领域 + 50+ 技能模块。NL2SQL 为主，工作流固化
- **Wind Alice**：27 个 agent 组成"全建制金融团队"，一句话做投研。多智能体协作，重工作流编排
- **度小满轩辕 FinX1**：开源金融推理大模型，CoT + 过程奖励 + RL，FinanceIQ 榜首。**本方案不采用 SFT 路线（业界硬结论 #3）**
- **通义点金**：阿里云金融级通用智能体，129 技能，三重合规防线，全链路审计追溯，弹性沙箱，AgentScope 金融版。RAG+Agent 三层，25TB 数据
- **东方财富妙想**：29 个炒股 Skills，偏 C 端
- **恒生 LightGPT / WarrenQ**：3500 万篇文本 + 100TB 结构化，对话检索/AI 解读/AI 写作，**逻辑推理过程展示**（借鉴）

### A.2 海外产品

- **Rogo AI**：投行首选，plan-and-execute + **per-clause citation + refuse-without-source**（本方案 Verifier 直接借鉴）
- **AlphaSense**：估值 40 亿美元，500M 文档，五大产品层，Gartner MQ 领导者
- **Hebbia Matrix**：a16z 领投 1 亿美金，**Matrix View 跨期对比 UX**（本方案场景 B 借鉴），分布式编排引擎，无限上下文
- **Kensho (S&P Global)**：S&P AI Benchmarks 三大评测轴，仅提交输出的安全流程
- **BloombergGPT**：500 亿参数金融专用大模型（arxiv 2303.17564），2023 年发布后进展有限；本方案不走大模型路线
- **Perplexity Finance**：对话式，通用能力+金融数据源
- **PageIndex / Mafin 2.5**：**Vectorless 检索**，树状推理导航，句级引用，可拒答，FinanceBench 98.7%（本方案 Section Tree 借鉴）

### A.3 关键论文

- **FinLongDocQA / FinLongDocAgent** (arxiv 2604.03664)：Document-Level Numerical Reasoning across Tables。**Expansion/Solving/Evaluation 三阶段循环**（本方案 ReAct 内核借鉴）。**62% 失败是检索未命中**、**GraphRAG 退化 2.7×** 两条硬结论出处
- **VeNRA** (arxiv 2603.04663)：Neuro-Symbolic Financial Reasoning via Deterministic Fact Ledgers。**对抗式 3B auditor**（本方案 Verifier Layer 2 借鉴）
- **When Financial Fine-tuning Fails** (arxiv 2609.04806)：Three-Level Detectability of Numerical Hallucination。**领域 SFT 把幻觉从 5.4% 拉到 98%**（本方案不走 SFT 路线的依据）
- **FinReporting** (arxiv 2604.05966)：Agentic Workflow for Cross-Jurisdiction Financial Disclosures
- **FinRobot** (arxiv 2405.14767)：AI Agent for Equity Research and Valuation，开源
- **TableGPT2** (arxiv 2411.02059)：Large Multimodal Model with Tabular Data Integration
- **MinerU** (arxiv 2409.18839) + **MinerU-Popo** (arxiv 2605.24973)：跨页表格/标题层级重建
- **Docling** (arxiv 2408.09869)：中文能力弱，不采用
- **agentUniverse** (蚂蚁开源)：PEER + DOE 模式，Financial Event Analysis 示例

### A.4 监管与标准

- **证监会公告〔2017〕17 号**：《公开发行证券的公司信息披露内容与格式准则第 2 号——年度报告的内容与格式》（2017 年修订，**适用于 2019 年报**）
- **证监会公告〔2021〕15 号**：同上 2021 年修订
- **证监会公告〔2025〕3 号**：同上 2025 年修订（最新）
- **财办会〔2011〕2 号**：企业会计准则通用分类标准（XBRL）实施通知

**关键：准则规定章节骨架法定但编号不稳定**（不同发行人编号可能差 1-4 节，如英洛华"第八节可转债"→"第十二节财务报告"）；本方案 §5.4 章节路由按标题不按序号即源于此。

---

## 附录 B · 关键文件与扩展点清单

**新建：**
- `packages/dbgpt-ext/src/dbgpt_ext/rag/knowledge/financial_report_pdf.py` — MinerU 版 Knowledge
- `packages/dbgpt-ext/src/dbgpt_ext/rag/operators/financial_report/` — AWEL operators (parse/section_route/table_extract/fact_load)
- `packages/dbgpt-serve/src/dbgpt_serve/rag/domain/financial_report_index.py` — DomainKnowledgeIndex 实现
- `packages/dbgpt-serve/src/dbgpt_serve/financial_report/` — Fact Ledger models + service + api
- `packages/dbgpt-core/src/dbgpt/agent/expand/actions/metric_calc_action.py` — 指标计算引擎
- `packages/dbgpt-app/src/dbgpt_app/openapi/api_v1/tools/financial_report_tools.py` — 6 个 ReAct 工具
- `packages/dbgpt-app/src/dbgpt_app/openapi/api_v1/financial_report_api.py` — SSE 端点
- `packages/dbgpt-app/src/dbgpt_app/openapi/api_v1/subagent/financial_report_verifier.py` — Verifier
- `configs/financial_metrics_aliases.yaml` — 指标字典
- `configs/financial_report_sections.yaml` — 章节别名表
- `web/types/financial-report-evidence.ts` — 证据链类型
- `web/new-components/financial-report/` — Evidence Viewer / PDF Previewer / Computation Trace / Matrix View
- `web/components/chat/chat-content/evidence-chip.tsx` — 证据 chip
- `docs/design/financial-report-analysis-mockup.html` — 高保真 mockup

**修改：**
- `packages/dbgpt-serve/src/dbgpt_serve/rag/models/chunk_db.py` — 扩展 meta_info（或新建 chunk_evidence_db）
- `packages/dbgpt-app/src/dbgpt_app/openapi/api_v1/api_v1.py` — 路由注册
- `web/lib/react-sse-parser.ts` — 事件白名单加 `evidence.*`
- `web/new-components/chat/content/ManusLeftPanel.tsx` — timelineSlot 加意图/计划/工具行渲染
- `web/new-components/chat/content/ArtifactRail.tsx` — Evidence Viewer 承载

**直接复用：** 见 §9 清单。

---

## 附录 C · 与仓库现有约定的对齐

- **提交拆分**（对齐用户习惯）：按工作线拆 6 个独立提交
  1. `feat(financial-report): ingestion pipeline with MinerU + Fact Ledger schema`
  2. `feat(financial-report): metric dictionary and calc engine`
  3. `feat(financial-report): router + ReAct tools + Verifier`
  4. `feat(financial-report): SSE endpoint and event contract`
  5. `feat(financial-report): frontend Evidence Viewer and PDF Previewer`
  6. `feat(financial-report): report generation workflow and Matrix View`
- **mockup 先行**：本文档配套的 `financial-report-analysis-mockup.html` 承载真实海翔药业 2019 数据 + 证据链交互 + 设计标注，用户评审通过后再进入编码
- **不混合提交**：数据文件、临时脚本不入库
- **对齐现有 UI 范式**（记忆条目）：右栏 = 上下文查看器默认收起、仅产物预览滑出；timelineSlot = 意图行 + 分组工具行 + 产物卡；流尾全局状态线

---

**下一步：**
1. 用户评审本方案稿 + HTML mockup，对齐视觉与交互
2. 确认后按 §10 分阶段落地，P0 优先跑通闭环
3. 每阶段结束跑评测集，指标达标进入下一阶段
