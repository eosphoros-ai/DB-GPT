---
name: multi-step-analysis
name_zh: 多步分析
command: /analyze
user-invocable: true
description: 智能分析场景的多步取数与跨步口径一致性技能。在已圈定的数据集上按分析计划分步生成并执行只读 SQL，每步引用同一指标定义（版本 pin）、统一注入默认过滤与时间粒度，保证跨图跨步口径一致。当用户要求"分析/归因/趋势/对比/占比/复盘/出报告"，需要多步取数（总量趋势+维度拆解+环比同比+异动定位）、需要保证多张图口径一致、需要量价拆解或结构拆解、或出现"两次查的数不一样/口径不一致"问题时使用。触发词：多步分析、分步取数、口径一致、指标版本、pin、环比、同比、趋势、拆解、量价分解、分析报告、analyze。
---

# 多步取数与口径一致性（Multi-Step Analysis）

## 必需关联知识

依照[分析 SOP](../../prompts/analysis-playbook.md)串联
[数据集圈定](../dataset-scoping/SKILL.md)、[图表选型](../chart-advisor/SKILL.md)、
[归因分析](../attribution-analysis/SKILL.md)与[报告生成](../report-generation/SKILL.md)。
正文预加载不等于各步骤已执行；结论必须引用实际取得的数据。

## 技能目标

在一个已圈定的数据集（`dataset_id`）上，把分析问题拆成若干**可验证的取数步骤**，逐步执行并沉淀观察，最终为图表、归因与报告提供**同源、同口径**的数据。

分析场景与问数场景最大的差别在这里：问数是"一发 SQL 出一个数"，分析是"多步 SQL 出一份报告"。多步的最大风险是**口径漂移**——第 3 步的 GMV 和第 1 步的 GMV 算法不一样，导致环比对不上、占比不闭合、结论自相矛盾。本技能的全部纪律都围绕"跨步一致"展开：

1. 每步都带 `dataset_id`（表范围 + 默认过滤 + 粒度已被数据集锁定）；
2. 每步都传同一份 `metric_refs`（指标 + **pin 的版本**）；
3. 时间粒度全程统一，需要上卷时从同一份细粒度结果聚合；
4. 每步执行后立刻核对"横向一致性"（各步总量能否对上、占比是否闭合）。

## 核心工作流程

1. **确认前置条件**
   - 必须已有 `dataset_id`。没有 → 先走 `dataset-scoping` 技能圈定，不要在无数据集状态下直接写 SQL。
   - 从数据集卡读回：表白名单、join 路径与基数、`pin_metrics`（指标@版本）、`default_filters`、`grain`、可见范围（行级权限）。

2. **检索可复用的验证样例**
   - 调用 `semantic_search(query="<分析问题关键词>", types=["sample"], top_k=5, layer="mysql_prod")`，或比对套件内 `few_shots/verified-analyses.yaml`。
   - 命中同型样例（如"区域销售下滑归因"）→ 直接复用其步骤骨架与图表选型，把样例 `id` 记入后续报告引用。

3. **拆解并公布分析计划**
   - 把问题拆成 3~6 步，典型骨架：① 总量与趋势（含对比基准）→ ② 主维度拆解（渠道/区域）→ ③ 次维度下钻（品类/客户）→ ④ 量价或结构分解 → ⑤ 异动定位（时间/单点）→ ⑥ 补充验证。
   - 步数上限 8（套件 `analysis_defaults.max_steps`）；超限时先合并假设，不要盲目扩步。
   - **先把计划讲给用户**（每步一句话 + 预期产出），再开始取数。用户可在计划阶段纠正方向，成本远低于取数后返工。

4. **逐步取数（每步三动作）**
   - 生成：`nl2sql(question="<该步的自然语言问题，含维度与粒度>", dataset_id="<id>", metric_refs=[{metric: "valid_gmv", version: "v2"}], grain="day", sql_only=true)`。
   - 核对口径注入说明：确认返回里列出的默认过滤、join、指标表达式与数据集声明一致；不一致就重写 question（补维度/粒度/过滤措辞），**最多重试 2 次**。
   - 执行：`sql_execute(sql="<生成的 SQL>", dataset_id="<id>", limit=5000, timeout_s=30)`，拿回 `columns/rows/row_count/est_scan_gb/elapsed_ms`。
   - 每步结束后写一句"观察"：数字 + 变化幅度 + 指向的下一步。

