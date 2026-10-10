# PR #3277 home examples and README packaging — 2026-10-10

> **Later follow-up:** the fresh SQL timeout and backend-image download limitations below
> are addressed and rechecked in [SQL/offline validation](pr-3277-skill-offline-validation.md).
> Two fresh SQL clicks completed and both packages were independently audited/downloaded;
> the financial report now opens with three embedded images while the backend is stopped.
> The dated results below remain as the earlier baseline.

This follow-up tests the four home-page example cards and the complete
`bash ../scripts/build_web_static.sh` command documented under **Use In DB-GPT**
in `web/README.md`. Earlier navigation checks and `npm run compile` alone did
not establish these acceptance criteria.

## Results and provenance

Product code: `a432763b175e6cfd8820577d4578e01dab5133a5`. The local backend used
an isolated source copy and SQLite metadata, with the existing configured
DeepSeek model and cached RoBERTa embeddings. Model credentials remained outside
the repository. The live scenarios used the real DB-GPT API and model, without
API fixtures. Windows Python 3.11.9 served the static UI through the normal
application mount at `127.0.0.1:5670`.

The initial report generations used the `7870c914` packaged frontend. After the
HTTP-error fix, all three reports were reopened, rendered and downloaded using
the Ubuntu artifact from [`ce179102` CI](https://github.com/jcsdxhe/DB-GPT/actions/runs/38024250721).
Its frontend and packaging sources are identical to `a432763b`; the four changed
backend/skill product files were compared byte-for-byte with that commit.
The skill-package download was exercised on this updated backend and frontend.
This is a source-matched validation, not a claim that every live generation ran
on the eventual PR head containing these review records.
The final guide cleanup also removes a reference to an absent
`references/output-patterns.md`; the model-backed captures precede this removal.

| Home card | Real behavior verified | Result and boundary |
| --- | --- | --- |
| Walmart sales analysis | Stage CSV, submit Agent request, process 6,435 rows / 45 stores, produce report, refresh history, render and download | Passed: 18 populated ECharts canvases, 88,309-byte HTML download. Basic fixture dimensions checked; not a statistical audit. |
| Database profile report | Select `Walmart_Sales`, execute real SQLite queries, generate report, refresh/render/download | Passed: two populated Chart.js charts, 6,471-byte HTML download. Does not cover every database engine. |
| Financial report analysis | Stage the bundled PDF, execute extraction/ratio/chart tools, render report after reload, download | Passed: three loaded PNG charts, 10,833-byte HTML download. Financial statements, conclusions and completeness were not independently audited. |
| Create SQL analysis skill | Create six skill files, validate/package, execute generated SQLite connection/query/chart scripts, reload and download `.skill` | Completed with an explicit continuation after one model turn returned only a plan. A further packaging-only turn verified the new download handoff. The 6,522-byte download matches the disk package by SHA-256. This is not an unconditional single-click completion claim. |

Accepted report audits and the skill-download audit recorded zero page errors,
console errors or failed HTTP responses; the report audits also recorded zero
failed asset requests. Downloaded HTML can reference chart CDNs or backend images;
standalone offline rendering was not validated. The generated
skill was independently exercised against a fresh three-row SQLite fixture:
connection/table discovery, two aggregate rows with expected values, a 1,200 ×
720 PNG, simple DELETE rejection, and package validation all passed. Archive
members match the six source files. Its generated MySQL/PostgreSQL paths were
not tested; the simple SQL keyword guard is not a comprehensive read-only or
security guarantee. Generated code was not installed globally or added to this PR.

## Failures found and focused repairs

- Windows example-file responses used backslashes rejected by the existing
  chat-path validator. Return forward-slash paths and test the API-to-validator
  round trip, including cross-owner rejection. The validator was not relaxed.
- A non-2xx Agent response left the home page displaying “thinking”. Surface
  JSON and non-JSON HTTP errors and keep the composer usable. Both regressions
  failed before the fix and passed afterward on the packaged UI.
- Windows selected the System32 WSL launcher despite Git Bash being on PATH.
  Resolve the configured Bash executable before subprocess launch; cover a
  real Bash execution in a native path containing spaces.
- Skill-creator CLI examples assumed the repository root and were confused
  with a JSON-argument tool wrapper. Expose `SKILLS_DIR` in execution contexts
  and document positional CLI calls with outputs in the conversation directory;
  remove its dangling reference to a file not shipped with the skill.
- Generated `.skill` packages were present on disk but absent from downloadable
  UI artifacts. Return a file chunk only for an existing package contained in
  the current conversation directory, with an outside-directory regression.

These are observed failures in the tested application. They are not attributed
to the Next upgrade without baseline comparison evidence. Initial failing
captures are retained locally. Two attachment tests still patched only an old
stream constructor; their fixtures now exercise the current constructor too,
retaining the original cleanup and retry assertions. A filename test now uses
a shell-sensitive character that is legal on Windows.

## Build, packaging and regression checks

- The [Ubuntu/macOS packaging run](https://github.com/jcsdxhe/DB-GPT/actions/runs/38024250721)
  passed TypeScript, lint, production build and the full README command.
  CI supplies a non-secret `.env` sentinel, verifies exact restoration and
  removal of `.env.copy`, compares `out/` with the Python static directory,
  and validates **60 HTML pages / 1,782 local asset references**. The packaged
  directory is retained as an artifact and actually served by the local backend.
- [Product-code CI](https://github.com/jcsdxhe/DB-GPT/actions/runs/38024843961)
  passed the expanded **150-test backend contract suite** on `a432763b` and
  reruns packaging on both platforms.
  Final conclusions and PR-head runs are recorded in the PR body.
- [Browser and connector CI](https://github.com/jcsdxhe/DB-GPT/actions/runs/38023294373)
  passed **48 Chromium tests in each of production and development**, plus
  **105 backend/real-database tests**, on `0363aa4c`. No frontend/browser-source
  changes followed that commit. These browser tests use API fixtures and are
  separate from the model-backed scenarios above.
- Local Windows: example API **5 passed**; Bash/runtime **23 passed**;
  execution integration **53 passed**; two affected attachment lifecycle tests
  passed. The packaged UI's two new HTTP-error browser tests passed without
  retries. TypeScript passed; lint reported **0 errors / 89 warnings**.
  Changed Python passed Ruff **0.16.10** check/format; actionlint and diff checks
  passed. Deprecation warnings remain in the Python environment.

The full packaging script was run on Ubuntu and macOS CI, not in local Windows
Git Bash. Windows acceptance covers serving those generated static files with
the real backend. Build-failure `.env` recovery, arbitrary workspace paths and
all external-service combinations are not established by these successful runs.
No type checking was disabled. No new local Node dev server was started; fresh
dev browser evidence comes from CI following the earlier local approval block.

## Remaining review coordination

Copilot credential exchange remains blocked by HTTP 403, with entitlement/app
compatibility unresolved. The earlier full-core mypy, Windows Docker and other
uncovered integrations retain their previously reported status; they were not
retested here. See the [connector record](pr-3277-connectors-auth-validation.md)
and dated [regression record](pr-3277-regression.md).

The refreshed upstream main is `ad203de5c7301c9a103caa1198d17aaee18c6647`;
merge-tree reports no conflicts with this candidate. Against unchanged #3278
`80c947d3d6e0753e188d72e0444f01f1576f74a3`, **15 shared paths conflict**, including
the new example/runtime test and CI changes. These changes have not been copied
into #3278. Maintainers must decide merge order and shared-change ownership;
reconcile and retest the second PR against the actual merged tree. No force
push, upstream PR merge or deployment is part of this validation.

Compact machine-readable evidence is in
[home-packaging-validation.json](evidence/pr-3277/home-packaging-validation.json).
