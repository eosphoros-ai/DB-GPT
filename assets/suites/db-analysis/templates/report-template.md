# {{report_title}}

<!--
  智能分析套件 (db-analysis) · 图文分析报告模板
  用途：report_export 的 template 入参；也是 LLM 装配 sections 时的章节骨架。
  约束：章节顺序与标题不得删减（尤其「数据集与口径说明」与「引用溯源附录」）；
        占位符 {{...}} 全部替换为实际内容；图表以 chart_id 绑定，不内嵌 base64。
  叙事顺序：总量趋势 → 结构拆解 → 逐层下钻 → 量价/异动 → 归因 → 建议。
-->

| 项 | 值 |
|---|---|
| 报告期间 | {{period_start}} ~ {{period_end}}（{{period_note}}） |
| 对比基准 | 环比 {{mom_window}} · 同比 {{yoy_window}}（等长窗口） |
| 分析范围 | {{scope_desc}}（区域/渠道/品类/客户群） |
| 数据集 | `{{dataset_id}}` · {{table_count}} 张表（语义层白名单） |
| 核心口径 | {{metric_refs_pinned}}（如 `valid_gmv@v2`、`paid_order_cnt@v1`） |
| 时间粒度 | {{grain}}（day / week / month，全程统一） |
| 数据截止 | {{data_as_of}} · 生成时间 {{generated_at}} |
| 执行库 | {{execution_instance}}（只读从库） · 可见范围 {{row_level_scope}} |
| 状态标注 | {{status_flags}}（正常 / 语义层降级 / 含口径例外步骤 / 图表退化） |

---

## 一、摘要（Executive Summary）

> 5 行以内，业务负责人只读本节也能决策。每行一个要点，全部带数字。

1. **发生了什么**：{{headline_finding}}（含指标、幅度、期间，例：华东区 10 月 valid_gmv 1.82 亿，环比 -12.3%）
2. **主因是什么**：{{primary_driver}}（含量化贡献度，例：自营App 3C 订单量断崖，贡献总下滑 44.7%）
3. **范围与起点**：{{impact_scope_and_onset}}（例：仅自营App + 仅 3C + 仅华东，10-11 起）
4. **性质判断**：{{nature_of_change}}（量/价、规模/结构，例：纯"量"问题，客单价同期 +7.5%）
5. **首要动作**：{{top_recommendation}}（谁做、做什么、何时复盘）

**置信度**：{{confidence_level}}（高/中/低）· **依据**：{{confidence_basis}}（闭合校验通过 / 已排除口径变更与数据缺失 / 样本量说明）

---

## 二、数据集与口径说明（Dataset & Semantics）

> 本章保证报告可复现。语义层缺失或降级时必须在此显著标注。

### 2.1 数据集范围（语义层表白名单）

| # | 表 | 语义说明 | 角色 | 白名单状态 |
|---|---|---|---|---|
| 1 | {{table_1}} | {{table_1_desc}} | 事实表 | published |
| 2 | {{table_2}} | {{table_2_desc}} | 明细表 | published |
| 3 | {{table_n}} | {{table_n_desc}} | 维度表 | published |

### 2.2 join 路径（来自语义层血缘）

```
{{join_path_1}}   例：ods_order_main.order_id = ods_order_item.order_id   (1:N)
{{join_path_2}}   例：ods_order_main.region_id = dim_region.region_id     (N:1)
```

**聚合侧约定**：{{aggregation_side_note}}（1:N join 下度量在哪一侧聚合，避免金额放大）

### 2.3 指标口径（版本 pin）

| 指标 | 版本 | 表达式 / 定义要点 | 默认过滤 | 时间粒度 | Owner | 生效时间 |
|---|---|---|---|---|---|---|
| {{metric_1}} | {{metric_1_version}} | {{metric_1_expression}} | {{metric_1_filters}} | {{grain}} | {{owner}} | {{effective_from}} |

> 会话内 pin 说明：本报告全程使用上述版本，未混用其他版本；若需变更口径，将提交语义纠错提案（进待审队列），不影响本报告可复现性。

### 2.4 统一注入的默认过滤与规则

- {{default_filter_1}}（例：`is_deleted = 0` 软删除过滤）
- {{default_filter_2}}（例：`order_type <> 'TEST'` 剔除测试单）
- {{default_filter_3}}（例：`order_status IN ('PAID','SHIPPED','FINISHED')`）
- 行级权限：{{row_level_scope}}；执行策略：只读 SELECT、超时 {{timeout_s}}s、行数上限 {{row_limit}}

### 2.5 口径例外与降级标注

