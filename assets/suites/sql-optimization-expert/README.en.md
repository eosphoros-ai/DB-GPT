# SQL Optimization Expert

An official built-in, read-only DB-GPT suite for SQL diagnosis, rewrites, index candidates and change reviews.

Select the suite from the home page or composer, choose an authorized database and supply SQL or DDL.

| Command | Output |
| --- | --- |
| /sql-diagnose | Evidence-based diagnosis, plain EXPLAIN and an HTML report for complete tasks |
| /sql-rewrite | Copyable candidate SQL, a change comparison and semantic checks |
| /index-advise | Candidate index DDL, tradeoffs and a measurement plan |
| /sql-review | Risks, rollout prerequisites, validation and recovery checklist |

Only completed report-tool results are downloadable reports. SQL and DDL are copyable code, not automatically executed. Unmeasured gains and missing evidence are stated explicitly.

MySQL, PostgreSQL and SQLite are the initial dialects. Production permissions, server-side cancellation and resource budgets remain deployment responsibilities. See the [workflow](prompts/workflow.md) and [read-only boundaries](references/production-readonly.md).
