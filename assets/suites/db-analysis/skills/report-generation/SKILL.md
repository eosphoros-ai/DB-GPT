---
name: report-generation
name_zh: 报告生成
name_en: Report Generation
description_en: Assemble query results, charts, attribution findings, and source references into a structured analysis report for HTML or PDF export.
command: /report
user-invocable: true
description: 智能分析场景的图文报告生成技能。把多步取数结果、图表与归因结论提炼成结构化图文分析报告，按固定章节骨架装配（摘要/数据集与口径说明/多维图表分析/归因结论/建议/引用溯源附录），生成引用 chips（指标@版本、表与 join、SQL 步骤、命中样例），并通过 report_export 导出 HTML（可分享）或 PDF（可归档）。当用户要求"出报告/生成报告/图文报告/周报月报/经营分析/导出 HTML 或 PDF/分享报告/报告加引用/报告结论提炼/把分析汇总成文档"，或需要把已有图表与结论收口成可交付物时使用。触发词：报告、出报告、图文报告、周报、月报、经营分析、导出、HTML、PDF、分享、引用溯源、结论提炼、report。
---

# 图文报告生成（Report Generation）

## 必需参考

按[报告模板](../../templates/report-template.md)组织正文，并遵循
[分析 SOP](../../prompts/analysis-playbook.md)中的口径、引用与交付要求。

## 技能目标

把一轮分析（数据集 + 多步取数 + 图表 + 归因结论）收口成**一份可直接分享、可溯源、可复现**的图文分析报告，产出 `report` 产物卡。

报告的三条质量标准：

1. **可决策**：摘要 5 行内讲清"发生了什么、为什么、该做什么"，业务负责人不读正文也能行动；
2. **可溯源**：每个数字、每张图、每条结论都挂引用 chips（指标@版本 / 表与 join / SQL 步骤号 / 命中的 verified 样例 id / 规则），读者点进去能看到权威定义与执行过的 SQL；
3. **可复现**：写明数据集范围、pin 的指标版本、默认过滤、时间粒度、对比窗口、执行库（只读从库）、数据截止时间与生成时间；降级或口径例外必须显著标注。

章节骨架固定，参考 `templates/report-template.md`；不自造结构，不删减"数据集与口径说明"和"引用溯源附录"两章。

## 核心工作流程

1. **盘点素材（装配前的清单核对）**
   - 数据集：`dataset_id`、表清单、join 路径、默认过滤、粒度、可见范围（行级权限）。
   - 口径：本轮 pin 的全部指标@版本（如 `valid_gmv@v2`、`paid_order_cnt@v1`、`aov@v1`、`refund_rate@v1`）。
   - 图表：`chart_id` 列表 + 每图标题/单位/注脚。
   - 数据：每步 `sql_execute` 的关键数字与步骤号。
   - 结论：归因结论卡（主因/次因/长尾、置信度、待验证假设、建议动作）。
   - 缺失项处理：无数据集或无口径信息 → 先补齐（走 `dataset-scoping`）或在报告中显式标注"口径未确认"；无图表 → 至少补一张核心趋势/贡献度图。

2. **提炼摘要（先写摘要，再回填正文）**
   - 5 行以内，每行一个要点：① 核心结论（含数字与幅度）② 主因（含量化贡献度）③ 影响范围与异动起点 ④ 口径与置信度 ⑤ 首要建议动作。
   - 摘要里的每个数字必须与正文一致（同源同版本），不得出现正文未支撑的数字。

3. **装配章节（按模板骨架填充 `sections`）**
   - `summary`：摘要（步骤 2 产出）。
   - `dataset_and_semantics`：数据集与口径说明（表清单、join、默认过滤、粒度、指标@版本、对比窗口、数据截止时间、降级/口径例外标注）。
   - `multi_dim_charts`：多维度图表分析。每张图一小节，结构为「结论式小标题 → 图（绑定 `chart_id`）→ 2~4 句解读 → 口径注脚」；图的顺序按"总量趋势 → 结构拆解 → 下钻 → 量价/异动"的叙事逻辑排列。
   - `attribution`：归因结论（主因/次因/长尾 + 闭合校验说明 + 置信度 + 待验证假设）。
   - `recommendations`：建议（谁做/做什么/看哪个指标/多久复盘，最多 5 条，按优先级排序）。
   - `citations`：引用溯源附录（指标版本表、表与 join 清单、SQL 步骤索引、命中样例 id、规则与权限说明）。

