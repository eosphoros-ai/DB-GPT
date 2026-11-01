---
name: business-report
description: This skill should be used when a user asks for an analysis report, a business review, a post-mortem, or any structured multi-section HTML deliverable over already-executed SQL/Python analysis. Trigger keywords include "分析报告", "复盘报告", "经营报告", "生成报告", "report", "analysis report", "business review", "post-mortem", "html report".
---

# Traceable Business Report (template-driven)

Render a multi-section analysis report **from a template plus structured data**, so every
number in the report is resolved by the backend from a captured artifact result instead of
being typed by the model. This is the default path for report generation: prefer it over
hand-writing HTML.

## Why

Hand-written report HTML is validated against the captured artifacts after the fact: a
number the model remembers (or copies from an earlier report) does not exist in any
artifact, the render is rejected, and repairing dozens of HTML numbers is slow. With this
template the model only supplies **pointers** (`artifact_id` + result path); the backend
resolves and formats the value, and a wrong pointer fails immediately with the exact
selector to fix.

## Tool call

```json
{
  "template_path": "business-report/templates/business_report.html",
  "title": "Olist 巴西站经营复盘报告",
  "data": {
    "REPORT_SPEC": { "...": "see below" }
  }
}
```

`data.REPORT_SPEC` may be a JSON object or a JSON string. Do not pass `html` together with
`template_path`. **Prefer the object form**: a spec hand-escaped into a JSON string is a
frequent, fatal mistake — one wrong escape makes the whole call unparsable and nothing
renders.

```json
{
  "template_path": "business-report/templates/business_report.html",
  "title": "Olist 巴西站经营复盘报告",
  "data": {"REPORT_SPEC": {"title": "…"}}
}
```

## Reference nodes (the only way to put a value in the report)

Every value is a reference node; the backend replaces it with the captured value and binds
the rendered `<span>` to the producing artifact:

```json
{"artifact_id": "sql-f6f8810...", "path": ["rows", 0, "gmv"], "format": "money2"}
{"artifact_id": "sql-29da2e3...", "path": ["rows", 0, "product_gmv"], "format": "money2"}
{"artifact_id": "sql-7de826c...", "kind": "sql", "quote": "r.score <= 2"}
{"artifact_id": "reference-e7ae093...", "format": "text"}
```

- `field` names a key of a **Python** artifact result (`result_selector_examples` in the
  manifest lists them). For a SQL metric use `path`
  `["rows", <index>, "<column>"]` with a name from the manifest `columns` (the result is
  `{"columns": [...], "rows": [...]}`). A SQL selector that names a `field` is refused with
  `RESULT_SELECTOR_INVALID`, which lists the available keys.
- Python artifacts must expose their metrics as a JSON result field (for example
  `{"RESULT_JSON": "{...}"}`); reference `{"artifact_id": "python-…", "field":
  "RESULT_JSON", "path": ["driver_analysis", "items", 0, "corr"]}`.
- `format`: `money2`, `num2`, `num1`, `int`, `pct` (adds `%`), `text`/`raw`.
- Never inline a literal number. Prose numbers must also be reference nodes: **a section
  whose text contains digits must carry evidence** (a KPI ref, a table built from
  `artifact_id` + `columns`, a chart, or bound values in `intro`/`bullets`), otherwise the
  render is refused before the browser with `REPORT_TEMPLATE_SPEC_INVALID`, which names the
  section and lists the available artifacts.
- Layout labels (headings, table headers, section titles) must contain no digits; use
  reference nodes for anything numeric, including threshold labels.
- Get real artifact IDs and result fields from `report_evidence_manifest` before writing
  the spec.
- Start with `artifact_types=["sql", "python", "chart"]`, then select the needed
  `artifact_ids` with `detail=true` (at most twelve per call). Read the governing KB
  slices separately. A catalog contains identifiers and columns, not the results;
  read a persisted output when the preview is truncated. A new report agent receives
  its own first catalog even if the lead already read the same version.
