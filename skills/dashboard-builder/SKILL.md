---
name: dashboard-builder
description: Plan, generate, repair, and safely revise reusable dashboards from a selected database or registered multi-file tabular dataset through the DB-GPT Dashboard tools.
version: 1.1.2
author: DB-GPT Dashboard Lab
allowed-tools: sql_query load_dashboard_style load_dashboard_draft resolve_dashboard_reference plan_dashboard revise_dashboard_plan create_dashboard_draft repair_dashboard_draft modify_dashboard_draft propose_dashboard_change question terminate
---

# Dashboard Builder

Use this skill when the user asks to create, revise, or repair a reusable data
dashboard from the database selected in the data assistant. A bounded CSV/Excel
upload group that DB-GPT registered as one SQLite data source counts as the
selected database; use SQL tools against that durable source.

This skill **orchestrates** the workflow. Deterministic tools own persistence,
SQL validation, query execution, revision checks, and publication safety. Do not
reimplement those responsibilities in free-form reasoning or scripts.

## Preconditions

- A database must be selected in the data assistant. A registered multi-file
  upload dataset satisfies this condition.
- Use only the selected database. Never invent another data source.
- If no database is selected, ask the user to select one and stop.
- Respond in the same language as the user.

## New dashboard: plan first

Visual styles are owned by the internal
[dashboard-design skill](internal/dashboard-design/SKILL.md). Gallery selections
load only that skill and the chosen reference automatically. Keep its layout and
palette while adapting the analytical content to actual data. When a user asks
for a style without choosing a gallery item, pass its exact name to
`load_dashboard_style` before planning; list styles only when you need to find
an appropriate reference. No style selection is needed
for a small dashboard with no requested visual preference. Internal chart, filter,
collaboration and design guidance lives under `internal/`; these are not separate
homepage skills.

1. Use `sql_query` only for the minimum read-only discovery needed to learn:
   table relationships, field types, data grain, date range, and useful category
   values. Use at most eight discovery queries in a planning turn. If validation
   feedback already names the incorrect plan fields, fix the plan directly instead
   of starting another round of discovery.
   Use the server's temporal discovery evidence for every candidate time column:
   storage type, actual sample values, inferred format and source distinct count.
   Raw distinct dates and distinct calendar months are different grains. Use the
   observed format to choose dialect-appropriate parsing, keeping the full year;
   do not assume a text date is accepted by a native date function. Ambiguous,
   mixed, unavailable or sampled evidence is not an exact source-wide fact.
   Reuse already observed facts instead of querying the same counts or date
   coverage again. Combine independent aggregates at the same table/grain in
   one discovery SELECT where possible. Stop discovery once the metric fields,
   grain, relationships and required filter values are understood. Do not run
   each future widget's ranking or trend query merely to preview its numbers;
   those queries will be generated and validated after confirmation. Still
   investigate unknown semantics, join cardinality, missing data and chart point
   counts when they affect the plan; this is not permission to guess.
2. When the selected source came from multiple uploaded files, inventory every
   source table before planning:
   - record its source file/sheet, row count, columns, likely grain, nulls, and
     duplicate-key counts;
   - inspect `__dbgpt_dataset_manifest` for provenance;
   - treat `__dbgpt_relationship_candidates` only as hints, never as confirmed
     joins;
   - verify candidate keys with distinct-key overlap, unmatched rows, and
     one-to-one/one-to-many/many-to-many cardinality checks;
   - never concatenate tables merely because columns match, and never join two
     fact tables at raw grain when that would multiply measures. Aggregate the
     child side to the intended dashboard grain first.
3. Keep the user's requested scope: one component per listed analytical item;
   do not add extra KPI cards or filters. For broad requests start with 3–4 core
   widgets. Add filters only when requested or necessary for the stated decision.
   If the requested period has no rows and an empty table is intended, set that
   table's `expected_data_points` to 0, preserving the exact requested period.
   Call `plan_dashboard` with exactly one `plan` argument containing a SQL-free
   plan object (a JSON-encoded string is also accepted). Follow the generated
   DashboardPlan validation shape in the registered tool inventory, including:
   - business theme and intended decision;
   - metric names as a string array; describe their meaning in the business text;
   - dimensions as a string array and an appropriate grain;
   - filters with real default values and options discovered from the data;
   - widgets with stable ids, type, title, business question, metric, and
     dimensions.
   If a visual reference is selected, use its slot ids exactly once; the tools
   preserve its layout and palette. Omit repeated layout hints, visual rationale
   and unused default fields. Keep metric definitions concise while retaining
   the requested population, time period, grain and data limitations. Otherwise
   use individual widget width/height hints and business layout rationale.
   Do not add `layout_template` to the plan;
   visual references are loaded separately from the SQL-free plan contract.