- {{caveat_1}}（例：10-24 数据未完整入仓，所有窗口统一截至 10-23）
- {{caveat_2}}（例：第 4 步含退款单，为净额分析特例，已在该节标注）
- {{degradation_note}}（例：语义层未绑定，数据集基于 DBSummary 表摘要圈定，口径需人工确认 → 结论置信度下调一档）

---

## 三、多维度图表分析（Analysis by Dimension）

> 每张图一小节：结论式小标题 → 图 → 2~4 句解读 → 口径注脚。图的顺序服从叙事逻辑。

### 3.1 {{chart_1_title}}

![{{chart_1_title}}](chart://{{chart_1_id}})

- **观察**：{{chart_1_observation}}（关键数字 + 变化幅度）
- **解读**：{{chart_1_interpretation}}（这个数字意味着什么，指向哪一步下钻）
- **口径**：{{chart_1_metric_ref}} · {{grain}} · {{chart_1_window}} · 数据截止 {{data_as_of}}
- **证据**：SQL 步骤 {{chart_1_step_ref}}

### 3.2 {{chart_2_title}}

![{{chart_2_title}}](chart://{{chart_2_id}})

- **观察**：{{chart_2_observation}}
- **解读**：{{chart_2_interpretation}}
- **闭合校验**：{{closure_check}}（各部分之和 vs 总量，差值与"其他"占比说明）
- **口径**：{{chart_2_metric_ref}} · **证据**：SQL 步骤 {{chart_2_step_ref}}

### 3.3 {{chart_3_title}}（逐层下钻）

![{{chart_3_title}}](chart://{{chart_3_id}})

- **观察**：{{chart_3_observation}}
- **下钻停止原因**：{{drill_stop_reason}}（已达可执行粒度 / 贡献度 < 40% 分布均匀 / 样本 < 30 / 步数上限）

### 3.4 {{chart_4_title}}（量价 / 结构分解）

![{{chart_4_title}}](chart://{{chart_4_id}})

| 分解项 | 数值 | 说明 |
|---|---|---|
| 量效应（Δ量 × 基期价） | {{volume_effect}} | {{volume_effect_note}} |
| 价效应（Δ价 × 本期量） | {{price_effect}} | {{price_effect_note}} |
| 合计 vs 实际变动 | {{decomposition_check}} | 误差 {{decomposition_error}}（> 1% 需复核指标版本） |
| 结构效应（mix shift） | {{mix_effect}} | {{mix_effect_note}} |

### 3.5 {{chart_5_title}}（异动定位 / 补充视角）

![{{chart_5_title}}](chart://{{chart_5_id}})

- **异动起点**：{{anomaly_onset}} · **影响范围**：{{anomaly_scope}}
- **库内可查变化**：{{internal_evidence}}（活动结束/缺货/价格调整等系统内记录）

---

## 四、归因结论（Attribution & Conclusions）

### 4.1 结论清单

| # | 结论 | 量化依据 | 证据（图表 / 步骤） | 口径 | 置信度 |
|---|---|---|---|---|---|
| 1 | {{conclusion_1}} | {{conclusion_1_evidence_numbers}} | {{conclusion_1_charts}} / {{conclusion_1_steps}} | {{conclusion_1_metric_ref}} | {{conclusion_1_confidence}} |
| 2 | {{conclusion_2}} | {{conclusion_2_evidence_numbers}} | {{conclusion_2_charts}} / {{conclusion_2_steps}} | {{conclusion_2_metric_ref}} | {{conclusion_2_confidence}} |
| 3 | {{conclusion_3}} | {{conclusion_3_evidence_numbers}} | {{conclusion_3_charts}} / {{conclusion_3_steps}} | {{conclusion_3_metric_ref}} | {{conclusion_3_confidence}} |

### 4.2 贡献度分解（主因 / 次因 / 长尾）

| 层级 | 维度成员 | 变动额 | 贡献度 | 累计贡献度 |
|---|---|---|---|---|
| L1（{{l1_dim}}） | {{l1_member_1}} | {{l1_delta_1}} | {{l1_share_1}} | {{l1_cum_1}} |
| L1（{{l1_dim}}） | {{l1_member_2}} | {{l1_delta_2}} | {{l1_share_2}} | {{l1_cum_2}} |
| L2（{{l2_dim}}） | {{l2_member_1}} | {{l2_delta_1}} | {{l2_share_1}} | {{l2_cum_1}} |

**闭合说明**：{{closure_summary}}（Σ 各层变动额 = 总变动额，差值 {{closure_gap}}，未覆盖部分归入"其他"占 {{other_share}}）

### 4.3 待验证假设（不作为结论）

| # | 假设 | 为何不能定为结论 | 需要什么数据/动作来验证 | 建议验证方 |
|---|---|---|---|---|
| 1 | {{hypothesis_1}} | {{hypothesis_1_reason}}（数据库内无佐证） | {{hypothesis_1_validation}} | {{hypothesis_1_owner}} |
| 2 | {{hypothesis_2}} | {{hypothesis_2_reason}} | {{hypothesis_2_validation}} | {{hypothesis_2_owner}} |

### 4.4 已完成的可信度排除

- 口径/版本变更：{{rule_out_metric_change}}
- 数据完整性（截止/缺数）：{{rule_out_data_completeness}}
- 日历效应（工作日数/节假日/大促）：{{rule_out_calendar}}
- 退款与取消异常：{{rule_out_refund}}
- 权限范围变化：{{rule_out_permission}}

---

## 五、建议与后续动作（Recommendations）

> 最多 5 条，按优先级排序；每条必须可执行、可归属、可复盘。禁止"加强运营"类空话。

| 优先级 | 建议动作 | 责任方 | 预期观测指标 | 复盘时间 | 依据 |
|---|---|---|---|---|---|
| P0 | {{action_1}} | {{action_1_owner}} | {{action_1_kpi}} | {{action_1_review_date}} | {{action_1_evidence}} |
| P1 | {{action_2}} | {{action_2_owner}} | {{action_2_kpi}} | {{action_2_review_date}} | {{action_2_evidence}} |
| P2 | {{action_3}} | {{action_3_owner}} | {{action_3_kpi}} | {{action_3_review_date}} | {{action_3_evidence}} |

**后续分析建议**：{{next_analysis}}（例：接入竞品价格数据源验证假设 1；对自营App 3C 做流量漏斗拆解定位流量端 vs 转化端）
**周期化建议**：{{scheduling_note}}（例：本报告口径可配置为每周一自动生成的经营周报）

---

## 六、引用溯源附录（Citations & Traceability）

### 6.1 指标版本引用（chips）

`{{metric_chip_1}}` `{{metric_chip_2}}` `{{metric_chip_3}}`
（例：`valid_gmv@v2` · `paid_order_cnt@v1` · `aov@v1` · `refund_rate@v1`；语义层 `{{semantic_layer}}`）

### 6.2 数据来源引用

| 表 | join / 关系 | 语义状态 | 引用章节 |
|---|---|---|---|
| {{cite_table_1}} | {{cite_table_1_join}} | published | {{cite_table_1_sections}} |

### 6.3 执行痕迹（SQL 步骤索引）

| 步骤 | 目的 | 结果规模 | 预估扫描 | 耗时 | 产物 |
|---|---|---|---|---|---|
| step1 | {{step1_purpose}} | {{step1_rows}} 行 | {{step1_scan_gb}} GB | {{step1_elapsed}} | {{step1_artifact}}（ch-01） |
| step2 | {{step2_purpose}} | {{step2_rows}} 行 | {{step2_scan_gb}} GB | {{step2_elapsed}} | {{step2_artifact}}（ch-02） |

> 完整 SQL 文本由核心按 `sql_card` 渲染器保留在会话轨迹中，可点击 chips 逐条复跑（只读从库）。

### 6.4 命中的已验证样例（few-shots）

| 样例 id | 问题 | 复用部分 | use_count |
|---|---|---|---|
| {{sample_id}} | {{sample_question}} | {{sample_reused}} | {{sample_use_count}} |

### 6.5 规则、权限与审计

- 执行策略：{{guardrails}}（只读 SELECT / 超时 / 行数上限 / 只读从库）
- 行级权限：{{row_level_scope}}
- 审批记录：{{approval_log}}（如触发高代价扫描 confirm / 外发分享 confirm，记录决议人与时间）
- 脱敏说明：{{desensitization_note}}（外发版本已处理的字段）
- 套件与版本：`db-analysis@{{suite_version}}` · 会话 pin `{{suite_pin}}` · 编排 `{{execution_mode}}`

### 6.6 附件

- 明细底表：{{csv_attachment}}（`export_csv` 产出，已脱敏）
- 报告格式：{{report_formats}}（HTML 分享链接 / PDF 归档）

---

<!--
  反馈闭环（由核心渲染，不在模板正文出现）：
    👍 沉淀 → 本次「问题 + 多步计划 + SQL + 图表选型 + 结论骨架」写入 verified 样例库，use_count+1
    ✏️ 纠错 → 生成语义提案进入待审队列（semantic.proposals），人审发布后 version+1；
              历史会话仍 pin 旧版本，本报告保持可复现
-->
