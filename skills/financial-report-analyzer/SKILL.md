---
name: financial-report-analyzer
description: 在当前智能体对话中分析中文上市公司文本型年度报告 PDF，支持单报告、同年度多公司及同公司跨年对比。提取真实财务事实，执行确定性计算，由当前智能体撰写带引用的结论，并用固定财报组件展示报告、来源和下载。
---

# 财报分析技能

用户直接在智能体对话上传年报或点击首页财报示例。所有步骤在当前对话完成，右侧 Computer 展示财报组件，不要求用户跳转独立页面。

## 工作流程

1. 调用 `prepare_financial_report`。仅有一份 PDF 可省略参数；有多份时指定当前附件清单的 `file_id`，不猜测路径或 ID。该工具复用页级提取器、Decimal 计算和报告存储，返回真实 facts、calculations、evidence、run_id、revision。它不调用另一个模型生成结论。
2. 工具的 `model_context` 是模型分析上下文，`chunks` 仅供界面展示。prepare 默认有界并发生成六专题并完整校验，返回 `review_context` 后直接逐项复核，不重复生成或保存。若返回 `topic_context` 则按串行恢复流程分析并 `save_financial_topic`；保存成功交接下个专题。显式读取或重做仍可 `get_financial_topic(run_id, topic_id)`。专题为 operating（经营表现）、recurring（扣非与利润构成）、margins（毛利变化）、expenses（费用变化）、cashflow（现金流）、balance（资产负债）。每个专题有依据时写两到三条互不重复的发现，不机械凑数；盈利质量三个专题分别展开。
3. 每条发现说明判断、事实或计算依据、反向信息与待核查事项。复制数据的 `reference` 字段，数字、年份和倍数由后端替换；不得直接写数字、追加单位、心算或编造原因。每条最多六个计算引用，过多时拆成多条。只分析当前专题数据，section 使用该专题返回值。费用率变化是百分点；负财务费用不能当缺失。没有附注证据时，仅描述现象和需要核查的可能线索，不能断言因果。
4. 每次遵循工具返回的 `next_action`。`topic_result.saved=false` 表示结论没有保存成功，一次处理全部 `issues` 的 `finding_index`、`field`；优先使用各错误的 hint 或 suggested_changes 修正，再使用新 revision 直接保存，不重复 get 或用 retry 重置计数。反向信息和待核查事项中的引用也必须声明在同一条发现的 Ids 数组。其他专题已保存结论不会丢失。仅当 `missingRequiredMetrics` 非空时，可提交空 findings，并用 `missing_reason` 说明缺项。连续三次失败后继续其他专题，复核时使用 insufficient，不将失败当成缺少财务数据或成功。
5. 缺少费用科目覆盖时可用 `append_findings` 只追加缺失科目的分析，保留已通过草稿，也可与 `patches` 合用；不要只追加引用 ID 而不讨论该科目。重复单位错误需同时检查本期金额是否被误写成增减额；无依据的原因假设放入 `unresolvedQuestions`，摘要只保留有依据的观察。
6. 全部专题处理后调用 `review_financial_report(run_id, revision, reviews)`。逐项覆盖全部专题，检查结论方向是否吻合引用数据、比较期间与口径是否一致、具体原因是否有原文依据。每项包含 topic_id、verdict（pass/revise/insufficient）、directionChecked、scopeChecked、causalityChecked（三项均为 true）和不含数字的具体 note。不要机械全部通过；需修订的专题单独修订后重新复核。失败或缺数据专题不得标记 pass。复核是当前智能体自查，不等于人工确认。
7. 明确复核完成后后端自动汇总发布；返回 `workflow.status=published` 后无需再次 publish。不再一次提交全报告 findings。只有逐专题处理并完成复核才可发布。按返回的 `completion_instructions`，依据 `completion_context` 正常回答用户的问题并 terminate。宽泛分析默认选择两三个最值得关注的发现，每段先解释变化意味着什么，再用少量数字支撑，段间留空行；不按内部专题逐栏报数，不写固定总结。正文财务数字以四到六处为宜，不反复列本期、上期和同比，用户明确要求明细时再展开。数字必须复制 facts/calculations 的 `reference`，占位符只显示数值及单位，金额会自动简写为万元或亿元；由你按语境写清指标名称、期间及判断，增减方向必须与计算一致；后端在数字旁添加可点击引用，定位到同一 HTML 报告的对应数据与计算依据。不得抄写 findings 中的数字、心算、追加单位或自行生成引用编号。保留具体证据边界，不用保存条数、专题数量等内部统计代替回答。不生成另一套 HTML，不跳转独立页面。
8. 普通追问调用 `read_financial_report` 后依据已保存数据回答。用户要求重做某专题时，先 read，再 `get_financial_topic(retry=true)`，仅保存该专题，重新复核并发布新版本；不重新提取 PDF。新上传报告才重新 prepare。旧版无 workflow 的报告保持旧协议，需新分析才能启用专题流程。

## 数据边界

- 当前提取器支持中文、人民币、非金融企业的文本型年度报告 PDF，使用真实比较期，缺项不补零。
- 归母净利润、扣非归母净利润、合并口径及期初/期末不能混用。
- 自动提取值仍待人工核对，引用校验不等于结论语义已经人工确认。
- `references/financial_metrics.md` 和 `references/analysis_framework.md` 可供参考，不能用参考材料中的常量补齐当前报告。
- 旧 scripts 与 HTML 模板保留兼容用途；当前智能体财报交付统一通过上述工具与固定组件完成。

