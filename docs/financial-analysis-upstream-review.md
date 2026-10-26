# Financial analysis: upstream review scope and validation

Prepared on 2026-10-26 for a **draft** contribution from
`zhiguang127:feat/financial-analysis` to `eosphoros-ai:main`.
The comparison base is `8733ce9071dbbfb09d3612c0d60a3d9bb3c66e20`.
The feature snapshot is `8af9eba27f094b329974c56c2987136267088ebc`;
the contribution branch also formats two test configuration files and adds
this review record. Existing development history is retained, including merge
commits. This is not a rebased or merge-ready series.

## User-visible behavior

Users can analyze an annual-report PDF, or explicitly compare two to five
reports, through the chat workflow or financial-analysis workspace. Extracted
facts retain document/page provenance, calculations use Decimal arithmetic,
and findings must pass reference and consistency checks. Reports expose source
previews, incomplete sections, revision history, and JSON/offline HTML exports.

Published reports become available before the final chat summary completes.
Interrupted conversations retain progress and saved report references; opening
history does not automatically rerun a model or promote a draft to published.
Comparison extraction and partial findings are useful independently of model
publication. The real-model comparison publication acceptance remains incomplete.

## Scope and proposed review order

The feature snapshot changes 136 files relative to the base. The large scope
is disclosed explicitly so maintainers can decide whether to accept an
integrated draft or request a smaller series.

| Area | Main paths | Relationship and suggested treatment |
| --- | --- | --- |
| Extraction and evidence | `skills/financial-report-analyzer/scripts/`, skill documentation | Foundation: identities, periods, tables, candidate values and source provenance. Review with the report service. |
| Single-report service | `packages/dbgpt-serve/src/dbgpt_serve/financial_analysis/` | Persistence, deterministic metrics, topic analysis, validation, questions, exports and lifecycle. Keep service, schema and service tests together. |
| Comparison extension | `comparison_*.py`, `models.py`, `migrate.py`, `revisions.py` | Depends on the report foundation. Could become a second feature PR with additive migration and compatibility tests. |
| Agent integration | `packages/dbgpt-app/src/dbgpt_app/openapi/api_v1/financial_*.py`, `tools/financial_tools.py`, `agentic_data_api.py` | Dedicated tools, bounded completion, progress and report artifacts. Depends on the service; shared entry-point edits need coordinated splitting. |
| Tool-call validation | `packages/dbgpt-core/src/dbgpt/agent/expand/` and action tests | Generic argument validation and bounded malformed-protocol retries. Candidate for an independent prerequisite PR. |
| History and file lifecycle | `react_history.py`, session-file service/registry, chat recovery code and tests | Generic disconnect checkpoints and persistent file binding support the feature. Candidate for a prerequisite PR after separating financial-specific hooks. |
| Workspace and chat UI | `web/new-components/financial-analysis/`, chat panels, `web/pages/index.tsx` | Evidence, report delivery, history, comparison, citations and responsive layouts. Keep UI and corresponding tests with their backend contract. |
| Offline export | `standalone/financial-analysis/`, `exports.py`, build dependencies | This is the runtime used for interactive offline report exports, not just a mock demo. Keep it with export functionality or defer that entire capability. |
| Development compatibility | `web/next.config.js`, `web/package.json`, `AdvancedCharts.tsx`, `examples_api.py` | Windows startup/path handling, HMR and chart SSR changes deserve separate scrutiny. Some could be separate fixes; do not remove them without rechecking development and report rendering. |
| Tests and documentation | backend tests, frontend tests, `scripts/verify_financial_comparison.py`, financial docs | Keep reproducible synthetic fixtures and regression tests. The long implementation plan and historical acceptance notes can be condensed before final review. |

No automatic history rewrite or scope removal has been performed. Proposed
split order: generic tool/history prerequisites, single-report service and UI,
then comparison and revision support. Offline export follows the report schema
it renders. The final series should be agreed with maintainers before rewriting
this integration branch.

## Current validation

The checks below were run on Windows with Python 3.11.9, Node 24.19.0,
Ruff 0.17.2, mypy 1.15.0, and the existing installed workspace dependencies.
No live model was called and no application database was migrated or reset.
Browser API traffic was mocked; the temporary development server used port
5688 and was shut down after testing.

| Check | Result and limits |
| --- | --- |
| Python formatting, import order and lint | All six `make fmt-check` Ruff checks pass. Executed directly with Ruff; the two lint commands omit `--fix` to remain checks. The Makefile and CI version policy are unchanged. |
| Backend selected regression suite | **398 passed, 1 skipped, 3 failed**. The three failures occur while setting up Windows symlinks (`WinError 1314`), before the relevant security assertions execute. These are not reported as passed. |
| Financial frontend unit tests | **19 passed** via `npm run test:financial`. |
| Existing frontend report/final-answer tests | `npm test` passes all four configured suites. |
| Offline export build | Rebuilt inline HTML runtime: **3,934,915 bytes**. Synthetic snapshots were regenerated with this runtime. |
| Offline browser tests | **11 passed**: ten synthetic/single-report scenarios using the new runtime and one existing saved real-PDF snapshot. The saved snapshot test does not rerun extraction or model analysis. |
| Report delivery and history browser tests | **9 passed**: six live-delivery scenarios and three history-recovery scenarios, with mocked API/SSE responses on an isolated development server. |
| TypeScript whole-project check | **Fails: 142 diagnostics**. An isolated upstream source snapshot checked with the same dependencies also has 142; counts by file and error code are identical. This is not a clean type-check result. |
| Core mypy | **Fails: 1,072 errors in 190 files**, checking 502 source files with `--no-incremental`. The isolated upstream snapshot produces identical error messages/counts after normalizing line numbers. |
| ESLint in changed TS/TSX/MTS files | Checked 51 committed source files with LF line endings. **23 errors and 1 warning remain**, all also present upstream in `AdvancedCharts.tsx` and `ManusRightPanel.tsx`. The comparable upstream files have 24 errors and 1 warning. Four new formatting errors in the two financial test configs were corrected. |
| Git whitespace | `git diff --check upstream/main...HEAD` passes. |

