---
name: chart-advisor
name_zh: 图表选型
command: /chart
user-invocable: true
description: 智能分析场景的图表自动匹配与出图技能。根据结果集的维度/度量/时间形态选择柱状图、折线图、饼图、散点图或组合图，完成维度度量映射、单位与口径注脚、Top N 截断，并对 ECharts option JSON 做括号配平与字段校验容错修复。当用户要求"出图/画图/可视化/图表/趋势图/占比图/对比图/柱状图/饼图/散点图/双轴图"，或 chart 调用返回 option 非法、图不出来、图形选错、坐标轴与单位不对、序列过多不可读时使用。触发词：图表、可视化、出图、画图、柱状图、条形图、折线图、饼图、散点图、堆叠图、双轴、chart、ECharts、图选错、图渲染失败。
---

# 图表自动匹配（Chart Advisor）

## 技能目标

把多步取数得到的结果集**自动、正确地**变成能回答一个具体问题的图表，并保证：

- **选型对**：时间序列用折线、类别对比用柱、结构占比用饼、相关性用散点，量纲差异大的双度量用双轴组合；
- **映射对**：x/y/series 与结果集列名严格对应，度量不放类目轴、维度不放数值轴；
- **可读**：类别过多先聚合或截断为 Top N + 其他，数据点过多先上卷；
- **可溯源**：标题为结论式短句，注脚带指标@版本、时间粒度、默认过滤提示与数据截止时间；
- **不崩**：option JSON 括号/引号配平、列名存在性校验，失败可自修一次。

图表产物（`chart`）是报告卡与右栏查看器的数据源，也是结论卡的证据锚点，因此每张图都要能被 `report_export` 通过 `charts` 引用绑定到章节。

## 核心工作流程

1. **识别结果集形态**
   - 读回该步 `sql_execute` 的 `columns` 与 `rows`，把列分成三类：**时间列**（stat_date/week/month，可排序）、**类别列**（region_name/channel_name/category_name，枚举）、**数值列**（度量，可求和/平均）。
   - 记录 `row_count`：> 60 个数据点先聚合或截断；类别 > 8 用横向条形或 Top N。

2. **按选型规则决定图类型**（`chart_type: auto` 时的判定顺序）

   | 判定条件（自上而下先命中先选） | 选型 |
   |---|---|
   | 无维度列且数值列 ≥ 2 | `scatter`（相关性/投入产出/离散异常） |
   | 有时间列 + 1~2 个数值列 | `line`（趋势） |
   | 有时间列 + 类别列 + 数值列，强调结构变化 | 堆叠 `bar`（或面积 `line`） |
   | 有时间列 + 类别列 + 数值列，强调总量趋势 | `line` + series=类别（序列 > 5 取 Top5 + 其他） |
   | 单期 + 类别列 + 数值列，问"占比/构成" | `pie`（类别 ≤ 6，超出合并"其他"，< 1% 不单独成扇区） |
   | 单期 + 类别列 + 数值列，问"排名/对比/差额" | `bar`（类别名长或类别多用横向条形，按度量降序） |
   | 两个量纲差异大的度量（金额 vs 比率） | 双轴 `bar + line`（左轴绝对值、右轴比率，标题与单位必须写明双轴） |

3. **完成维度度量映射**
   - `x` = 时间列或类别列（唯一）；`y` = 主度量列；`series` = 需要分组的第二维度列（可选）。
   - 差额/增长率类度量：`y` 用差额列，并在 `title` 中说明正负含义（负值 = 下滑），必要时设 0 基准线。
   - 比率类统一转百分比并保留 1 位小数；金额类按量级选 万/亿，**同一报告内单位保持一致**。

4. **调用 chart 出图**
   - `chart(data_ref="<步骤结果引用>", chart_type="auto|bar|line|pie|scatter", x="<列名>", y="<列名>", series="<列名或省略>", title="<结论式短句>", unit="<万元|亿|单|%>", footnote="valid_gmv@v2 · 日粒度 · 已剔除测试单 · 数据截止 2026-10-24")`
   - 拿到返回的 `chart_id` 与 ECharts option；核对 option 中 `series[].type`、`xAxis.type`（时间/类别为 `category`，散点为 `value`）、`data` 长度与结果集一致。

5. **JSON 容错与自修（option 非法时）**
   - 常见故障：括号/引号不配平、尾随逗号、列名写错（结果集里不存在）、`data` 里混入未转义的中文引号、把数值写成字符串导致轴异常。
   - 自修顺序：① 检查括号与引号配平（`{}`/`[]` 成对、字符串用双引号、去掉尾随逗号）→ ② 用结果集 `columns` 校验所有字段名 → ③ 数值列强制转 number，类别列强制转 string → ④ 数据点 > 60 先聚合 → ⑤ 用修正后的参数重试 **1 次**。
   - 仍失败：退化为结果表 + 文字描述（"该步数据以表格呈现，图表渲染失败：<原因>"），**不阻塞后续分析与报告**。

6. **图表组的一致性收口（出报告前）**
   - 单位一致（不要一张万元一张元）；配色语义一致（同一渠道/品类在各图颜色相同）；标题风格一致（都用结论式短句）。
   - 每张图对应一个结论要点；没有结论支撑的图不进报告（避免"图很多、结论没有"）。
   - 汇总 `chart_id` 列表交给 `report-generation` 做章节绑定。

