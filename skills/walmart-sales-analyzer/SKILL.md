---
name: walmart-sales-analyzer
description: Analyze Walmart sales data to explore trends between store sales and unemployment rates. Generate insightful visualizations and a beautiful HTML report with deep analysis. Suitable for quick insights into the relationship between sales data and macroeconomic factors.
---

# Walmart Sales Data Deep Analyzer

This skill is designed to help users conduct in-depth analysis of Walmart sales data, particularly exploring the relationship between sales and unemployment rates across different stores. It visually presents these trends by generating visualizations with detailed interpretations and professional HTML reports.

## Features

This skill provides the following analysis and visualization features:

1.  **Data Correlation Heatmap**: Displays the correlation between all numerical variables in the dataset and provides a detailed interpretation.
2.  **Sales vs. Unemployment Scatter Plot**: Visually demonstrates the relationship between weekly sales and the unemployment rate, accompanied by a regression line, and deeply analyzes consumption resilience under economic pressure.
3.  **Time Series Trend of Sales and Unemployment for Specific Stores**: Tracks the trends of sales and unemployment rates over time for selected stores to analyze seasonal forces and macro trends.
4.  **Comparison of Average Sales and Average Unemployment Across Stores**: Compares the average sales performance of different stores with local average unemployment rates to provide suggestions for regional operational strategies.
5.  **HTML Deep Analysis Report Generation**: Automatically integrates all charts into a beautiful, responsive HTML report that includes detailed analysis conclusions and business recommendations.

## Usage

To use this skill, you need to provide a CSV file containing Walmart sales data. The file should contain at least the following columns: `Store` (Store ID), `Date` (Date), `Weekly_Sales` (Weekly Sales), `Unemployment` (Unemployment Rate).

## Core Workflow

1. **Check Uploaded File**: First, verify that a valid Walmart Sales CSV file was provided.
2. **Execute Analysis Script**: Use the `run_skill_script` tool with `script_file_name="generate_html_report.py"`. Pass the CSV file path to the `input_file` argument in the `args` parameter.
   - Example: `{"skill_name": "walmart-sales-analyzer", "script_file_name": "generate_html_report.py", "args": {"input_file": "/path/to/Walmart_Sales.csv", "output_dir": "."}}`
   - *Note: This script automatically generates all required charts (`correlation_heatmap.png`, `sales_vs_unemployment_scatter.png`, etc.) and the base report.*
3. **Present Report**: To present the results to the user via the DB-GPT UI, you must use the `html_interpreter` tool. Provide the `template_path` (`walmart-sales-analyzer/templates/report_template.html`) and the necessary text data to render the report interactively. You MUST fill in ALL the placeholders dynamically based on your analysis (including ALL section titles, report titles, and analysis content, otherwise they will render as 'NA') and ensure they are translated to the user's language.
   - Example `data` payload:
     {
       "LANG": "en",
       "REPORT_TITLE": "Walmart Sales Deep Analysis Report",
       "REPORT_SUBTITLE": "Based on macroeconomic indicators and store performance",
       "EXEC_SUMMARY_TITLE": "Executive Summary",
       "EXEC_SUMMARY_CONTENT": "<p>Your detailed summary...</p>",
       "SECTION_1_TITLE": "1. Multi-dimensional Correlation Analysis",
       "SECTION_1_ANALYSIS": "<h3><span class=\"tag\">Insights</span> Variable relationships</h3><ul><li>...</li></ul>",
       "SECTION_2_TITLE": "2. Sales vs Unemployment Regression",
       "SECTION_2_ANALYSIS": "<h3><span class=\"tag\">Deep Dive</span> Resilience under pressure</h3><p>...</p>",
       "SECTION_3_TITLE": "3. Dynamic Trends Tracking",
       "SECTION_3_ANALYSIS": "<h3><span class=\"tag\">Trends</span> Seasonal vs Macro</h3><p>...</p>",
       "SECTION_4_TITLE": "4. Store Performance Comparison",
       "SECTION_4_ANALYSIS": "<h3><span class=\"tag\">Strategy</span> Regional operations</h3><p>...</p>",
       "CONCLUSION_TITLE": "Final Conclusions & Recommendations",
       "CONCLUSION_CONTENT": "<ol><li>...</li></ol>",
       "FOOTER_TEXT": "Deep Data-Driven Decisions"
     }
     ```
4. **Complete Task**: Call `terminate` with a final answer summarizing your actions.

### Script List

*   `scripts/generate_html_report.py`: **Recommended**, generates an HTML report containing all charts and deep analysis with one click.
*   `scripts/generate_correlation_heatmap.py`: Generates a data correlation heatmap.
*   `scripts/generate_sales_unemployment_scatter.py`: Generates a scatter plot of sales vs. unemployment rate.
*   `scripts/generate_time_series_trend.py`: Generates a time series trend chart for a specific store.
*   `scripts/generate_store_avg_comparison.py`: Generates a comparison chart of average values across stores.

### Templates

*   `templates/report_template.html`: HTML style template used to generate the deep analysis report.

## Important Notes

*   **Language Requirement: You MUST ensure that your output language exactly matches the language used by the user in their input/request.**
*   All charts support multi-language display.
*   The report template uses a responsive design suitable for viewing on different devices and provides detailed analysis interpretations and business suggestions.