The three backend failures are:

- `session_file/tests/test_inspector.py::test_symlink_inputs_are_rejected_safely`
- `session_file/tests/test_registry.py::TestMaterializeLocalFile::test_materialize_rejects_symlink_escape_of_work_root`
- `session_file/tests/test_registry.py::TestMaterializeLocalFile::test_write_stream_secure_refuses_symlinked_candidate`

Both test files are unchanged from the upstream base. Linux execution of these
security cases remains required; the permission failure is not evidence that
their assertions succeed.

For type-check baselines, upstream sources were extracted to an isolated local
directory and checked with the same Python/frontend dependencies. Cross-package
JSON inputs and the `docker` source-directory layout were also supplied.
The mypy comparison disables incremental caches. ESLint reads committed blobs
to avoid treating Windows checkout CRLF differences as source changes.

### Reproduce the checks

Install the project's dependencies using `CONTRIBUTING.md`. The recorded
`--no-sync` commands use an already prepared environment.

```bash
uv run --no-sync pytest \
  packages/dbgpt-serve/src/dbgpt_serve/financial_analysis/tests \
  packages/dbgpt-app/src/dbgpt_app/openapi/api_v1/tests/test_financial_comparison_tools.py \
  packages/dbgpt-app/src/dbgpt_app/openapi/api_v1/tests/test_financial_execution_progress.py \
  packages/dbgpt-app/src/dbgpt_app/openapi/api_v1/tests/test_financial_history_recovery.py \
  packages/dbgpt-app/src/dbgpt_app/openapi/api_v1/tests/test_react_history.py \
  packages/dbgpt-app/src/dbgpt_app/openapi/api_v1/tests/test_agentic_data_api_lifecycle.py \
  packages/dbgpt-app/src/dbgpt_app/openapi/api_v1/tests/test_react_final.py \
  packages/dbgpt-core/src/dbgpt/agent/expand/actions/tests \
  packages/dbgpt-serve/src/dbgpt_serve/session_file/tests -q

make fmt-check
uv run --no-sync mypy --no-incremental --config-file .mypy.ini \
  --ignore-missing-imports packages/dbgpt-core/

npm run test:financial --prefix web
npm test --prefix web
cd web
npx tsc --noEmit --incremental false --pretty false
cd ..

node standalone/financial-analysis/build.cjs \
  web/node_modules/.cache/financial-comparison/pr-runtime.html
uv run --no-sync python scripts/verify_financial_comparison.py \
  --output-dir web/node_modules/.cache/financial-comparison \
  --runtime web/node_modules/.cache/financial-comparison/pr-runtime.html
cd web
npx playwright test --config playwright.financial.config.ts offline-comparison.spec.cjs
npx playwright test --config playwright.recovery.config.ts
```

The optional saved real-PDF browser scenario skips on a fresh checkout without
`real-peer.json`; the ten synthetic/single-report scenarios do not require it.
To reproduce the six live-delivery scenarios, run a development server in a
separate terminal, set `FINANCIAL_LIVE_BASE_URL` to its URL, and run:

```bash
cd web
npx playwright test --config playwright.financial.config.ts live-report-delivery.spec.cjs
```

Use a free port and stop the server after testing. The recorded run combined
the live-delivery and recovery suites in a temporary Playwright configuration
with a managed server at `http://127.0.0.1:5688`; it did not require a backend.

### Existing fork CI evidence

- Python Code Quality Checks run `40271341944` passed on `8af9eba27`.
- Build Web Application run `40196516530` passed on `5826eb4b9` (Ubuntu/macOS).
  The `web/` tree is identical between that commit and the feature snapshot
  `8af9eba27`. The contribution branch subsequently changes formatting in two
  test configs. A new production build was not run locally in this preparation.
- Upstream PR checks and any first-time-contributor approval are separate from
  these fork results.

## Remaining acceptance and design decisions

- End-to-end real-model comparison publication is not accepted. Historical
  runs retained valid findings but remained draft/awaiting revision.
- Real same-company cross-year PDFs, real restatement/conflict cases and
  independent human verification of amounts, ratios and narrative are pending.
- MySQL/PostgreSQL migrations have not been exercised against real servers.
  SQLite compatibility tests do not establish those deployments are safe.
- Real chat-to-model-to-published-report browser acceptance remains distinct
  from the mocked browser tests above.
- Full repository pytest/doctests and a clean whole-project type/lint result
  are not claimed.
- Maintainers should review shared Agent retry policy, storage lifecycle hooks,
  model configuration/defaults, migration integration, export packaging and
  localization before treating the feature as ready to merge.

See [comparison acceptance](financial-comparison-acceptance.zh-CN.md) and
[refresh/recovery behavior](financial-analysis-refresh-recovery.zh-CN.md) for
historical evidence and operational details. Historical counts are not
presented as new test executions. This draft is intended to discuss scope and
architecture while these acceptance items remain visible.
