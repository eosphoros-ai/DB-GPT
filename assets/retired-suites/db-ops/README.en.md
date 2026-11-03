# Smart Database Operations

`db-ops@1.1.0` · Official DB-GPT plugin

Investigate database performance and health with evidence, diagnose causes, and produce repair proposals with explicit risk and approval requirements.

## Workflow

1. Confirm the target database, environment, and time window.
2. Collect available slow logs, execution plans, metrics, and index information.
3. Correlate the evidence and identify likely causes.
4. Produce a diagnostic report.
5. Propose repairs with impact estimates, rollback plans, and review requirements.

## Commands and skills

| Command | Purpose | Skill |
| --- | --- | --- |
| `/slowlog` | Collect and diagnose slow queries | Slow Query Diagnosis |
| `/explain` | Interpret an execution plan | Execution Plan Review |
| `/inspect` | Inspect database health | Health Inspection |
| `/index` | Recommend indexes | Index Advisor |
| `/profile` | Profile storage and propose governance | Database Profiling |
| `/fix` | Review and organize repair proposals | Change Review |

Skills reference shared diagnostic and production safety runbooks. Execution plan review reuses the slow-query diagnostic guidance.

## Evidence and diagnosis

Slow-query analysis groups SQL fingerprints and examines missing indexes, poor plans, large scans, locks, SQL patterns, and resource bottlenecks.

Health inspection covers connections, QPS, slow-query rates, buffer hit rates, storage and I/O, replication lag, and lock waits. Profiling examines table growth, fragmentation, primary keys, large fields, data tiers, and index redundancy.

If a connection, log, metric, or execution plan is unavailable, identify the missing evidence. Do not invent timings, row estimates, or observed index usage.

## Change review

Repairs remain proposals. Review destructive risk, lock impact, estimated duration, replication effects, online DDL options, rollback, and approvals.

Production DDL is denied by default. Destructive actions require human review, and rejection must not be bypassed through a different tool or rewritten parameters. Shell operations, database drops, and truncation are outside the declared tool boundary.

Configuration describes the intended restrictions; actual enforcement is owned by the platform's permissions, approval gates, and registered tools.

## Context and outputs

Confirm the target database and time window before collection. The default window is the last four hours, with five-minute granularity and a declared maximum span of seven days. Environment information matters when reviewing changes.

Expected outputs include a diagnostic report and repair plan. Execution plans and source references provide supporting evidence. A proposed repair must be clearly labeled as requiring review rather than displayed as an executed change.

## Package and loading

The plugin uses `.qwenwork-plugin/plugin.json`, skill `SKILL.md` files, and local playbooks and runbooks. DB-GPT context, tool, and approval declarations live in `plugin.json.dbgpt`.

The backend preloads a selected command's skill and linked Markdown references. Loading errors block business tools; document paths and hashes are saved in conversation history. Loading a skill does not prove that its diagnostic operations have run.

English mode uses English metadata and this README. Command IDs, target database identifiers, and tool bindings are preserved.