4. Stop the turn with `terminate`. The user must see and confirm the plan before
   component SQL is generated.

Never call `create_dashboard_draft` in the planning turn. Never replace this
workflow with a one-off HTML report.

## Confirmed plan: generate queries

When the message contains an authoritative `[[confirm-dashboard:ID]]` marker:

1. Use the persisted plan contract and its widget ids exactly.
2. Call `create_dashboard_draft` with the supplied dashboard id and expected
   revision. Without global filters, submit up to four widgets per call, using
   fewer for long queries. With filters, submit at most two because each widget
   also needs a frozen publication query and bindings. Follow the batch limit
   reported by the tool after a retry. The server stages these bounded
   batches and creates the draft atomically after every planned widget is present;
   when it reports missing widget ids, send only those missing widgets next.
3. Generate one parameterized, read-only query per widget.
   Reuse the temporal evidence injected into this turn, not an assumed format
   from a column name or a missing earlier discovery result. It is contextual
   evidence, not a server guarantee of SQL business semantics.
4. Declare typed output fields and a compatible chart encoding for every query.
5. Map every global filter to named SQL parameters.
   `filter_parameters` keys are saved filter ids; values are parameter-name
   strings or `{start_parameter, end_parameter}` for date and number ranges. Output fields
   are `{name, type}` objects, not strings or a field-name map. When the plan has
   filters, every widget needs a publication binding. The frozen query must
   return its filter fields and grouping/measure fields within the declared
   `max_rows` (default 1000, maximum 5000). If needed, aggregate at the full
   filter/grouping grain while preserving the measure; never truncate source
   rows or average averages. The publication output columns must match the
   widget output fields. See the generated DashboardQueryDraftRequest shapes.
6. If a tool argument is reported as truncated or malformed JSON, do not resend
   the complete payload. Retry with at most two widgets so the server can stage it.
7. If a widget fails server validation, call `repair_dashboard_draft` only for
   failed widgets. Preserve successful widgets.
8. Finish with `terminate` and state which widgets succeeded or still need work.

## Filter rules

- Date and number ranges use separate start and end parameters; never bind
  the two-value array to scalar equality.
- A scalar select may use a null guard, for example
  `(:category IS NULL OR category = :category)`.
- A multi-select parameter may appear only inside `IN` or `NOT IN`, for example
  `store_id IN (:store_ids)`.
- Do not add `IS NULL` guards for multi-select lists. The backend normalizes an
  empty list to mean no restriction.
- Never concatenate user values into SQL or emulate list membership using
  `INSTR`/`LIKE` and comma-delimited strings.
- An approved table with `expected_data_points: 0` permits a genuine empty
  result. Never remove its predicate, change its year, or insert dummy rows to
  make it nonempty. Other unexpected empty queries remain repairable failures.

## Revise or repair

- A `[[revise-dashboard-plan:ID]]` marker means replace the pending SQL-free plan
  with `revise_dashboard_plan`, then stop for confirmation again.
- Use `repair_dashboard_draft` for query or encoding failures in an existing
  generated draft.
- Use `modify_dashboard_draft` only for bounded changes explicitly requested by
  the user. First call `load_dashboard_draft` in the same turn to obtain the
  current schema and revision. Keep the dashboard id, data source, ownership,
  and revision contract.
- Never silently apply an AI change that requires user review.

## Selection-aware annotation

When the message contains an authoritative `[[dashboard-annotation:ID]]` marker:

1. Do not reload this skill or call `load_tools`; the server has already selected
   this workflow and registered its bounded tools.
2. For a `[修改组件]` annotation, use `propose_dashboard_change` with the exact
   Dashboard and annotation ids in the message. Address widgets and filters by
   stable ids, never by array indexes, and propose only the smallest change.
3. For `[指标解释]` or `[异常分析]`, load only the persisted Dashboard context and
   explain it. Deterministic anomaly evidence is authoritative: never run SQL,
   recalculate a result, call a proposal/mutation tool, or change `anomaly`,
   `normal`, or `indeterminate` conclusions.
4. Stop after the explanation or validated proposal. A modification proposal must
   still be applied or rejected by the user in the Dashboard UI; never save it
   silently.

## Completion checks

Before reporting success, rely on tool observations to verify:

- all requested widgets exist;
- every widget query passed read-only and field-mapping validation;
- filters have real options and parameter mappings;
- multi-table metrics reconcile to source totals at the declared grain, and
  join diagnostics show no unexplained fan-out;
- failed widgets are reported without discarding successful widgets;
- the result is a recoverable Dashboard draft, not only prose or an image.

For the detailed phase contract and examples, read
`references/workflow-contract.md` when needed.