保存校验失败时优先只传 `patches=[{"finding_index":错误索引,"changes":{"字段":"修正值"}}]`（省略 findings），后端合并已存草稿并完整重验。期间只使用 `data.periods` 中已提供的年份标签，财务数字仍须事实/计算引用。后端 errorCode/issues 是真实失败原因；复核意见不得将格式错误改写成数据缺失。

## 多财报对比

- 只有用户明确要求比较时才调用 `prepare_financial_comparison(file_ids, comparison_kind, baseline_file_id?)`。一次选择当前对话中两到五份已授权 PDF；`peer` 是同报告年度多公司，`trend` 是同公司不同报告年度。多附件本身不表示比较意图；单报告继续使用原工具。
- 比较使用 `schemaVersion=2, mode=comparison`，旧单报告仍是 v1。公司身份由封面/提取元信息识别，不由文件名推断；有歧义时向用户确认，通过 `resolve_financial_comparison(run_id, revision, resolutions)` 保存明确的公司及报告年度。禁止自行编造澄清结果。
- 复用原六专题保存、局部 patches、重试、复核和发布流程。复制 `findingReferenceTemplates` 的归属字段；每条发现另含 `entityIds`、`periods`、`metricCodes`、`subjectEntityId`、`baselineEntityId`、`comparisonDirection`。集合必须精确覆盖全部输入事实，方向与后端计算一致。单对象发现也必须提供字符串形式的 `subjectEntityId`，其基准为 null、方向为 none。
- 金额差、百分点和同比只引用已保存计算。横向“较基准公司”和跨年“较基准期”不能写成年同比；同比仅指有效共同披露基础上的相邻年度。业务结构差异不能据此解释为竞争力或经营原因。
- 同公司重复披露保留全部候选。仅有明确且相容的调整前后关系才按版本化政策取值；未解释冲突不选最新或首个值。跨年没有共同披露基础就保留断点，不拼接连续趋势。
- 数据就绪不等于模型分析通过或报告发布。文件失败、校验失败和数据不足分别说明；只剩一个有效对象时保存数据但不得声称完成对比。`workflow.status=published` 才可称“报告已生成”，其中的缺口仍须保留。
- 显式继续只重试失败文档及失败专题，成功文档不重新解析。单专题重做使用原 `get_financial_topic(retry=true)`；基准切换形成新版本，不能改写旧发布版。
- 追问可调用 `read_financial_report(run_id, revision)` 固定版本，引用链接携带 revision。历史、JSON 和离线 HTML 均读取同一快照；恢复不重新调用模型。离线 HTML 的来源 PDF 需要回到应用授权访问。

运行、显式迁移和隔离验收见 `docs/financial-comparison-acceptance.zh-CN.md`。当前执行器仅支持单个本地服务进程；扫描 PDF、跨币种换算、金融企业专用口径、季报及自动 OCR 不在本版验收范围。

## 底层 PDF 提取契约

以下字段描述 `scripts/extract_financials.py` 的原始提取结果；它与上文的单报告工作流及多报告比较快照分层使用，不替代专用财报工具。


- `file_path` 必须指向可读取的 `.pdf` 文件，内容为带文本层的中文年度报告。提取范围是可识别的合并财务报表和“主要会计数据和财务指标”规则表格，不提供季度报告、纯文本文件或金融企业专用报表的解析保证。
- 不执行 OCR，不从叙述段落中的邻近数字补填指标。扫描件、缺少年度标识或无法识别的表格可能返回 `_meta.status: "unsupported"`；此时停止后续自动计算，说明限制。文件格式错误或读取异常返回 `{"error": true, "message": "..."}`。
- 成功读取后的 JSON 使用 `schemaVersion: 1`，包含：
  - `document`：文档 ID、文件名、页数和 SHA-256。
  - `facts`：指标、期间、币种、单位、精确十进制字符串 `normalizedValue`、`extractionStatus`（`parsed` / `missing` / `conflict`）以及 `evidenceExcerptIds`。缺失或冲突值为 `null`，不能按零处理。
  - `evidence`：原始值、表格行列、单位依据和从 1 开始的 PDF 物理页码。`sourceObservations` 保留表格候选值及来源期间，包括期初余额和调整前数据；这些观察值不能直接视为可比财务事实。
  - `company_name`、`report_year`、`company_identity`：识别出的公司、年度及公司候选依据；未识别的信息保留空值，`report_date` 当前为 `null`。
  - `revenue`、`net_profit` 等当年数值及 `prev_` 前缀的上年数值：供现有比率和图表脚本使用的浮点兼容字段。需要精确金额或追溯来源时使用 `facts` 与 `evidence`。
  - `_meta`：已提取/缺失字段、解析状态、表格问题及限制。`humanVerified` 为 `false`，`parsed` 不表示已经人工核验。
- 金额按显式的元、千元、万元、百万元或亿元单位换算为人民币元；显式非人民币币种不受支持，不做汇率转换。仅识别显式调整前/后标记，不自动完成重述核对，也不将期初余额当作上年末余额。
- 提取依赖 `pdfplumber>=0.10.4`（声明在 `dbgpt-ext` 的 `rag` 可选依赖中）。该下限覆盖 `Page.extract_text_lines()` 和 `Page.close()` 两个实际调用的 API；脚本执行环境也必须满足此版本约束。
