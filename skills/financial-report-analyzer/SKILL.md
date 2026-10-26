---
name: financial-report-analyzer
description: 用于中文非金融企业文本年度报告 PDF 的财务分析。从可识别的财务表格提取指标与页码证据，计算财务比率并生成图表和分析报告；不支持纯文本、扫描件 OCR 或叙述段落数值兜底。
---

# 财报分析技能 (Financial Report Analyzer)

本技能帮助 DB-GPT 分析中文非金融企业的文本年度报告 PDF，通过提取表格数据、计算财务比率、生成可视化图表并结合业务背景，产出有来源依据的财务分析报告。自动提取结果仍需人工核对。

## 输入与提取结果

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

## 核心工作流程

1. **数据提取与结构化**：
   - 使用 `execute_skill_script_file` 工具执行 `scripts/extract_financials.py` 脚本，传入财报文件路径（`file_path` 参数），自动提取营收、净利润、资产、负债等核心数值。
   - 脚本通过 pdfplumber 解析上述文本年度报告 PDF，返回包含精确金额、页码证据和兼容数值字段的 JSON。
   - 先检查 `error`、`_meta.status` 及各指标的 `extractionStatus`。部分指标缺失或冲突时保留空值，并在分析中说明缺口。

2. **财务比率计算**：
   - 使用 `execute_skill_script_file` 执行 `scripts/calculate_ratios.py`，传入 Step 1 的 JSON 数据。
   - 自动计算毛利率、净利率、ROE、资产负债率等关键指标，输出 30 个模板占位符键值。
   - 参考 `references/financial_metrics.md` 确保指标定义的准确性。
   - 系统将脚本的实际 JSON 结果捕获为 Python 产物，并通过通用 `auto_data` 传递模板字段，后续 `html_interpreter` 会自动合并。不使用专用 `ratio_data` 状态。

3. **图表生成**：
   - 使用 `execute_skill_script_file` 执行 `scripts/generate_charts.py`，传入 Step 1 的 JSON 数据。
   - 自动生成 3 张可视化图表：
     - `financial_overview.png`：核心财务指标对比柱状图
     - `profitability.png`：盈利能力指标横向条形图
     - `asset_structure.png`：资产结构环形饼图
   - **系统会自动将图片复制到静态目录并记录 URL 映射**（`react_state["image_url_map"]`），后续 html_interpreter 会自动合并。

4. **深度分析**：
   - 遵循 `references/analysis_framework.md` 提供的框架，从盈利质量、偿债风险、营运效率和现金流四个维度进行深度剖析。
   - 结合"经营情况讨论与分析"章节，解释业绩变动的核心驱动因素。
   - 撰写以下 7 段分析文本：
     - `PROFITABILITY_ANALYSIS`：盈利能力分析
     - `SOLVENCY_ANALYSIS`：偿债与风险分析
     - `EFFICIENCY_ANALYSIS`：营运效率分析
     - `CASHFLOW_ANALYSIS`：现金流与利润质量分析
     - `ADVANTAGES_LIST`：核心优势列表（HTML `<li>` 格式）
     - `RISKS_LIST`：主要风险列表（HTML `<li>` 格式）
     - `OVERALL_ASSESSMENT`：综合评价

5. **渲染报告**：
   - 调用 `html_interpreter`，使用 `template_path` 模式：
     ```json
     {
       "template_path": "financial-report-analyzer/templates/report_template.html",
       "data": {
         "PROFITABILITY_ANALYSIS": "LLM撰写的盈利能力分析...",
         "SOLVENCY_ANALYSIS": "LLM撰写的偿债分析...",
         "EFFICIENCY_ANALYSIS": "LLM撰写的营运效率分析...",
         "CASHFLOW_ANALYSIS": "LLM撰写的现金流分析...",
         "ADVANTAGES_LIST": "<li>优势1</li><li>优势2</li>",
         "RISKS_LIST": "<li>风险1</li><li>风险2</li>",
         "OVERALL_ASSESSMENT": "LLM撰写的综合评价..."
       },
       "title": "XX公司 2023年度财报分析报告"
     }
     ```
   - **重要**：`data` 字典中只需传入你撰写的 7 段分析文本！后端会自动合并：
     - Step 2 的 30 个数据指标（COMPANY_NAME、REVENUE、NET_PROFIT 等）
     - Step 3 的图表 URL（CHART_FINANCIAL_OVERVIEW、CHART_PROFITABILITY、CHART_ASSET_STRUCTURE）
   - **绝对不要**在 `data` 中包含数据指标或图表路径，否则 JSON 过大会导致截断。
   - 分析正文中的业务数值必须引用产生它的 SQL/Python 产物；通过 `report_evidence_manifest` 查看实际字段和路径，不手填或猜测选择器。使用知识库口径时，将对应切片绑定到具体方法说明；来源绑定不代表已通过确定性核验。