- Numeric preflight reports all unbound literals together, with spec JSON paths and
  SQL/Python producer candidates. Correct every listed value; adding one KPI to the
  section does not bind the remaining prose. Use a producer table plus a qualitative
  summary when per-value prose would be too long. Uncaptured derived totals require
  a captured calculation or a summary without that number.

## REPORT_SPEC shape

```jsonc
{
  "title": "…", "subtitle": "…", "scope": "分析窗口 ｜ 口径 ｜ 货币",
  "kpis": [{"label": "商品 GMV", "unit": "R$", "hint": "SUM(price)", "ref": <ref>}],
  "sections": [
    {"heading": "一、总体经营表现", "kpis": [...], "intro": [[part, …]], "table": {...},
     "chart": {...}, "bullets": [[part, …]], "list": [[part, …]],
     "recommendations": [{"badge": "P0", "cls": "p0", "title": "…",
                          "lines": [{"label": "依据", "parts": [part, …]}]}],
     "note": {"label": "口径说明", "parts": [part, …], "ref": <ref>}}
  ]
}
```

- `<part>` is either a plain string (no digits) or a reference node.
- `table`: **name the producer and the columns; the engine expands the rows.** Never write
  one reference node per cell — a 10x5 table would cost ~5,500 characters and overrun the
  model output limit.

  ```jsonc
  {"artifact_id": "sql-f6f88101…", "label": "品类明细", "limit": 10,
   "columns": ["category", {"field": "gmv", "label": "GMV", "format": "money2"}, "orders_cnt"]}
  ```

  A `columns` entry is a field name (result key, also used as the label) or
  `{"field", "label", "format"}`. `limit`/`offset` window the artifact rows; each expanded
  cell carries its own `path` selector. The explicit
  `"rows": [[part, …], …]` form is only for cells that no artifact row can produce.
- `chart`: only when a real ChartArtifact exists. Image chart:
  `{"refs": ["<sql-id>", "<chart-id>"], "img": "artifact://….json", "caption": "…"}`.
  ECharts host (the engine then needs one producer with a selector and a target id):
  `{"refs": ["<sql-id>", "<chart-id>"], "renderer": "echarts", "chart_id": "<chart-id>",
   "host_id": "chart-1", "producer": {"artifact_id": "<python-id>", "field": "CHART_DATA_JSON"},
  "caption": "…"}`. `<figure>`/`<img>` are chart hosts and must be covered by a chart artifact.
- `recommendations` produce `<li>` items; give at least as many as the user requested, and
  keep the section heading containing “建议”.
- `note.ref`: bind the knowledge-space slice actually used for the methodology statement.
  A whole-page binding does not count.

## Chart configuration

Charts are not limited to the automatic line/bar/scatter choice. Use `chart.option`
for a full JSON ECharts configuration, including any built-in series type, composed
series, dataset/encode, multiple coordinates and zoom controls. For example:

```json
{"caption":"Composition","producer":{"artifact_id":"sql-real","path":[]},
 "option":{"series":[{"type":"pie","radius":["40%","70%"],
 "encode":{"itemName":"actual_category","value":"actual_measure"}}]}}
```

The engine injects the producer's captured rows/columns as the default dataset.
For structured charts, select `series.data`, `nodes`, `links`, `dataset.source`,
or individual data values using `{artifact_id,field,path}` references. Do not
inline observed data. Use captured tree/graph/boxplot/candlestick structures;
request only a missing conversion via request_report_calculation when necessary.
Map charts can set `maps={mapName:{artifact_id,field,path}}` to register captured
GeoJSON, then use that mapName in the option. All input IDs, selectors, resolved
options and geography are captured and checked against the rendered chart.
No chart-type whitelist is imposed; JavaScript callbacks and extra plugins are
not executable through JSON options. Captured Python chart images remain supported.
Placeholder-based skill templates use `data.REPORT_CHARTS=[<chart>, ...]` for the
same renderer, independently of their preset chart layout.

