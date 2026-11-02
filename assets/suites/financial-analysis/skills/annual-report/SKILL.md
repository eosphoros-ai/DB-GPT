---
name: annual-report
name_zh: 读年报
name_en: Annual Report
command: /读年报
command-en: /annual-report
user-invocable: true
description: 上传一份年度报告 PDF，解读经营表现、利润质量、现金流与资产负债，并关联原文依据。
description_en: Upload one annual-report PDF to analyze operating performance, earnings quality, cash flow and the balance sheet with source evidence.
argument-hint-zh: 请分析这份年度报告，说明最值得关注的经营变化、现金流和风险，并给出原文依据。
argument-hint-en: Analyze this annual report, explain the most important operating changes, cash flow and risks, and cite the source evidence.
input_files:
  min: 1
  max: 1
  types: [application/pdf]
---

# 读年报

遵循[财报分析流程](../../prompts/financial-playbook.md)。分析对象是一份已授权的年度报告 PDF。

- 只有一份 PDF 时调用 `prepare_financial_report()`；有多份附件时先确认目标，再使用附件清单的真实 `file_id`，不能随意选择第一份。
- 本命令不自动启动多财报比较。用户需要比较时，请使用财报对比任务并明确比较范围。
- 缺少文件时提示上传一份支持的 PDF；普通追问使用 `read_financial_report` 读取已有报告，不要求重复上传。
- 关注经营表现、扣非与利润构成、毛利变化、费用变化、现金流和资产负债。指标不足时解释缺口，不填零或臆测原因。
- 使用后端的固定财报展示与引用，不另写 HTML 或改用通用报告工具。
