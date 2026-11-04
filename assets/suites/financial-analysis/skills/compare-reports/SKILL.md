---
name: compare-reports
name_zh: 财报对比
name_en: Compare Reports
command: /财报对比
command-en: /compare-reports
user-invocable: true
description: 上传两到五份年度报告 PDF，比较同年多家公司或同公司跨年的表现，解释可比口径和数据缺口。
description_en: Upload two to five annual-report PDFs to compare peers or reporting years while preserving comparability limits and data gaps.
argument-hint-zh: 请比较这些年度报告的经营表现、利润质量和现金流，说明可比口径与数据缺口。
argument-hint-en: Compare these annual reports for operating performance, earnings quality and cash flow, explaining comparability and data gaps.
input_files:
  min: 2
  max: 5
  types: [application/pdf]
---

# 财报对比

遵循[财报分析流程](../../prompts/financial-playbook.md)。选中本快捷命令表示用户请求比较；若用户同时明确说不要比较，则先确认新的任务，不执行比较。

- 材料是当前会话中两到五份已授权年度报告 PDF。使用附件清单的真实 ID，不能编造 ID 或使用其他会话的文件。
- `comparison_kind="peer"` 表示同报告年度多公司，`comparison_kind="trend"` 表示同公司跨年。先根据用户请求确定比较类型和范围；信息不足时询问，不从文件名猜测公司身份或报告年度。
- 通过 `prepare_financial_comparison(file_ids, comparison_kind, baseline_file_id?)` 创建比较。身份与年度歧义按工具反馈确认，再调用 `resolve_financial_comparison` 保存用户明确的选择。
- 使用后端对齐后的事实与计算，保留公司、期间、口径和基准。缺少共同披露基础时保留断点；不把跨公司差额写成年同比。
- 部分文档失败时保留成功数据，明确失败文档及其影响。只有一个有效对象时不得声称完成比较；已有比较报告的追问读取固定版本，不重新提取。
