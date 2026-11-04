---
name: excel-analyzer
description: >
  Comprehensive Excel/CSV data analysis skill. Provides statistical summaries,
  missing value detection, outlier analysis, correlation matrices, and data visualization
  (bar, line, scatter, pie, box charts). Use when: analyzing data files (.csv, .xlsx, .xls),
  generating descriptive statistics, identifying data quality issues, creating charts,
  or producing data analysis reports with HTML output.
---

# Excel Analyzer

Analyze tabular data files and generate charts.

## Workflow

1. **Load Data** — Read the file with  for automatic stats
2. **Review Stats** — Check missing values, outliers, and distributions
3. **Choose Charts** — See  for chart selection
4. **Generate Charts** — Use  with appropriate parameters
5. **Produce Report** — Call  with complete HTML to display results

## Step 1: Data Analysis

Run the analysis script:



Output includes: shape, dtypes, missing counts/percentages, describe stats, nunique, outlier counts, and correlation matrix.

## Step 2: Chart Generation

Consult  to pick the right chart type, then:



For box plots, use  instead of /.

## Step 3: Report Generation

After analysis and chart creation, generate a complete HTML report via .
Use the  parameter to pass full HTML code with embedded charts (base64) and analysis results.

## Notes

- Always check the analysis output before deciding which charts to create
- For large datasets (>100k rows), consider sampling before charting
- The correlation matrix helps identify variable pairs for scatter plots