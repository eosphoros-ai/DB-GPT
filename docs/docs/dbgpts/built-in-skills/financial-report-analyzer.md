# financial-report-analyzer

The built-in skill analyzes Chinese text-based annual-report PDFs from non-financial listed companies. It supports one report, two to five companies in the same reporting year (`peer`), or two to five annual reports for the same company (`trend`). Scanned PDFs, quarterly reports, currency conversion and financial-industry accounting are outside this release's acceptance scope.

## Entry Points

Upload reports in the current agent conversation. A single report uses `prepare_financial_report`; an explicit comparison request uses `prepare_financial_comparison(file_ids, comparison_kind, baseline_file_id?)`. Multiple attachments alone do not trigger a comparison. The `/读年报` and `/财报对比` commands start a new analysis and require files attached to that send, even if the conversation has a saved report. After sending, the command selection clears; ask follow-up questions directly without selecting the command again. The result opens in the existing Computer workspace.

The `/financial-analysis` page also provides single-report, peer and trend modes, a baseline selector, report history and explicit recovery. Changing the baseline creates a new revision. The report keeps the established chapter navigation, execution panel, evidence panel and authorized source preview.

## Data And Analysis

`scripts/financial_document.py` extracts page-level facts and identity candidates. Amounts and deterministic results remain decimal strings. Missing values, extraction failures and conflicting disclosures remain visible; comparability is a separate decision involving company, period, currency, scope and profit attribution.

The backend calculates gross margin, expense ratios, cash/profit ratio, debt ratio, baseline differences, percentage-point differences and valid year-over-year changes. Trend calculations require shared disclosure support for the selected values and preserve gaps. Explicit restatements retain the original candidates and the versioned selection policy.

The agent reuses six topic workflows: operating performance, recurring earnings, margins, expenses, cash flow and balance sheet. Each finding declares entities, periods, metrics, subject, baseline and direction. The backend validates these fields and references. Unsupported causes belong in open questions. Validation failures remain distinct from missing financial data.

Models review direction, accounting scope and explanation boundaries before publication. Automatic validation or model review does not constitute independent human verification. Valid findings can be published together with clearly identified gaps.

## Recovery And Export

Single reports retain protocol v1; comparisons use v2. Data readiness, analysis and publication have separate states. Successful document extractions persist immediately, and explicit recovery retries failed documents without parsing successful documents again. Topic retry preserves other topics.

Published revisions are immutable. History, questions, citations and exports can select an exact saved revision. JSON and interactive offline HTML embed the same report snapshot. HTML includes its scripts and styles; source PDFs require authorized access through the application.

## Operations

The runner supports one local service process. The financial service itself does not alter existing tables. On SQLite, framework Alembic upgrades run at startup by default (`disable_alembic_upgrade=false`) and can alter existing tables. To inspect changes before startup, set `disable_alembic_upgrade=true` in the `[service.web]` configuration and preview any remaining financial migration with `uv run python -m dbgpt_serve.financial_analysis.migrate --database-url <target>` without `--apply`. Back up the intended database before applying the migration with `--apply` through the normal maintenance process. Do not run an old binary against comparison tasks.

Build the offline runtime with `node standalone/financial-analysis/build.cjs <output.html>` and configure `DBGPT_FINANCIAL_EXPORT_RUNTIME`. The current skill is defined in `skills/financial-report-analyzer/SKILL.md`; legacy scripts and templates remain available for compatibility.

Implementation details, isolated validation commands, measured results and unverified scenarios are recorded in the repository's `docs/financial-comparison-acceptance.zh-CN.md`. Synthetic fixtures and engineering tests do not replace real-PDF, real-model or human acceptance.
