# 第 10 轮：专题修正反馈与发布稳定性

日期：2026-10-04 至 2026-10-05。起点：`c87e4f95`。本轮沿用首页当前智能体和财报组件，解决六专题流程停留在草稿的问题，不扩展 PDF 提取指标或页面布局。

## 已完成

- 专题批次采用完整校验：混合提交中只要一条不合法，就反馈真实发现序号、字段和错误；修正成功前不覆盖已保存专题。独立分析器与旧报告仍保留逐条接受有效发现的行为。
- 保存结果明确返回 `topic_result.saved`，不再让模型把工具返回误认为保存成功。工具根据实际状态提供 `next_action` 和最新 revision，指引修正当前专题、继续其他专题、复核或发布。
- 数字错误反馈列出当前字段中的未引用数值，提示全部删除或改用已有引用；不让模型自行计算差额，不放宽数字、来源和口径校验。反馈不保存被拒绝的原始结论文本。
- 重复读取未完成专题不再增加尝试次数、改变 revision 或重置修正预算。连续三次失败后明确记录失败和结束时间，仍可复核、发布部分报告；复核不会把失败状态改成“缺数据”。
- 单独重做专题时清除旧复核提示；其他专题和原提取、计算数据保留。已发布专题的普通读取不改变任务阶段，避免重启时把已发布报告重置为草稿，也不重新要求发布。
- 财报流程启用 40 步预算，普通聊天保持原预算。准备工具先返回流程和数据缺口，各专题再读取相关事实、计算与证据，减少重复发送整份报告。
- 增加真实智能体校验脚本，覆盖首页示例或真实文件上传、六专题发布、聊天历史、同会话追问以及可选的单专题重做。生命周期脚本支持指定测试 owner。

## 验证

最终后端及提取器相关回归 105 项通过。新增场景覆盖混合批次的实际错误字段、全部未引用数字反馈、重复读取与失败预算、失败专题的部分发布、已发布报告读取不改变阶段，以及修订后旧复核失效。修改文件 Ruff 和空白检查通过。

前端报告渲染、嵌入产物的历史/切换/来源/导出/重试测试，以及与 `5eb7ac42` 的初始布局对比通过。本轮没有修改前端，也没有重新执行全仓 TypeScript 检查或浏览器视觉验收。

真实 Qwen 使用 5671 独立测试服务、单独元数据库和 `financial-round10` owner：

| 样本 | 首次发布结果 | 有效发现 | 仍失败的专题 |
| --- | --- | --- | --- |
| 海翔药业 2019 | 已复核、已发布，partial | 15 | 现金流 |
| 安靠智电 2019 | 已复核、已发布，partial | 12 | 经营表现、毛利 |

两份样本均完成当前智能体的 prepare → 专题读取/保存/修正 → review → publish → terminate，同会话追问先 read，不重新提取，也不修改已保存报告。海翔单独重做费用专题完成新版本复核发布，其他专题结果保持一致。部分问答解释降级为已保存引用数据，不将其称为全部解释通过校验。

上述两次首次发布和费用重做验证在最终数值定位反馈加入前完成。最终代码对海翔现金流做单独重做：前两次保存失败，反馈明确列出未引用的数值；第三次修正成功，新增三条现金流发现。最终报告为 18 条发现、六个专题全部 reviewed、analysis completed，完成第三个发布版本；其他 15 条发现及原事实、计算保持一致。第一次补测曾遇到模型流连接中断，未执行财报工具、未改写报告；重试后上述流程通过。补测的原始事件按 step ID 拼接后核对了 false → false → true 三次保存结果。

最新报告与安靠报告均通过 JSON/HTML 下载、文件摘要、同版本幂等、历史重新打开和 owner 隔离；导出绑定同一保存版本。重启测试服务后，两份已发布报告保持已发布状态。不能据两份样本判断普遍成功率，也不能将智能体复核视为人工确认。

## 回归与真实检查命令

仓库根目录：

```powershell
.venv/Scripts/python.exe -m pytest packages/dbgpt-serve/src/dbgpt_serve/financial_analysis/tests packages/dbgpt-app/src/dbgpt_app/tests/test_examples_api.py skills/financial-report-analyzer/tests -q --disable-warnings
node standalone/financial-analysis/test-data.cjs
node standalone/financial-analysis/test-agent-artifact.cjs .work/financial-analysis/round7/ui-test/node_modules/react-test-renderer
node standalone/financial-analysis/test-layout.cjs 5eb7ac42
```

先配置独立测试服务及数据库。以下智能体命令会调用已配置的模型、创建测试对话和文件；`--pdf` 可换用自己的样本，默认使用首页财报示例。

```powershell
.venv/Scripts/python.exe scripts/financial_analysis_agent_check.py --base-url http://127.0.0.1:5671 --output-dir .work/financial-analysis/round10/check --retry-topic
.venv/Scripts/python.exe scripts/financial_analysis_lifecycle_check.py --base-url http://127.0.0.1:5671 --user-id financial-round10 --output-dir .work/financial-analysis/round10/lifecycle
```

`--resume` 使用同一输出目录的已保存分析事件，继续追问和可选的专题重做检查，避免重新分析整份 PDF。PDF、数据库、事件、导出和日志保存在被忽略的 `.work/financial-analysis/round10/`，不随源码提交。

本轮独立的 5671 服务已在收尾时关闭；测试数据保留在独立数据库中，不会自动出现在日常服务的聊天历史。日常后端需启动或重启以加载本轮代码。

## 边界与下一项

本轮完成流程收敛和失败透明化，仍是个人内测 Alpha。真实模型仍可能反复违反数字引用规则，导致专题失败；通过校验的文字也需核对语义与因果。下一项优先改善专题结论质量，核对最重要的发现和解释边界，再完成实际浏览器操作验收。完整三表、附注检索、OCR 和多文件期间对齐仍未进入本轮范围。