6. **完成**：
   - 调用 `terminate` 返回 1-2 句话的简短摘要。
   - 报告会以卡片形式展示在左侧面板，用户点击卡片即可在右侧面板查看完整报告。

## 完整流程示例

```
Step 1: execute_skill_script_file(skill_name="financial-report-analyzer", script_file_name="extract_financials.py", args={"file_path": "/path/to/report.pdf"})
  → 返回 schemaVersion: 1 的 JSON，含 document、facts、evidence、sourceObservations、_meta 和兼容数值字段（完整结果记为 raw_data）
  → 检查 error 和 _meta.status；unsupported 时停止自动计算，部分缺失或冲突的指标保留空值

Step 2: execute_skill_script_file(skill_name="financial-report-analyzer", script_file_name="calculate_ratios.py", args=<raw_data>)
  → 返回 30 个模板键值，系统捕获 Python 产物并通过通用 auto_data 传递模板字段

Step 3: execute_skill_script_file(skill_name="financial-report-analyzer", script_file_name="generate_charts.py", args=<raw_data>)
  → 生成图表，系统自动复制到 /images/ 并记录 URL 映射

Step 4: （LLM 自行撰写 7 段深度分析文本）

Step 5: html_interpreter(template_path="financial-report-analyzer/templates/report_template.html", data={仅包含 7 段分析文本}, title="报告标题")
  → 后端自动合并数据指标 + 图表 URL + 分析文本，渲染完整报告

Step 6: terminate(result="简短摘要")
```

## 资源使用说明

- **脚本**（均通过 `execute_skill_script_file` 执行）：
  - `scripts/extract_financials.py`：接收 `file_path` 参数，读取文本年度报告 PDF，返回指标、来源证据、解析状态和兼容数值字段。
  - `scripts/calculate_ratios.py`：计算财务比率，输出 30 个模板占位符键值。系统捕获实际结果和来源，复用通用模板数据流程。
  - `scripts/generate_charts.py`：生成 3 张可视化图表（matplotlib），系统自动处理图片复制。
- **参考**：
  - `references/financial_metrics.md`：包含公式定义。
  - `references/analysis_framework.md`：包含分析逻辑。
- **模板**：
  - `templates/report_template.html`：最终交付报告的 HTML 模板（**必须严格遵循**，不得删减章节或修改表格结构）。由 html_interpreter 的 template_path 参数自动读取并填充。
  - `templates/report_template.md`：Markdown 版本，仅供参考结构说明。

## 注意事项

- **必须使用 `execute_skill_script_file`** 执行脚本（不要用 shell_interpreter），因为 `execute_skill_script_file` 会自动处理图片复制和数据记录。
- 脚本提取可能受排版影响，建议在计算前人工核对提取的关键数值。
- 始终关注"非经常性损益"，以评估公司核心业务的真实盈利能力。
- 年报实际披露了可比数据时再分析多年趋势；兼容数值字段仅覆盖当年和上年，更多期间应检查 `facts` 中的来源与口径，不补造第三年数据。
- `extract_financials.py` 依赖 `pdfplumber>=0.10.4`；不会自动安装依赖或对扫描件执行 OCR。
- `generate_charts.py` 依赖 matplotlib，请确保环境中已安装该库。
