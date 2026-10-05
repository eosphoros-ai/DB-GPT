---
name: financial-report-analyzer
description: 在当前智能体对话中分析中文上市公司文本型年度报告 PDF。提取真实财务事实，执行确定性计算，由当前智能体撰写带引用的结论，并用固定财报组件展示报告、来源和下载。
---

# 财报分析技能

用户直接在智能体对话上传年报或点击首页财报示例。所有步骤在当前对话完成，右侧 Computer 展示财报组件，不要求用户跳转独立页面。

## 工作流程

1. 调用 `prepare_financial_report`。仅有一份 PDF 可省略参数；有多份时指定当前附件清单的 `file_id`，不猜测路径或 ID。该工具复用页级提取器、Decimal 计算和报告存储，返回真实 facts、calculations、evidence、run_id、revision。它不调用另一个模型生成结论。
2. 按返回的 `workflow.topics` 逐专题执行 `get_financial_topic(run_id, topic_id)` → 分析 → `save_financial_topic(run_id, revision, topic_id, findings)`。专题为 operating（经营表现）、recurring（扣非与利润构成）、margins（毛利变化）、expenses（费用变化）、cashflow（现金流）、balance（资产负债）。每个专题有依据时写两到三条互不重复的发现，不机械凑数；盈利质量三个专题分别展开。
3. 每条发现说明判断、事实或计算依据、反向信息与待核查事项。复制数据的 `reference` 字段，数字、年份和倍数由后端替换；不得直接写数字、追加单位、心算或编造原因。每条最多六个计算引用，过多时拆成多条。只分析当前专题数据，section 使用该专题返回值。费用率变化是百分点；负财务费用不能当缺失。没有附注证据时，仅描述现象和需要核查的可能线索，不能断言因果。
4. 每次遵循工具返回的 `next_action`。`topic_result.saved=false` 表示结论没有保存成功，按 `issues` 的 `finding_index`、`field` 修正，再使用新 revision 直接保存，不重复 get 或用 retry 重置计数。反向信息和待核查事项中的引用也必须声明在同一条发现的 Ids 数组。其他专题已保存结论不会丢失。仅当 `missingRequiredMetrics` 非空时，可提交空 findings，并用 `missing_reason` 说明缺项。连续三次失败后继续其他专题，复核时使用 insufficient，不将失败当成缺少财务数据或成功。
5. 全部专题处理后调用 `review_financial_report(run_id, revision, reviews)`。逐项覆盖全部专题，检查结论方向是否吻合引用数据、比较期间与口径是否一致、具体原因是否有原文依据。每项包含 topic_id、verdict（pass/revise/insufficient）、directionChecked、scopeChecked、causalityChecked（三项均为 true）和不含数字的具体 note。不要机械全部通过；需修订的专题单独修订后重新复核。失败或缺数据专题不得标记 pass。复核是当前智能体自查，不等于人工确认。
6. 调用 `publish_financial_report(run_id, revision)` 汇总发布，不再一次提交全报告 findings。只有逐专题处理并完成复核才可发布。报告在当前对话右侧显示，保留部分分析、失败及缺项。然后简短总结并 terminate；不生成另一套 HTML，不跳转独立页面。
7. 普通追问调用 `read_financial_report` 后依据已保存数据回答。用户要求重做某专题时，先 read，再 `get_financial_topic(retry=true)`，仅保存该专题，重新复核并发布新版本；不重新提取 PDF。新上传报告才重新 prepare。旧版无 workflow 的报告保持旧协议，需新分析才能启用专题流程。

## 数据边界

- 当前提取器支持中文、人民币、非金融企业的文本型年度报告 PDF，使用真实比较期，缺项不补零。
- 归母净利润、扣非归母净利润、合并口径及期初/期末不能混用。
- 自动提取值仍待人工核对，引用校验不等于结论语义已经人工确认。
- `references/financial_metrics.md` 和 `references/analysis_framework.md` 可供参考，不能用参考材料中的常量补齐当前报告。
- 旧 scripts 与 HTML 模板保留兼容用途；当前智能体财报交付统一通过上述工具与固定组件完成。