4. **生成引用 chips**
   - `citations` 入参按三类必备组织：
     - **指标版本**：`{type: "metric", ref: "valid_gmv", version: "v2", layer: "mysql_prod"}`
     - **数据来源**：`{type: "table", ref: "ods_order_main", joins: ["ods_order_main.order_id=ods_order_item.order_id (1:N)"]}`、`{type: "rule", ref: "readonly_replica + row_level_scope"}`
     - **执行痕迹**：`{type: "step", ref: "step3", sql_summary: "按品类汇总 valid_gmv 差额 Top10"}`、`{type: "sample", ref: "va-001-eastchina-sales-decline"}`
   - 每条结论/每张图至少绑定 1 个指标版本 chip + 1 个执行痕迹 chip。

5. **导出报告**
   - HTML（默认，可分享）：`report_export(title="<范围+主题+期间>", sections=[...], charts=["ch-01","ch-02",...], citations=[...], format=["html"], template="templates/report-template.md")`
     → 返回 `report` 产物卡 + 分享链接。
   - PDF（归档/外发）：`format=["html","pdf"]` 或单独 `format=["pdf"]`；PDF 前确认图表已在 HTML 中正常渲染（PDF 由核心导出器基于同一份 spec 生成）。
   - 外发分享：`share_scope="external"` 会触发审批 confirm（`approval_overrides`）。导出前先完成脱敏（客户名/手机号/身份证按规则处理），并在报告页脚标注密级与可见范围。
   - 明细底表：`export_csv(data_ref="<结果引用>", filename="<报告名>-附录明细", desensitize=true)`，在报告附录中给出文件引用。

6. **交付与反馈闭环**
   - 交付时给：2~4 句核心结论摘要 + 报告卡 + 口径与版本 + 数据截止时间 + 后续可选动作（切问数深挖某个数 / 设为定时任务周期化 / 提交语义纠错提案）。
   - 报告 👍 → 核心把"问题 + 多步计划 + SQL + 图表选型 + 结论骨架"沉淀为 verified 样例（对应 `few_shots/verified-analyses.yaml` 的运行时样例库），提升 `use_count`。
   - 报告 ✏️ 纠错 → 生成语义提案进**待审队列**（`semantic.proposals`），人审发布后 version+1；历史会话仍 pin 旧版本，旧报告可复现。**只承诺"已提交待审提案"，不承诺"已修改口径"**。

7. **周期性报告（周报/月报）**
   - 结构与一次性报告相同，但需固定：对比窗口规则（周环比 = 上一自然周，月同比 = 去年同月）、Top N 榜单、异动阈值与标注方式。
   - 建议用户把该报告配置为定时任务（核心 Scheduled Tasks 能力），实现周期化产出；本套件只声明分析口径，不自行调度。

## 完整流程示例

承接 `attribution-analysis` 示例（数据集 `ds-trade-east-1024`，图表 `ch-01..ch-05`）。

