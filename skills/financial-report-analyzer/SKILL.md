---
name: financial-report-analyzer
description: 专门用于上市公司财报（如年度报告、季度报告）的深度分析。该技能能够自动提取关键财务指标，计算核心财务比率，生成可视化图表，并结合行业背景生成专业的财务分析报告。
---

# 财报分析技能 (Financial Report Analyzer)

本技能旨在帮助 DB-GPT 系统化地分析上市公司财报，通过提取核心数据、计算财务比率、生成可视化图表并结合业务背景，产出高质量的财务分析报告。

## 核心工作流程

1. **数据提取与结构化**：
   - 使用 `execute_skill_script_file` 工具执行 `scripts/extract_financials.py` 脚本，传入财报文件路径（`file_path` 参数），自动提取营收、净利润、资产、负债等核心数值。
   - 脚本支持 PDF 文件（通过 pdfplumber 解析）和纯文本文件，返回 JSON 格式的结构化数据。

2. **财务比率计算**：
   - 使用 `execute_skill_script_file` 执行 `scripts/calculate_ratios.py`，在 `input_artifact_ids` 指定 Step 1 的提取产物 ID；程序直接读取该产物作为输入，不接受手写覆盖数值。
   - 自动计算毛利率、净利率、ROE、资产负债率等关键指标，输出 30 个模板占位符键值。
   - 参考 `references/financial_metrics.md` 确保指标定义的准确性。
   - 系统将脚本的实际 JSON 结果捕获为 Python 产物，并通过通用 `auto_data` 传递模板字段，后续 `html_interpreter` 会自动合并。不使用专用 `ratio_data` 状态。

3. **图表生成**：
   - 使用 `execute_skill_script_file` 执行 `scripts/generate_charts.py`，在 `input_artifact_ids` 指定 Step 1 的提取产物 ID。图表和财务比率使用同一份提取结果。
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

5. **交付报告**：
   - 调用 `generate_report`，传入报告标题、需要覆盖的分析维度和建议要求。
   - 报告子代理使用已捕获的脚本结果、图表及模板生成报告；通过证据清单读取实际指标路径，缺失计算只补算缺失部分。
   - 不要自行调用 `html_interpreter`，不要手写图表文件路径或猜测指标值及来源。

6. **完成**：
   - 调用 `terminate` 返回 1-2 句话的简短摘要。
   - 报告会以卡片形式展示在左侧面板，用户点击卡片即可在右侧面板查看完整报告。

## 完整流程示例

```
Step 1: execute_skill_script_file(skill_name="financial-report-analyzer", script_file_name="extract_financials.py", args={"file_path": "/path/to/report.pdf"})
  → 返回 JSON: {"revenue": 10500000000, "net_profit": 1200000000, ...}  （记为 raw_data）

Step 2: execute_skill_script_file(skill_name="financial-report-analyzer", script_file_name="calculate_ratios.py", args=<raw_data>)
  → 返回 30 个模板键值，系统捕获 Python 产物并通过通用 auto_data 传递模板字段

Step 3: execute_skill_script_file(skill_name="financial-report-analyzer", script_file_name="generate_charts.py", args=<raw_data>)
  → 生成图表，系统自动复制到 /images/ 并记录 URL 映射

Step 4: （LLM 自行撰写 7 段深度分析文本）

Step 5: generate_report(instructions="财报分析报告：包含财务摘要、盈利、偿债、效率、现金流、优势和风险")
  → 后端自动合并数据指标 + 图表 URL + 分析文本，渲染完整报告

Step 6: terminate(result="简短摘要")
```

## 资源使用说明

- **脚本**（均通过 `execute_skill_script_file` 执行）：
  - `scripts/extract_financials.py`：接收 `file_path` 参数，读取财报文件（支持 PDF 和文本格式），提取核心财务数据。
  - `scripts/calculate_ratios.py`：计算财务比率，输出 30 个模板占位符键值。系统捕获实际结果和来源，复用通用模板数据流程。
  - `scripts/generate_charts.py`：生成 3 张可视化图表（matplotlib），系统自动处理图片复制。
  - `scripts/fill_template.py`：（备用）接收 `ratio_data`、`chart_paths`、`analysis` 三个参数，读取 HTML 模板并替换所有占位符。正常情况下不需要使用此脚本，因为 html_interpreter 的 template_path 模式会自动完成模板填充。
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
- 对比至少三年的历史数据，以识别趋势。
- `generate_charts.py` 依赖 matplotlib，请确保环境中已安装该库。
