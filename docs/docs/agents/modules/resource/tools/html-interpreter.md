# html_interpreter

## Overview

`html_interpreter` renders HTML as an interactive web report.

It is the final presentation tool for web pages, HTML reports, dashboards, and skill-based report delivery.

## Parameters

### Direct HTML mode

```json
{
  "html": "<html>...</html>",
  "title": "Report"
}
```

### Template mode

```json
{
  "template_path": "skill/templates/report_template.html",
  "data": {
    "KEY": "value"
  }
}
```

### File mode

```json
{
  "file_path": "/absolute/path/to/file.html",
  "title": "Report"
}
```

## What it does

- renders complete HTML directly
- supports template placeholder replacement
- can merge generated data and images into reports
- can render from an existing HTML file

## When to use it

- final HTML report generation
- interactive webpage delivery
- template-based report output from skills

## Example

```json
{
  "template_path": "financial-report-analyzer/templates/report_template.html",
  "data": {
    "REPORT_TITLE": "Q2 Financial Review",
    "EXEC_SUMMARY": "Revenue increased while gross margin remained stable."
  }
}
```

## Notes

- this should be the final rendering step for HTML-style outputs
- do not rely on `code_interpreter` alone for final HTML delivery
- template mode is especially useful for skill-based reporting workflows
