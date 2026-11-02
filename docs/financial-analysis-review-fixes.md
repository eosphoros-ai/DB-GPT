# Financial workspace review verification

This records the 13 inline comments and two localization nitpicks in
eosphoros-ai/DB-GPT#3307, verified on October 26, 2026. The findings were checked
against the implementation before changing it. All 15 resulted in repairs;
the remaining acceptance limits below still apply.

| Review item | Repair | Regression evidence |
| --- | --- | --- |
| 4374227799: Windows-only documentation command | Use `uv run --no-sync python -m pytest`. | Documentation command reviewed against the contribution guide. |
| 4374227803: unbounded cancellation cleanup | Shield cancellation cleanup within a five-second deadline; consume/log failures from tasks that finish later. | Lifecycle tests include a task that resists cancellation, expires the cleanup deadline and later raises. |
| 4374227822: unrelated turns forced through a saved report | Scope the read, answer-validation and final-render gates to financial intent or active financial work. Retain short contextual follow-ups. | Four unrelated questions bypass the gates even after an unnecessary report read; eight financial/short follow-ups still require a fresh read. |
| 4374227832: comparison analyzer missing model name | Require both an LLM client and `model_name`, matching the single-report path. | A client without a model name does not construct `TopicGenerator`; serial topic analysis remains available. |
| 4374227843: Agent tests in the serve package | Move tool/Agent tests into `dbgpt_app` and retain only service/workflow tests in `dbgpt_serve`. | Moved tests run in the app suite; importing the remaining workflow test module does not import `dbgpt_app`. |
| 4374227847: financial close failure skips registry cleanup | Log a financial close failure and continue closing the registry and unbinding endpoints. | A failing financial `close()` still permits both cleanup operations. |
| 4374227855: unconditional `tomllib` import | Import TOML support only in the optional model adapter, falling back to `tomli` on Python 3.10. | Python 3.10.0 compiled the complete script and executed the actual fallback-import block plus a TOML parse. The full acceptance CLI was not run under 3.10. |
| 4374227861: unreadable offline citation syntax | Preserve evidence labels while stripping authenticated application-link wrappers in the offline Markdown adapter. | Pure label/formatting test and a browser snapshot containing a financial Markdown citation. |
| 4374227872: light-only comparison styles | Use workspace tokens for controls, borders, headers, bars, conflict cells and clarification panels; replace the undefined text token. | Browser checks verify light controls and dark controls, table headers and conflict backgrounds. |
| 4374227877: `randomUUID` absent on HTTP LAN | Generate UUID v4 identifiers with `crypto.getRandomValues`. | Unit test covers 100 unique, correctly shaped IDs; a real non-loopback HTTP browser upload/create-run flow passes with `isSecureContext === false` and no `randomUUID`. API responses are mocked. |
| 4374227889: citation version overrides later manual choice | Scope manual selection to the report and citation request. A subsequent citation click can select its own revision again. | Citation -> other revision -> current task -> new citation request regression. |
| 4374227904: optional report recovery breaks history | Isolate the latest-report request and preserve cancellation/stale-request guards. | Browser test aborts the optional lookup while an empty conversation remains writable. |
| 4374227919: default offline command runs live tests | Separate `offline` and `live` Playwright projects; the default financial command selects only `offline`. | Default command discovers and passes 13 offline cases without a development server. |
| Localization nitpick: shared progress and financial components | Add matching English/Chinese locale keys and interpolation parameters; subscribe components and label maps to language changes. | Locale parity, English-text audit and mounted-component language-switch tests. Financial narrative and source excerpts retain their original language. |
| Localization nitpick: chat-page additions | Localize the financial notification, incomplete-stream and restored-history fallbacks, history error and mobile return action. | Changed-file ESLint and whole-project TypeScript comparison; mocked history/delivery browser regressions. |

## Regression results

The checks used the existing prepared environment, temporary SQLite databases
and generated fixtures under ignored cache directories. The temporary Next
server used port 5688 and was managed/stopped by Playwright. No daily database
was changed and no live model was called.

- Final selected full backend regression: **425 passed, 1 skipped, 3 failed**.
- The full result includes **11 data-foundation regressions**. These cover exact
  decimal arithmetic, missing/zero inputs, incompatible currency, negative
  prior-period growth and rejection of narrative-only extraction.
- Financial Vitest: **24 passed**.
- Existing `npm test`: all four configured suites passed.
- Offline build: **3,966,373 bytes**, with inline assets and no application
  runtime or external network dependency.
- Default offline browser command: **13 passed**, including dark comparison,
  offline citation labels, mobile evidence and a saved real-PDF snapshot
  re-rendered with the new runtime. The snapshot does not rerun real extraction
  or model analysis.
- Mocked chat delivery/history: **10 passed**. The additional real-HTTP-origin
  create-run browser scenario passed separately after its API mock was aligned
  to `/api/v1/agent/files`.
- All six Ruff formatting/import/lint checks equivalent to `make fmt-check`
  passed; lint checks were run without the Makefile's mutation flag.
- ESLint passed for all changed frontend TypeScript files.
- Whole-project TypeScript remains at **142 diagnostics**, matching the
  established upstream baseline by file/error code. No financial source
  diagnostics remain. This is not a clean whole-project type check.

The three backend failures are unchanged upstream session-file security tests
that fail while creating Windows symbolic links (`WinError 1314`), before their
assertions run:

- `test_inspector.py::test_symlink_inputs_are_rejected_safely`
- `test_registry.py::TestMaterializeLocalFile::test_materialize_rejects_symlink_escape_of_work_root`
- `test_registry.py::TestMaterializeLocalFile::test_write_stream_secure_refuses_symlinked_candidate`

Linux execution of those cases remains necessary. Real-model publication,
human verification of financial figures, real cross-year/restatement samples
and MySQL/PostgreSQL migrations remain unaccepted. They are not implied by the
mocked or saved-snapshot checks above.

## Reproduction

Install dependencies according to `CONTRIBUTING.md`. `--no-sync` below assumes
that the environment is already prepared.

```bash
uv run --no-sync python -m pytest \
  packages/dbgpt-serve/src/dbgpt_serve/financial_analysis/tests \
  packages/dbgpt-app/src/dbgpt_app/openapi/api_v1/tests/test_financial_turn_scope.py \
  packages/dbgpt-app/src/dbgpt_app/openapi/api_v1/tests/test_financial_workflow_tools.py \
  packages/dbgpt-app/src/dbgpt_app/openapi/api_v1/tests/test_financial_comparison_tools.py \
  packages/dbgpt-app/src/dbgpt_app/openapi/api_v1/tests/test_agentic_data_api_lifecycle.py -q
npm run test:financial --prefix web
npm test --prefix web
node standalone/financial-analysis/build.cjs \
  web/node_modules/.cache/financial-comparison/runtime.html
uv run --no-sync python scripts/verify_financial_comparison.py \
  --output-dir web/node_modules/.cache/financial-comparison \
  --runtime web/node_modules/.cache/financial-comparison/runtime.html
npm run test:e2e:financial --prefix web
```

For mocked browser delivery tests, start a development server on a free port,
set `FINANCIAL_LIVE_BASE_URL` and run `npm run test:e2e:financial:live --prefix web`.
An optional `FINANCIAL_HTTP_LAN_BASE_URL` exercises a real insecure HTTP origin;
without it the create-run test explicitly removes `randomUUID` on loopback.
From `web/`, run `npx playwright test --config playwright.recovery.config.ts`
for the managed-server history tests.