5. **跨步一致性自检（每 2~3 步做一次）**
   - 总量对齐：拆解各部分之和 vs 步骤①的总量，差值 > 2% 必须解释（未覆盖类目归"其他"或标注口径缺口）。
   - 口径对齐：所有步骤的指标版本、默认过滤、粒度必须完全相同；若某步为特殊目的放宽了过滤（如含退款），在报告中标注为"口径例外步骤"。
   - 对比窗口对齐：环比/同比两侧窗口**等长**（本月 1~24 日 vs 上月 1~24 日 vs 去年同月 1~24 日），不要拿整月比半月。

6. **需要可视化时立即出图**
   - 调用 `chart(data_ref="<该步结果引用>", chart_type="auto", x="<维度列>", y="<度量列>", series="<可选分组列>", title="<结论式短句>", unit="<万/亿/%>")`，详细选型见 `chart-advisor` 技能。
   - 图表是报告的骨架，边取数边出图，不要攒到最后一次性生成。

7. **收敛到结论**
   - 步骤跑完后汇总各步观察，交给归因（`attribution-analysis` 技能）做贡献度计算与主因定位，再由 `report-generation` 技能装配报告。
   - 若数据不足以支撑用户想要的结论，如实说明缺口并给出"还需哪一步取数"，不要用推测填补。

8. **明细底表与导出**
   - 用户要底表或报告附录时：`export_csv(data_ref="<结果引用>", filename="<语义化文件名>", desensitize=true)`。
   - 导出行数 > 10 万会触发审批 confirm，先与用户确认范围。

## 完整流程示例

承接 `dataset-scoping` 示例：数据集 `ds-trade-east-1024`（5 表，`valid_gmv@v2`，日粒度，默认过滤已声明）。
用户问题：「分析本月华东区销售下滑的归因，出图文报告」（数据截止 2026-10-24）

```
Step 0（计划公布）
  "分 5 步：① 本月华东区 valid_gmv 日趋势 + 环比/同比基准；② 按渠道拆解贡献度；
   ③ 主力下滑渠道内按品类下钻；④ 量价分解（订单量 × 客单价）；⑤ 异动起点定位。
   全程 valid_gmv@v2、日粒度、等长对比窗口（1~24 日）。"

Step 1: nl2sql(question="华东区 2026-10-01 至 10-24 每日 valid_gmv，并给出 2026-09-01~09-24 与 2025-10-01~10-24 同期合计",
               dataset_id="ds-trade-east-1024", metric_refs=[{metric:"valid_gmv",version:"v2"}], grain="day", sql_only=true)
  → 口径注入说明: 已注入 is_deleted=0 / order_type<>'TEST' / order_status IN (PAID,SHIPPED,FINISHED) / region='华东' / join dim_region
  sql_execute(sql=..., dataset_id="ds-trade-east-1024", limit=5000, timeout_s=30)
  → 本月 1.82 亿；上月同期 2.075 亿（环比 -12.3%）；去年同期 1.898 亿（同比 -4.1%）
  chart(data_ref="step1", chart_type="auto", x="stat_date", y="valid_gmv", series="period", title="华东区日度 valid_gmv：10 月中旬起持续低于上月同期", unit="万元")
  观察：下滑集中在 10-11 之后，前半月与上月基本持平 → 指向步骤⑤定位异动起点

Step 2: nl2sql(question="华东区 2026-10-01~10-24 与 2026-09-01~09-24 按渠道汇总 valid_gmv 及差额",
               dataset_id="ds-trade-east-1024", metric_refs=[{metric:"valid_gmv",version:"v2"}], grain="day", sql_only=true)
  sql_execute(...) → 自营App -0.161 亿（占总下滑 63.1%）、第三方平台 -0.062 亿（24.3%）、线下门店 -0.032 亿（12.5%）
  自检：0.161+0.062+0.032 = 0.255 亿 = 步骤①的总差额 → 闭合 ✅
  chart(data_ref="step2", chart_type="bar", x="channel_name", y="gmv_delta", title="渠道贡献：自营App 贡献了 63% 的下滑", unit="万元")

Step 3: nl2sql(question="华东区自营App渠道 2026-10-01~10-24 vs 上月同期，按品类汇总 valid_gmv 差额 Top10",
               dataset_id="ds-trade-east-1024", metric_refs=[{metric:"valid_gmv",version:"v2"}], grain="day", sql_only=true)
  sql_execute(...) → 3C数码 -0.114 亿（占自营App下滑 70.8%）、服饰 -0.029 亿（18.0%）、家居 -0.018 亿（11.2%）
  自检：合计 0.161 亿 = 步骤②自营App差额 → 闭合 ✅
  chart(data_ref="step3", chart_type="bar", x="category_name", y="gmv_delta", title="自营App下滑集中在 3C 数码", unit="万元")

Step 4: nl2sql(question="华东区自营App 3C数码 本期与上期的 paid_order_cnt@v1 与 aov@v1，做量价分解",
               dataset_id="ds-trade-east-1024",
               metric_refs=[{metric:"valid_gmv",version:"v2"},{metric:"paid_order_cnt",version:"v1"},{metric:"aov",version:"v1"}],
               grain="day", sql_only=true)
  sql_execute(...) → 订单量 -18.4%、客单价 +7.5% → 下滑是"量"的问题，不是"价"的问题
  chart(data_ref="step4", chart_type="line", x="stat_date", y="paid_order_cnt", series="period", title="3C 订单量自 10-11 起断崖，客单价同期上行", unit="单")

Step 5: nl2sql(question="华东区自营App 3C数码 2026-10-05~10-24 每日 paid_order_cnt 与退款率 refund_rate@v1",
               dataset_id="ds-trade-east-1024", metric_refs=[{metric:"paid_order_cnt",version:"v1"},{metric:"refund_rate",version:"v1"}], grain="day", sql_only=true)
  sql_execute(...) → 10-11 起订单量断崖（-41% vs 10-10），退款率维持 2.1% 无异常
  观察：异动起点 10-11、仅限自营App 3C、非退款导致 → 事实层面的定位完成

Step 6（收敛）
  → 交给 attribution-analysis 做贡献度排序与主因/次因判定；
    "竞品促销导致"属于外部因素，数据库无佐证 → 写入"待验证假设"，不写进结论；
  → 交给 report-generation 装配报告（引用 valid_gmv@v2 / paid_order_cnt@v1 / aov@v1 / refund_rate@v1 + 5 张图表 + 5 步 SQL 痕迹）
```

