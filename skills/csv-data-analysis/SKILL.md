---
name: csv-data-analysis
description: This skill should be used when users need to analyze CSV or Excel files, understand data patterns, generate statistical summaries, or create data visualizations. Trigger keywords include "analyze CSV", "analyze Excel", "data analysis", "CSV analysis", "Excel analysis", "data statistics", "generate charts", "data visualization".
---

# Intelligent Deep Data Analysis Tool

The Data Analysis Tool is an AI-powered deep automated data exploration tool built on frontend visualization technologies (ECharts + Tailwind CSS). It rapidly extracts statistical features, data quality metrics, numerical distributions, outlier detection, categorical information, correlations, rankings, and time series trends. The latter half of the report supplements these with anomaly overviews, attribution clues, and summary recommendations, producing highly polished and interactive web-based analysis reports. Supported formats include CSV, Excel (.xlsx/.xls), and TSV.

The report follows a structure of "foundational data analysis in the first half, anomaly detection and attribution enhancement in the second half." Core sections include: Executive Summary, Data Overview & Quality Check, Numerical Distribution Features, Feature Analysis & Structural Analysis, Relationship Analysis & Anomaly Identification, Data Anomaly Overview, Attribution Analysis Module, Analysis Results & Statistical Details, Root Cause Inference / Conclusions / Recommendations.

## Core Workflow (Required Reading for LLMs)

As an AI assistant, when a user uploads a CSV or Excel file and requests analysis, you must strictly follow these two steps:

### Step 1: Extract Data Features (Execute Script)

Use the `execute_skill_script_file` tool to run `csv_analyzer.py`, passing in the data file path (supports .csv, .xlsx, .xls, .tsv formats).

**Tool call parameter example:**
```json
{
  "skill_name": "csv-data-analysis",
  "script_file_name": "csv_analyzer.py",
  "args": {"input_file": "/path/to/data.csv or /path/to/data.xlsx"}
}
```

**Script return explanation:**
The script returns a large block of `text` content containing two parts:
1. **[Statistical Summary]**: For you to read and understand the dataset's basic characteristics, distributions, correlations, and categorical composition.
2. **[Marker-wrapped data blocks]**: The script output contains marker data blocks in the format `###KEY_START###...###KEY_END###`. The backend automatically captures and injects these into the template — **you do not need to handle or pass this content**.

### Step 2: Generate Insights & Display Report (Inject into Template)

Read the "Statistical Summary" obtained in Step 1, and reason about the business significance or patterns behind the data. Then use the `html_interpreter` tool to load the template and inject data.

**Critical Rules (Must Follow):**

1. **You must set `template_path`** to `csv-data-analysis/templates/report_template.html`. The template has built-in complete ECharts rendering JavaScript code and all section titles and footer text. You only need to fill in 9 content placeholders via the `data` parameter. **Never write or modify any JavaScript chart rendering code yourself.**

2. **Marker data blocks are automatically injected by the backend** — you must not pass them in `data`. The backend automatically extracts content from `###KEY_START###...###KEY_END###` markers in the script output and injects it into the template; in this skill, this is primarily `CHART_DATA_JSON`.

3. **`*_INSIGHTS`, `EXEC_SUMMARY`, and `CONCLUSIONS`** must use HTML formatting (e.g., `<p>`, `<ul>`, `<li>`, `<strong>`, `<ol>`) to ensure proper layout. These are deep business insights you write based on the statistical summary.

4. **The output language must match the user's input language.** Pass the `LANG` placeholder (`"en"`) so that the template's section titles, labels, and footer text are displayed in English.

5. **Pass exactly 9 placeholders — no more, no less.** Auto-injected marker fields like `CHART_DATA_JSON` are handled by the backend and should not be passed by you. The template already hardcodes all section titles (Distribution Analysis, Correlation Analysis, etc.), insight box titles ("Insights"), and footer text — you do not need to pass these.

6. **Insight content must be substantive.** Each insight module should cover 4 layers of information: `observation`, `possible causes`, `business impact`, and `action recommendations`. Do not merely restate statistical values or write only a few vague conclusions.

7. **Foundational analysis first, attribution as an enhancement module.** The first half of the report must focus on analyzing the data features of the CSV itself, including numerical distributions, categorical structures, outliers, correlations, ranking patterns, etc., and should incorporate chart interpretations wherever possible. "Data Anomaly Overview," "Attribution Analysis," and "Root Cause Inference" should appear in the second half as enhancement modules — the entire report must not consist solely of attribution content.

