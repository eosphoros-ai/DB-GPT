---
name: financial-workflow
name_zh: 财报工作流与证据规则
name_en: Financial Workflow and Evidence
user-invocable: false
description: 专用财报工具的提取、专题分析、复核、发布与引用规则。
description_en: Rules for extraction, topic analysis, review, publication and citations using the dedicated financial tools.
---

# 财报工作流与证据规则

## 执行与恢复

- `prepare_financial_report` 和 `prepare_financial_comparison` 是已注册的工具，不能当成脚本执行。工具返回当前持久化状态和合法 `next_action`，按该动作继续。
- 六个专题逐项保留有依据的发现。需要修订时只修指定专题，用 `get_financial_topic`、`save_financial_topic` 保存更改；不重复解析 PDF 或生成已经成功保存的内容。
- `review_financial_report` 依据返回的 `review_context` 逐项复核。未通过、失败或数据不足的专题不能标记为通过；模型复核不等于人工核验。
- 仅按工具指引调用 `publish_financial_report`；复核后已自动发布时无需重复发布。只有 `workflow.status=published` 才能称为报告已生成，仍须保留具体缺口。
- 普通追问先 `read_financial_report`。读取当前会话已保存的报告或明确版本，不能把另一个会话或另一版的结果当成当前报告。

## 证据与回答

- 财务数字、同比、差额和百分点使用后端已保存事实与计算的引用，不能自行心算、填补缺失值或把来源文本中的邻近数字补进指标。
- 公司、期间、合并口径、归母与扣非口径、期初与期末不得混用。比较发现保留工具规定的对象、基准、期间、指标与方向字段。
- 使用工具返回的引用模板和 `completion_instructions`。金额单位由引用渲染，不重复追加单位或自行编造引用编号。
- 默认回答突出两三个最值得关注的变化，解释含义并给少量关键数字；详细数据放在报告中。用户明确要求明细时再展开。
- 固定财报组件负责报告、图表与原文依据展示。不得调用 `generate_report`、`html_interpreter`、代码或 shell 生成另一份报告。

## 支持范围

当前支持具有文本层的中文、人民币、非金融企业年度报告 PDF。扫描件、自动 OCR、季报、跨币种换算和金融企业专用口径不在支持范围。文件、提取、专题分析或复核失败必须按真实错误说明，保留可用结果，不能把未完成任务标为完成。
