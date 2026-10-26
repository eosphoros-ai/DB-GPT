# financial-report-analyzer

The built-in skill analyzes Chinese text-based annual-report PDFs from non-financial listed companies. It supports one report, two to five companies in the same reporting year (`peer`), or two to five annual reports for the same company (`trend`). Scanned PDFs, quarterly reports, currency conversion and financial-industry accounting are outside this release's acceptance scope.

## Entry Points

Upload reports in the current agent conversation. A single report uses `prepare_financial_report`; an explicit comparison request uses `prepare_financial_comparison(file_ids, comparison_kind, baseline_file_id?)`. Multiple attachments alone do not trigger a comparison. The result opens in the existing Computer workspace.

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

The runner supports one local service process. Existing databases need the comparison schema before comparison tasks can run. The financial service does not execute its own `ALTER` statements, but enabled framework migrations can update existing tables during application startup; the service then refreshes its schema state. Inspect the actual database before planning a separate migration. From the repository root, set `FINANCIAL_DATABASE_URL` to a SQLAlchemy database URL and preview the remaining changes without `--apply`. These executable examples use an isolated in-memory database; replace that URL with the intended database URL before actual maintenance.

Bash:

```bash
FINANCIAL_DATABASE_URL='sqlite:///:memory:'
uv run --no-sync python -m dbgpt_serve.financial_analysis.migrate --database-url "$FINANCIAL_DATABASE_URL"
```

PowerShell:

```powershell
$FINANCIAL_DATABASE_URL = 'sqlite:///:memory:'
uv run --no-sync python -m dbgpt_serve.financial_analysis.migrate --database-url "$FINANCIAL_DATABASE_URL"
```

Back up the intended database before enabling startup migrations or applying a maintenance migration. If the preview lists missing changes, review them and rerun the command with `--apply` through the normal maintenance process. An empty plan requires no second migration. Do not run an old binary against comparison tasks.

The offline HTML runtime requires the companion financial workspace frontend and its installed web dependencies. A backend-only checkout does not contain the build script. In a checkout containing that frontend, run `node standalone/financial-analysis/build.cjs web/node_modules/.cache/financial-comparison/runtime.html`, then configure `DBGPT_FINANCIAL_EXPORT_RUNTIME` in the backend to point to the built file. Until the runtime is installed, HTML export returns `EXPORT_RUNTIME_MISSING`; JSON export remains available. The current skill is defined in `skills/financial-report-analyzer/SKILL.md`; legacy scripts and templates remain available for compatibility.

Implementation details, isolated validation commands, measured results and unverified scenarios are recorded in the repository's `docs/financial-comparison-acceptance.zh-CN.md`. Synthetic fixtures and engineering tests do not replace real-PDF, real-model or human acceptance.

HTML export accepts an optional `language` (`en` or `zh`, default `zh`) and preserves the selected UI language offline. English and Chinese HTML files are separate artifacts of the same unchanged revision; JSON data is language independent. Rebuild the frontend runtime after updates.