**`html_interpreter` call example:**
```json
{
  "template_path": "csv-data-analysis/templates/report_template.html",
  "data": {
    "LANG": "en",
    "REPORT_TITLE": "Sales Dataset Deep Analysis Report",
    "REPORT_SUBTITLE": "Multi-dimensional Data Feature & Business Insight Mining",
    "EXEC_SUMMARY": "<p>This dataset contains 1,000 rows and 5 columns with good data completeness. Key findings include:</p><ul><li><strong>Audience Distribution:</strong> Primarily concentrated in the 25-35 age group...</li></ul>",
    "DISTRIBUTION_INSIGHTS": "<p>The numerical distribution chart reveals that Metric A exhibits a pronounced right-skewed distribution, suggesting...</p>",
    "CORRELATION_INSIGHTS": "<p>The heatmap between variables reveals strong positive correlations, particularly between..., which implies...</p>",
    "CATEGORICAL_INSIGHTS": "<p>Category proportions show that Beijing and Shanghai account for over 50% of the 'City' field.</p>",
    "TIME_SERIES_INSIGHTS": "<p>The time series trend indicates a significant seasonal uptick toward year-end.</p>",
    "CONCLUSIONS": "<p>Based on the comprehensive multi-dimensional analysis, the data exhibits clear structural features and patterns.</p><h3>Recommendations</h3><ul><li>Regularly monitor missing value ratios...</li><li>Focus on high-growth market segments...</li></ul>"
  }
}
```

> **Strictly Prohibited:**
> - Do NOT pass `CHART_DATA_JSON` or any auto-injected marker fields in `data` (handled automatically by the backend)
> - Do NOT add any JavaScript code in `data`
> - Do NOT omit the `template_path` parameter (omitting template_path will prevent charts from rendering!)
> - Do NOT return static PNG images — this tool has been fully upgraded to ECharts dynamic frontend rendering
> - Do NOT pass non-existent placeholders (the template only has the following 9 text placeholders + 1 auto-injected CHART_DATA_JSON; other names will be ignored)

## Placeholder Reference (9 total, passed by LLM via data)

The placeholders you need to fill in the template are as follows:

| Placeholder | Type | Required | Description |
|---|---|---|---|
| `LANG` | Text | Yes | Report language: set to `"en"` for English section titles, labels, and footer text |
| `REPORT_TITLE` | Text | Yes | Report title, e.g., "Sales Dataset Deep Analysis Report" |
| `REPORT_SUBTITLE` | Text | Yes | Report subtitle, e.g., "Multi-dimensional Data Feature & Business Insight Mining" |
| `EXEC_SUMMARY` | HTML | Yes | Executive summary: overview of data scale, key findings, and conclusion preview |
| `DISTRIBUTION_INSIGHTS` | HTML | Yes | Numerical distribution feature interpretation: skewness, volatility, quantile ranges, dispersion |
| `CORRELATION_INSIGHTS` | HTML | Yes | Relationship analysis & anomaly identification interpretation: correlations, linkages, outliers, structural relationships |
| `CATEGORICAL_INSIGHTS` | HTML | Yes | Feature analysis & structural analysis interpretation: categorical structure, concentration, rankings, and group characteristics |
| `TIME_SERIES_INSIGHTS` | HTML | Yes | Supplementary interpretation for the data anomaly overview section: discuss trends if time columns exist; discuss stratification differences and anomaly patterns if no time columns |
| `CONCLUSIONS` | HTML | Yes | Root cause inference, conclusions & recommendations body; must distinguish between "data evidence" and "reasonable speculation" |

> **Note:** `csv_analyzer.py` includes `###CHART_DATA_JSON_START###...###CHART_DATA_JSON_END###` marker data blocks in its output. The backend automatically extracts and injects these into the template — they should not be passed in `data`. All section titles in the template (e.g., "Distribution Analysis", "Correlation Analysis", "Conclusions & Recommendations"), insight box titles ("Insights"), and footer text are hardcoded in English in the HTML — they do not need to be passed via placeholders.

## Why Choose This Tool?

1. **Fast & Lightweight**: No more slow Python plotting and bulk PNG generation — only core JSON data is transmitted.
2. **Modern Interactive Layout**: Fully integrated with Tailwind CSS responsive layouts and Apache ECharts smooth animated interactions.
3. **Deep Business Insights**: By separating machine-driven data extraction from LLM-driven logical reasoning, this tool produces highly valuable data analysis reports.

## File Structure

```
csv-data-analysis/
├── SKILL.md                        # The skill guide you are currently reading
├── scripts/
│   └── csv_analyzer.py             # Python analysis engine (supports CSV/Excel/TSV, lightweight, no graphics dependencies)
└── templates/
    └── report_template.html        # Responsive ECharts report template (with built-in rendering logic and hardcoded titles)
```
