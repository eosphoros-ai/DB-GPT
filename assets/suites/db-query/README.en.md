# Smart Data Query

`db-query@1.1.0` · Official DB-GPT plugin

Turn a business question into a reproducible, read-only query and a result preview with source references. This plugin focuses on accurate data retrieval from business databases.

## Workflow

1. Select a database and describe the metric, dimensions, and time range.
2. Resolve business terms to authoritative metric definitions, approved tables, join paths, and default filters.
3. Generate SQL, validate it, and correct validation errors.
4. Execute through the approved read-only tools and preview the results.
5. Export when requested, preserving the same definitions and filters.

## Commands and skills

| Command | Purpose | Skill |
| --- | --- | --- |
| `/nl2sql` | Generate validated, read-only SQL | NL2SQL Precision |
| `/schema` | Resolve table schemas and semantic definitions | Semantic Linking |
| `/metric` | Look up metric definitions and versions | Metric Definitions |
| `/export` | Export query results with masking and row limits | Result Export |

Readonly Guardrails is an internal skill loaded through the command's declared references. It covers cost estimates, timeouts, row limits, row-level access rules, and approval requirements.

## Database and semantic context

Examples use the selected session database. Confirm the connection before sending a request. The intended semantic workflow uses published metric definitions, table scopes, default filters, and row-level rules; missing semantic context is reported as degraded, and results need review.

Metric IDs and versions, table names, SQL, and database identifiers retain their original values when the interface language changes.

## Safety and approvals

The plugin declares an allowed tool set for semantic retrieval, schema linking, SQL generation, querying, and export. DDL and shell operations are denied. Plugin rules can tighten platform permissions and approvals.

Approval declarations cover expensive scans, queries without time filters, and large exports. Actual enforcement is owned by the core execution and approval gates; a configuration declaration alone is not evidence that a check ran.

## Results

Expected outputs include a SQL card, result preview, and source references. An export should use the same metric definitions and filters as the preview. Missing data or unavailable definitions must be disclosed.

## Package and loading

The source package uses `.qwenwork-plugin/plugin.json` and skill `SKILL.md` files. DB-GPT settings are stored in the manifest's `dbgpt` extension. There is no second `suite.yaml` for this built-in plugin.

The backend preloads the selected command's skill and its local Markdown references. Loading failures block business tools. Loaded document paths and hashes are recorded separately from tool execution results and restored from conversation history.

The interface uses English metadata and this `README.en.md` in English mode. Chinese content remains available in the original README and skill metadata.
