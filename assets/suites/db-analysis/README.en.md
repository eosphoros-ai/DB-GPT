# Smart Data Analysis

`db-analysis@1.1.0` · Official DB-GPT plugin

Analyze business data through a scoped dataset, consistent queries, charts, supported conclusions, and a report with source references.

## Workflow

1. Define the dataset from approved tables and documented join paths.
2. Build an analysis plan and run several read-only queries.
3. Keep metric versions, default filters, time grain, and comparison periods consistent.
4. Choose charts that match the result's dimensions and measures.
5. Explain changes using evidence and assemble the report.

## Commands and skills

| Command | Purpose | Skill |
| --- | --- | --- |
| `/analyze` | Run the full analysis workflow | Multi-step Analysis |
| `/dataset` | Define table scope and semantic context | Dataset Scoping |
| `/chart` | Select and generate charts | Chart Selection |
| `/report` | Assemble and export a report | Report Generation |
| `/attribute` | Explain changes and dimension contributions | Attribution Analysis |

The full analysis command references the other skills, the analysis playbook, and the report template. Their content is loaded before business execution.

## Database and metric context

The Walmart sales example explicitly uses `Walmart_Sales`. Other examples use the selected session database. A missing named connection must be resolved before sending the example.

The intended workflow pins published metric definitions across the analysis. For example, multiple charts using `valid_gmv@v2` should share its formula and filters. Unavailable semantic context must be disclosed instead of silently inventing definitions.

## Analysis and charts

Compare periods and dimensions with a consistent time grain. Use bars for rankings and comparisons, lines for trends, pies for suitable share views, and scatter plots for relationships. Include units, definitions, and source references.

Attribution separates contribution, price and volume effects, and structural changes. Label supported causes, secondary factors, and unverified hypotheses separately.

## Report structure

The report template includes:

1. Executive summary
2. Dataset and metric definitions
3. Charts and dimensional analysis
4. Attribution findings
5. Recommendations
6. Source references

Declared output formats include Markdown, HTML, and PDF. Report and export availability depends on the registered tools and actual execution results.

## Safety and approvals

Querying is read-only. DDL and shell operations are denied. Declared approval cases include expensive scans, excessive dataset scope, large exports, and external sharing. Platform permission and approval gates remain authoritative.

## Package and history

The plugin uses `.qwenwork-plugin/plugin.json`, skill `SKILL.md` files, a playbook, and a report template. DB-GPT runtime declarations live in `plugin.json.dbgpt`.

The backend preloads skill and reference text. Missing, empty, out-of-package, or oversized dependencies block business tools. Conversation history stores document paths and hashes for display; a loading label is distinct from a successful query, chart, or report.

English mode displays English metadata, examples, and this README. Database names, command IDs, and skill bindings remain stable.
