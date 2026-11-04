# financial-report-analyzer

## Overview

`financial-report-analyzer` is a built-in skill for deep analysis of listed-company financial reports such as annual and quarterly reports.

It extracts structured financial data, computes ratios, generates charts, and renders a report-ready financial analysis page.

## Repo path

```text
skills/financial-report-analyzer/
├── SKILL.md
├── scripts/
│   ├── extract_financials.py
│   ├── calculate_ratios.py
│   ├── generate_charts.py
│   └── fill_template.py
├── references/
│   ├── analysis_framework.md
│   └── financial_metrics.md
└── templates/
    ├── report_template.html
    └── report_template.md
```

## When to use it

- analyze annual or quarterly reports
- extract core financial indicators
- calculate profitability and solvency metrics
- generate financial charts
- produce a professional HTML financial report

## Core workflow

1. Run `extract_financials.py` to structure source data.
2. Run `calculate_ratios.py` to compute financial indicators.
3. Run `generate_charts.py` to create report visuals.
4. Write the skill's required narrative analysis sections.
5. Render the final output with `html_interpreter` and the bundled template.

## Important resources

| Resource | Purpose |
|---|---|
| `scripts/extract_financials.py` | Pulls core financial values from report files |
| `scripts/calculate_ratios.py` | Computes key ratio fields for templating |
| `scripts/generate_charts.py` | Generates chart assets used in the report |
| `references/financial_metrics.md` | Defines the financial metrics and formulas |
| `references/analysis_framework.md` | Defines the analysis structure and interpretation logic |
| `templates/report_template.html` | Final HTML delivery template |

## Output expectations

This skill is optimized for structured reporting across:

- profitability
- solvency and risk
- operating efficiency
- cash flow and earnings quality
- advantages and risks
- overall assessment