```
Step 1（素材盘点）
  dataset_id=ds-trade-east-1024（5 表 + 4 条 join + 3 条默认过滤 + 日粒度）
  pin: valid_gmv@v2 / paid_order_cnt@v1 / aov@v1 / refund_rate@v1
  charts: ch-01 日趋势(line) / ch-02 渠道贡献(bar) / ch-03 品类下钻(bar) / ch-04 量价双轴(bar+line) / ch-05 渠道结构(pie)
  数据截止 2026-10-23（10-24 未完整入仓，已在归因阶段统一下修窗口）；执行库=只读从库 ro-mysql-prod-01

Step 2（摘要提炼）
  "华东区 2026-10（1~23 日）valid_gmv 1.82 亿，环比 -12.3%（剔除国庆假期后 -9.8%）、同比 -4.1%。
   主因：自营App 3C 数码订单量断崖，贡献总下滑 44.7%；异动起点 10-11。
   性质：纯"量"问题（订单量 -18.4%，客单价 +7.5%）。
   口径：valid_gmv@v2，日粒度，等长窗口，已剔除测试单与未支付单，置信度高。
   首要动作：本周补齐 4 个缺货主推 SKU，并做 10-11 前后自营App 3C 流量漏斗对比。"

Step 3~4（章节装配 + 引用 chips）
  sections = [summary, dataset_and_semantics, multi_dim_charts(5 小节), attribution, recommendations(3 条), citations]
  citations = [
    {type:"metric", ref:"valid_gmv", version:"v2", layer:"mysql_prod"},
    {type:"metric", ref:"paid_order_cnt", version:"v1"}, {type:"metric", ref:"aov", version:"v1"},
    {type:"metric", ref:"refund_rate", version:"v1"},
    {type:"table", ref:"ods_order_main", joins:["ods_order_main.order_id=ods_order_item.order_id (1:N)",
                                                "ods_order_main.region_id=dim_region.region_id (N:1)"]},
    {type:"rule", ref:"默认过滤: is_deleted=0 / order_type<>'TEST' / order_status IN (PAID,SHIPPED,FINISHED)"},
    {type:"rule", ref:"执行库: 只读从库 ro-mysql-prod-01 · 行级权限: 可见 region 3 个"},
    {type:"step", ref:"step1~step5", sql_summary:"总量趋势/渠道拆解/品类下钻/量价分解/异动定位"},
    {type:"sample", ref:"va-001-eastchina-sales-decline"}
  ]

Step 5（导出）
  report_export(title="华东区销售下滑归因分析报告（2026-10-01 ~ 10-23）",
                sections=sections, charts=["ch-01","ch-02","ch-03","ch-04","ch-05"],
                citations=citations, format=["html"], template="templates/report-template.md")
  → report 产物卡 + 分享链接（内部可见）
  export_csv(data_ref="step3", filename="华东区品类下滑明细-附录.csv", desensitize=true)
  用户要求外发 → report_export(..., format=["html","pdf"], share_scope="external")
  → 触发审批 confirm（外发脱敏确认），用户批准后生成 PDF 与外发链接

Step 6（交付）
  "报告已生成：华东区 10 月（1~23 日）valid_gmv 环比 -12.3%，主因自营App 3C 订单量断崖（贡献 44.7%），
   10-11 起异动；口径 valid_gmv@v2，置信度高。报告含 5 张图与完整引用溯源。
   可选：① 切问数场景深挖 3C Top SKU 明细；② 设为每周一自动生成；③ 若认为 v2 口径应含预售定金，我可提交语义纠错提案（进待审）。"
  → 用户 👍 → 核心沉淀为 verified 样例，use_count +1
```

## 注意事项

- **章节骨架不得删减**：`dataset_and_semantics` 与 `citations` 是分析场景区别于普通 BI 截图的关键，缺失即视为不合格报告（评审/复现都会失败）。
- **结论必须挂证据**：每段结论至少绑定一个 `chart_id` 与一个 SQL 步骤号；无证据支撑的判断只能进"待验证假设"。
- **数字一致性**：摘要、正文、图表注脚、附录中同一数字必须完全一致；先算后舍（展示保留 1 位小数），不得用四舍五入后的值再参与计算。
- **口径例外要显著标注**：若某步为特殊目的放宽了默认过滤（如含退款/含未支付单），必须在该小节与"数据集与口径说明"双处标注，避免读者误用。
- **降级必须标注水位线**：语义层缺失、走 DBSummary 圈定数据集、图表渲染失败退化为表格、导出器异常改为 Markdown 正文——都要在报告顶部或对应位置写明，不得静默降级。
- **脱敏与外发**：`share_scope="external"` 前完成脱敏并标注密级；不要为了跳过审批而改用内部链接外发。
- **导出失败不丢成果**：`report_export` 异常时，保留全部图表与结论卡，按模板骨架输出 Markdown 报告正文，并告知用户导出器异常。
- **不要把报告当分析**：报告是收口动作，只有在图表与结论已就绪时才调用；素材不足时先补分析，不要用空话填满章节。
- **P0 为 ReAct 编排**：报告装配由本技能驱动（提示词约束）；确定性后处理（章节绑定校验、引用装配、导出流水线）在 P1 以 `execution: flow` 引用 AWEL flow 实现，届时本技能职责收敛为"内容生产"。
- 工具只使用套件 `tools.allow` 内的：`report_export`、`export_csv`、`chart`（补图）、`semantic_search`（口径回源用于附录）。
