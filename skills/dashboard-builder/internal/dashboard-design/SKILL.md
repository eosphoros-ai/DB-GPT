---
name: dashboard-design
description: Internal visual references for dashboard-builder. Select a dashboard style for the user's data while preserving its layout, colors and readable chart hierarchy.
version: 1.0.0
author: DB-GPT Dashboard Lab
---

# Dashboard Design

This is an internal skill used by dashboard-builder, not a separate user task.
Use the selected reference to guide the dashboard's appearance. It never supplies
data, SQL, filter values, targets or claims about the selected source.

- When the user selects a gallery style, its reference and these instructions
  are already loaded. Do not reload the skill or scan the other references.
- Otherwise, if the user requests a particular visual style, call
  `load_dashboard_style` without a selection to list the available references,
  then load the matching selection. Match business intent and data shape:
  a command center emphasizes a large-screen overview; logistics emphasizes
  delivery/cost comparisons; marketing emphasizes campaign/channel outcomes.
  Do not make users choose a style for a simple request with no visual preference.
- Keep the selected reference's slot ids and visual hierarchy. Adapt its suggested
  titles, metrics and chart kinds to actual fields; explain substitutions in the
  plan. Never invent appointments, revenue, targets or geography to fit a design.
- Use Top 10 for ordinary category rankings and label that scope. Keep complete
  time ranges for trends; choose a row budget covering all dates and series
  (default 1000, at most 5000), or use an appropriate coarser time grain. Label
  bounded detail-table ranges. KPI totals must cover all relevant source rows.
- Plan first and wait for confirmation using dashboard-builder. Generate actual
  queries with the existing Dashboard tools; their data validation still applies.
  Report the resulting dashboard through those tools so the homepage can open it.
- Read only the selected style's extra guidance. Do not load all styles, duplicate
  the data schema, dump a complete reference into the answer, or produce a second
  HTML report alongside the dashboard.

The eight active gallery references are listed in [the reference index](references/index.md).
Each reference separates visual configuration from data queries. To extend a
style, edit its reference and guidance here rather than adding a generation flow.
