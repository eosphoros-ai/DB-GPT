# Financial contribution: two-PR delivery

This series contains the complete net changes from `feat/financial-analysis`,
including the follow-up review repairs from upstream PRs #3308 and #3309.
It replaces the earlier nine-slice proposal. Existing development and review
branches remain available; no published history is rewritten.

## Review boundaries

Both branches start at upstream `main` commit `06a46eea2` and target
`eosphoros-ai/DB-GPT:main`. Their changed-file sets are disjoint.

| Order | Branch | Scope |
| --- | --- | --- |
| 1 | `review/financial-v2-backend` | Shared Agent/tool fixes, PDF extraction and dependencies, exact calculations, single/multi-report domain and persistence, APIs, Agent tools, history and session-file lifecycle, backend tests and financial documentation. |
| 2 | `review/financial-v2-web` | Financial workspace and comparison UI, chat delivery/recovery, evidence and revisions, localization, offline HTML runtime, frontend tooling and tests. |

Merge the backend first, then the frontend. The financial Agent uses the shared
core's native tool-choice hook, so those changes belong in the same backend PR.
The frontend can be built separately, but financial interactions require the
backend API. JSON export is available in the backend; HTML export needs the
frontend PR's built runtime. Until that runtime is configured, the API returns
`EXPORT_RUNTIME_MISSING` explicitly.

Single-report and comparison contracts remain together within each layer.
Tests travel with the code they verify. The combined tree is checked against
the full integration snapshot so no implementation path is silently omitted.
Unlike the earlier proposal, this series also retains the existing historical
planning/acceptance documents, example-path compatibility change, dashboard
test configuration and local-development Next configuration.

## Review repairs retained

- #3308: serialize resolved arguments before executing tools; reset the protocol
  budget per run; preserve exhaustion after report-repair handling; cover the
  actual native termination lifecycle.
- #3309: preserve input units/currencies in calculation traces; declare
  `pdfplumber>=0.10.4` and synchronize lock metadata; cover blank/overlapping
  table columns and real parser/cleanup APIs with a synthetic PDF.
- Keep the current dedicated financial Agent workflow and add the raw PDF
  extraction contract to its Skill instructions. The foundation-only PR's
  legacy HTML workflow does not replace the integrated workflow.
- Preserve the fixes recorded in [review verification](financial-analysis-review-fixes.md).

## Validation and limits

Each PR description records checks for its submitted branch, plus checks of
the combined tree. Earlier numbers in the historical review and acceptance
records describe their named snapshots, not new executions of this series.

Use `CONTRIBUTING.md` to prepare dependencies. Run the core tool and financial service/Agent/session-file suites for PR 1,
and financial Vitest,
existing frontend suites, offline build/browser checks and mocked chat/recovery
checks for PR 2. Python imports must resolve to the tested checkout's sources.

Synthetic PDF and mocked browser coverage do not establish successful real-model
publication or independent human verification. Historical Windows symlink setup
failures and upstream type-check diagnostics remain explicitly reported where
applicable. Real MySQL/PostgreSQL migrations and real cross-year/restatement
acceptance remain separate work.