## 完整流程示例

承接 `multi-step-analysis` 示例（数据集 `ds-trade-east-1024`，`valid_gmv@v2`，日粒度）。

```
结果集 A（Step 1）: columns=[stat_date, period, valid_gmv]  rows=72（24 天 × 3 个对比期）
  → 形态：时间列 + 类别列(period=本期/上期/去年同期) + 数值列
  → 选型：line + series=period（强调总量趋势）
  chart(data_ref="step1", chart_type="auto", x="stat_date", y="valid_gmv", series="period",
        title="华东区日度 valid_gmv：10-11 起持续低于上月同期", unit="万元",
        footnote="valid_gmv@v2 · 日粒度 · 已剔除测试单与未支付单 · 数据截止 2026-10-24")
  → chart_id="ch-01"；option 校验：xAxis.type="category"、series 3 条、data 长度 24×3 ✅

结果集 B（Step 2）: columns=[channel_name, gmv_current, gmv_prev, gmv_delta]  rows=3
  → 形态：类别列 + 数值列，问"谁贡献了下滑" → 选型：bar（按 gmv_delta 升序，负值在前）
  chart(data_ref="step2", chart_type="bar", x="channel_name", y="gmv_delta",
        title="渠道贡献：自营App 占总下滑 63.1%", unit="万元",
        footnote="负值=环比下滑额 · valid_gmv@v2 · 等长窗口 1~24 日")
  → chart_id="ch-02"

结果集 C（Step 3）: columns=[category_name, gmv_delta]  rows=14
  → 类别 14 > 8 → 截断 Top10 + 其他（其他 = 剩余 4 类合计，占比 3.2%）
  chart(data_ref="step3", chart_type="bar", x="category_name", y="gmv_delta",
        title="自营App下滑集中在 3C 数码（占 70.8%）", unit="万元", footnote="Top10 + 其他 · 已闭合至渠道差额 0.161 亿")
  → chart_id="ch-03"

结果集 D（Step 4）: columns=[stat_date, paid_order_cnt, aov]  rows=48（24 天 × 本期/上期）
  → 两个量纲差异大的度量（单 vs 元）→ 双轴 bar+line
  chart(data_ref="step4", chart_type="auto", x="stat_date", y="paid_order_cnt", series="period",
        title="3C 订单量自 10-11 断崖（-18.4%），客单价同期 +7.5%（右轴）", unit="单",
        footnote="左轴 订单量 paid_order_cnt@v1 · 右轴 客单价 aov@v1 · 双轴图")
  → chart_id="ch-04"

结果集 E（占比需求）: columns=[channel_name, gmv_current, share]  rows=7
  → 问"渠道结构占比" → pie，类别 7 > 6 → 合并后 5 类 + 其他
  chart(data_ref="step2b", chart_type="pie", x="channel_name", y="share",
        title="华东区渠道结构：自营App 占 46.2%，第三方 31.5%", unit="%", footnote="单期占比 · 合计 100.0%（含其他 2.1%）")
  → 首次返回报错 "option parse error: unexpected token at line 12"
  → 自修：发现 series[0].data 末项多了一个尾随逗号，且 category_name 误写为 categroy_name
  → 修正后重试 1 次成功，chart_id="ch-05"

收口：chart_id 列表 [ch-01..ch-05] + 每图一句结论 → 交 report-generation 绑定章节
      单位全报告统一为「万元」，比率统一「%」1 位小数；渠道配色跨图一致
```

## 注意事项

- **一张图只回答一个问题**：标题写结论式短句（"自营App 贡献 63% 下滑"）而不是"渠道对比图"；读者看图题就能拿到结论。
- **维度不要放数值轴**：把 `channel_name` 放进 `y` 会导致 ECharts 轴类型误判（应为 `category`）。映射前先看列类型。
- **饼图的适用边界**：只用于单期结构占比且类别 ≤ 6；多期结构变化用堆叠柱，不要用多个饼图并排（人眼比角度差的能力远差于比长度）。
- **序列过多不可读**：series > 5 时取 Top5 + 其他合并；散点数据点 > 500 时先聚合或抽样，并标注抽样比例。
- **负值与基准线**：差额类图表保留负值，不要取绝对值（会丢失"下滑"方向）；必要时加 0 基准线与数据标签。
- **单位与量级**：金额自动选 万/亿 后，`unit` 与 `footnote` 都要写明；同一报告内不得混用单位，否则读者会误读量级。
- **口径注脚不可省**：`指标@版本 · 时间粒度 · 默认过滤 · 数据截止时间` 四要素是图表可溯源的最低要求，也是报告引用 chips 的来源。
- **option JSON 括号配平是高频故障**：生成/修改 option 时先数括号再提交；失败按 §5 自修顺序处理，**最多重试 1 次**，避免在同一张图上反复消耗轮次。
- **不要为了好看改数**：不得截断 y 轴制造夸张斜率而不标注、不得隐藏异常点、不得平滑掉真实波动；如需突出显示，用标注（markLine/markArea）而不是改数据。
- **用户显式指定类型时以用户为准**，但明显不合适（20 个类别画饼图、时间序列画饼图）要提示并给出替代建议，由用户决定。
- 工具只使用套件 `tools.allow` 内的 `chart`（数据来源为 `sql_execute` 结果引用，报告绑定由 `report_export` 完成）。
