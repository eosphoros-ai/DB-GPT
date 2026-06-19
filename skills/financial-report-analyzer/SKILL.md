---
name: financial-report-analyzer
description: Deep analysis of listed-company financial reports (annual, quarterly). Automatically extracts key financial metrics, calculates core ratios, generates visualizations, and produces professional analysis reports with industry context.
---

# Financial Report Analyzer

This skill helps DB-GPT systematically analyze listed-company financial reports by extracting core data, calculating financial ratios, generating visualizations, and combining business context to produce high-quality financial analysis reports.

## Core Workflow

1. **Data extraction and structuring**:
   - Use `execute_skill_script_file` to run `scripts/extract_financials.py` with the report file path (`file_path` parameter) to automatically extract revenue, net profit, assets, liabilities, and other core figures.
   - The script supports PDF files (via pdfplumber) and plain text files, returning structured JSON.

2. **Financial ratio calculation**:
   - Use `execute_skill_script_file` to run `scripts/calculate_ratios.py` with the JSON from Step 1.
   - Automatically calculates gross margin, net margin, ROE, debt-to-asset ratio, and other key metrics, outputting 30 template placeholder key-value pairs.
   - Refer to `references/financial_metrics.md` to ensure metric definitions are accurate.
   - **The system automatically saves the returned JSON** (`react_state["ratio_data"]`); `html_interpreter` merges it later.

3. **Chart generation**:
   - Use `execute_skill_script_file` to run `scripts/generate_charts.py` with the JSON from Step 1.
   - Automatically generates 3 visualizations:
     - `financial_overview.png`: grouped bar chart of key financial metrics
     - `profitability.png`: horizontal bar chart of profitability metrics
     - `asset_structure.png`: donut chart of asset structure
   - **The system automatically copies images to the static directory and records URL mappings** (`react_state["image_url_map"]`); `html_interpreter` merges them later.

4. **In-depth analysis**:
   - Follow the framework in `references/analysis_framework.md` to analyze profitability quality, solvency risk, operating efficiency, and cash flow.
   - Combine with the "Management Discussion and Analysis" section to explain the main drivers of performance changes.
   - Write the following 7 analysis sections:
     - `PROFITABILITY_ANALYSIS`: profitability analysis
     - `SOLVENCY_ANALYSIS`: solvency and risk analysis
     - `EFFICIENCY_ANALYSIS`: operating efficiency analysis
     - `CASHFLOW_ANALYSIS`: cash flow and earnings quality analysis
     - `ADVANTAGES_LIST`: core strengths list (HTML `<li>` format)
     - `RISKS_LIST`: key risks list (HTML `<li>` format)
     - `OVERALL_ASSESSMENT`: overall assessment

5. **Render report**:
   - Call `html_interpreter` using `template_path` mode:
     ```json
     {
       "template_path": "financial-report-analyzer/templates/report_template.html",
       "data": {
         "PROFITABILITY_ANALYSIS": "LLM-written profitability analysis...",
         "SOLVENCY_ANALYSIS": "LLM-written solvency analysis...",
         "EFFICIENCY_ANALYSIS": "LLM-written operating efficiency analysis...",
         "CASHFLOW_ANALYSIS": "LLM-written cash flow analysis...",
         "ADVANTAGES_LIST": "<li>Strength 1</li><li>Strength 2</li>",
         "RISKS_LIST": "<li>Risk 1</li><li>Risk 2</li>",
         "OVERALL_ASSESSMENT": "LLM-written overall assessment..."
       },
       "title": "XX Company 2023 Annual Financial Report Analysis"
     }
     ```
   - **Important**: The `data` dict should only contain your 7 analysis sections! The backend automatically merges:
     - 30 data metrics from Step 2 (COMPANY_NAME, REVENUE, NET_PROFIT, etc.)
     - Chart URLs from Step 3 (CHART_FINANCIAL_OVERVIEW, CHART_PROFITABILITY, CHART_ASSET_STRUCTURE)
   - **Never** include data metrics or chart paths in `data`; oversized JSON may be truncated.

6. **Complete**:
   - Call `terminate` with a 1–2 sentence summary.
   - The report appears as a card in the left panel; clicking it opens the full report in the right panel.

## Full Workflow Example

```
Step 1: execute_skill_script_file(skill_name="financial-report-analyzer", script_file_name="extract_financials.py", args={"file_path": "/path/to/report.pdf"})
  -> Returns JSON: {"revenue": 10500000000, "net_profit": 1200000000, ...}  (save as raw_data)

Step 2: execute_skill_script_file(skill_name="financial-report-analyzer", script_file_name="calculate_ratios.py", args=<raw_data>)
  -> Returns 30 template key-values; system records to react_state["ratio_data"]

Step 3: execute_skill_script_file(skill_name="financial-report-analyzer", script_file_name="generate_charts.py", args=<raw_data>)
  -> Generates charts; system copies to /images/ and records URL mappings

Step 4: (LLM writes 7 in-depth analysis sections)

Step 5: html_interpreter(template_path="financial-report-analyzer/templates/report_template.html", data={only the 7 analysis sections}, title="Report title")
  -> Backend merges data metrics + chart URLs + analysis text and renders the full report

Step 6: terminate(result="Brief summary")
```

## Resource Usage

- **Scripts** (all run via `execute_skill_script_file`):
  - `scripts/extract_financials.py`: Accepts `file_path`, reads the report (PDF or text), extracts core financial data.
  - `scripts/calculate_ratios.py`: Calculates financial ratios, outputs 30 template placeholder key-values. System records results automatically.
  - `scripts/generate_charts.py`: Generates 3 visualizations (matplotlib); system handles image copying.
  - `scripts/fill_template.py`: (Fallback) Accepts `ratio_data`, `chart_paths`, and `analysis`, reads the HTML template and replaces all placeholders. Normally not needed because `html_interpreter` `template_path` mode handles template filling.
- **References**:
  - `references/financial_metrics.md`: Formula definitions.
  - `references/analysis_framework.md`: Analysis logic.
- **Templates**:
  - `templates/report_template.html`: Final HTML report template (**must be followed strictly**; do not remove sections or change table structure). Read and filled via `html_interpreter` `template_path`.
  - `templates/report_template.md`: Markdown version for structural reference only.

## Notes

- **Always use `execute_skill_script_file`** to run scripts (not `shell_interpreter`), because it handles image copying and data recording automatically.
- Extraction may be affected by layout; verify key figures manually before calculating ratios.
- Always consider non-recurring items when assessing core business profitability.
- Compare at least three years of historical data to identify trends.
- `generate_charts.py` depends on matplotlib; ensure it is installed in the environment.