## Output budget

The whole spec travels in **one** tool-call argument, and the model output limit is about
8k tokens: a payload that is cut off cannot be parsed, so the render never even starts.
Keep the spec small — tables by `artifact_id` + `columns` (never per-cell references),
`limit` instead of pasted rows, short `intro`/`bullets`, and no repeated prose. If a
render result says the arguments were cut off by the output limit, shrink the spec
instead of resending it.

A long report may be built in pieces. Send the first part as
`data={"REPORT_SPEC": {...}}`, then extend the saved spec with
`data={"REPORT_SPEC_APPEND": {...}}` (call it again with `retry_saved=true` when a render
was already attempted): `sections` and `kpis` are **appended**, every other key
**overwrites**. The engine stores the merged spec, so never resend a part you already
sent, and finish with the required recommendation section.

KPI values must use `ref`, not `value`. Paragraphs use `sections[].intro` as arrays
of parts; recommendations belong to `sections[].recommendations` and contain a
`title` and `lines[].parts`. Unknown keys such as `placeholders`, `sections[].parts`
or top-level `recommendations` are rejected with a JSON path before rendering.
`REPORT_SPEC` repairs retain unspecified root fields; an explicitly supplied
`sections` or `kpis` replaces that complete list. A root field set to `null` is
removed, including an unsupported field from a previous invalid spec.
`REPORT_SPEC_APPEND` extends those
lists and does not insert an identical fragment twice.
Preflight (6), document assembly (6), actual render validation (3), and invalid calls
(3) have separate budgets and a total cap of 18 report calls. Pre-render spec/selector
failures never spend render attempts. Progress compares the merged spec and error;
retry_saved and template HTML length are not progress signals. Fix all returned
JSON paths together. An identical input with the same failure stops retries.

The report agent's tool schema is generated from this same spec model. Captured
charts belong only in sections[].chart: `{"refs":["real-chart-id"],"caption":"…"}`.
Image URLs are resolved from the captured chart output. Native figures use the
existing AutoChart frontend. ECharts still uses its existing reviewed template and
bootstrap; an empty div without rendering code is not a chart.

If an essential derived result is truly missing, call request_report_calculation
with its name, formula and real SQL/Python source_artifact_ids, then terminate.
The lead computes only that missing result with code_interpreter using the injected
REPORT_CALCULATION_INPUTS JSON file and prints JSON for normal artifact capture.
Resume the saved spec and bind the new Python artifact; never rerun full analysis.

For an authored recommendation target, a reference node in recommendation lines
may add `"proposal":"reduce the rate to 5%"`. The engine labels it explicitly as
a proposed, unobserved target. The node's artifact_id and field/path still select
the real rationale; proposal is forbidden in KPI and observed-value paragraphs.

On failure, a labelled draft can preview independently validated blocks through
the existing HTML preview. It does not create a report_id or indicate completion.
Use status=completed to determine success, never the mere presence of draft HTML.

## Failure handling

For a large nested result, request only its relevant subtree with
`report_evidence_manifest(artifact_ids=["real-id"], detail=true,
selectors={"real-id":{"field":"CHART_DATA_JSON","path":["stats_table"]}})`.
Selector examples also name fields inside captured JSON strings; truncated previews
are not evidence that a result is missing. This reuses the manifest and result
selector, and never reexecutes analysis.

Nested Python tables may use the same field/path selector on the table node,
for example `{"artifact_id":"python-id","field":"CHART_DATA_JSON",
"path":["stats_table"],"columns":["actual_column"]}`. Prefer an object with
rows and columns. The engine expands both SQL and Python rows and retains the
complete selector for every cell; do not paste per-cell values into the spec.

The render error names the exact `artifact_id`, selector and container. Fix the **spec**
(`data.REPORT_SPEC`), then call `retry_saved=true` with the corrected data only — never
resend full HTML and never rerun completed analysis.