## 注意事项

- **没有 `dataset_id` 不取数**：绕过数据集直接写 SQL 会丢失默认过滤与白名单约束，是口径漂移的头号原因。
- **指标版本一次 pin、全程复用**：`metric_refs` 里的 `version` 每一步都要显式传，且必须相同。若某指标未在 `suite.semantic.pin.versions` 中，取最新 published 版本并在报告口径说明里写明版本号与生效时间；发现版本有问题时停下来告知用户 + 提交语义纠错提案，**不要中途换版本**。
- **不要手写口径过滤**：软删除、测试单、订单状态、行级权限由数据集统一注入。SQL 里出现重复或冲突的过滤条件时，说明 question 写法诱导了模型重写口径，需重写 question。
- **等长窗口对比**：环比/同比必须窗口等长且同粒度。"本月至今 vs 上月整月"是常见错误，会得到虚高的下滑幅度。
- **禁止混粒度**：日粒度结果不要与月粒度结果直接相减。要周维度就从日粒度上卷（同一份数据），并说明周起始日约定（周一为周首）。
- **1:N join 的聚合侧**：主表 join 明细表时，金额度量若在主表侧，需先在明细侧聚合到订单粒度再上卷，否则金额翻倍。每步核对 `row_count` 是否符合预期量级。
- **每步都要自检数字量级**：结果行数、总量与上一步是否对得上；对不上先查口径，再查数据。
- **代价意识**：优先聚合后取数，明细只在必要时取且带 `limit`；`est_scan_gb > 100` 会触发审批 confirm，先与用户说明并给替代方案（缩窗、降粒度、只跑关键步骤）。
- **失败降级**：`nl2sql` 口径不符 → 重写 question（≤2 次）；`sql_execute` 超时 → 缩窗/先聚合/分片；连续失败 → 输出已完成步骤的阶段性结果并说明未完成项，不要静默丢步。
- **计划可调、口径不可调**：用户中途改需求可以增删步骤，但不能改已 pin 的指标版本与默认过滤（需要改则重新圈数据集并声明为新口径）。
- 工具只使用套件 `tools.allow` 内的：`semantic_search`、`nl2sql`、`sql_execute`、`chart`、`export_csv`（数据集圈定用 `dataset_scope`，报告用 `report_export`）。
