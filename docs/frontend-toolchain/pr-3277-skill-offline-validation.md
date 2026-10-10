# SQL example and financial HTML follow-up — 2026-10-10

This record follows the [home/packaging acceptance](pr-3277-home-packaging-validation.md).
The earlier fresh SQL example failed during model inference, and the downloaded
financial report still referenced three backend PNGs. Neither was counted as
fully passed in the earlier evidence.

## Changes

- Model workers encode some failures in an error-bearing ModelOutput rather
  than raising. AIWrapper now rejects these chunks before publishing text or
  accepting tool calls. The existing three-attempt inference retry handles them;
  tools are not rerun by this change. Six regressions failed before the fix and
  passed afterward, covering both text and native-tool modes, recovery and
  exhausted retries.
- ReAct final events and stored history carry a completion status. Failed model
  runs and loops ending without termination no longer display a successful task
  footer. Old history without this optional field remains readable.
- The SQL example explicitly requests a small SQLite implementation, disposable
  query/chart tests and a downloadable package within the same turn. It avoids
  requiring an external database account for the homepage demonstration.
- Generated conversation packages use file downloads rather than installed-skill
  previews. Verified packages are shown before other outputs; deleted template
  paths inferred from shell logs are not offered as delivered files.
- HTML downloads embed their image resources as data URLs. Both home artifacts
  and the legacy HTML preview use the same implementation. A failed image fetch
  reports a download error instead of saving an incomplete report. Responsive
  images use the embedded fallback. Scripts and styles are retained as supplied;
  this is not a generic website archiver or a promise that all generated reports
  with CDN scripts work offline.

## Live acceptance and provenance

Product implementation: `9ccc699c8da72098dbf1c45bd68817118d2378c2`.
A Windows Python 3.11.9 backend served the actual Ubuntu README-packaging
artifact through the normal application static mount. The isolated backend
source matches this revision; existing model credentials stayed outside Git.

Two new homepage clicks completed SQL skill generation, tests and packaging in
one turn, without follow-up instructions or clarification answers. Observed
durations were **45.108 s** and **51.122 s**; these are two measurements, not a
latency/reliability guarantee. Packages were **5,368 bytes / 4 members** and
**5,003 bytes / 5 members**. Both downloads matched their disk packages by
SHA-256. Independently reviewed and executed scripts produced the expected two
aggregate rows on fresh three-row SQLite fixtures, PNGs of **1080×600** and
**960×600**, rejected a DELETE, and passed package validation. This does not
prove every generated command or database engine is correct or secure.

The first generation used the `3bb41183` UI and exposed an incorrect installed-
skill preview. The final implementation presents the actual conversation package
and omits guessed/deleted template file links for that packaged delivery.
Both packages were downloaded again through the `9ccc699c` UI without installed-
skill API requests or page/console/HTTP errors. The second generation itself also
used this final UI. Generated code was not installed globally or committed.

The existing financial PDF report was downloaded using the final implementation:
**251,219-byte HTML, three embedded PNG images**. After stopping the backend and
disabling browser networking, the file opened from disk with all three images
loaded, no HTTP requests and no page errors. This tests offline presentation;
the report was not regenerated and its financial analysis was not audited.

Walmart and database-profile reports were also reloaded and downloaded through
the changed HTML helper; their downloaded files rendered **18 ECharts canvases**
and **2 Chart.js canvases** while online. They still depend on chart CDNs.

## Automated validation

The final static UI passed **8 local Chromium regressions**, covering package
downloads in live/history views, failed model turns with/without partial output,
offline image rendering, failed image fetches and HTTP 400/503 recovery.
The first candidate's new no-artifact failure test exposed the missing footer
(**50 passed / 1 failed** in CI); it was repaired rather than removed.

[Build and packaging CI](https://github.com/jcsdxhe/DB-GPT/actions/runs/38029229145)
**passed** on `9ccc699c`: **170 backend contracts / 4 warnings**, TypeScript,
lint, **45 build contracts**, **24 frontend tests** plus Wiki assertions,
production build and the complete README command on Ubuntu/macOS.
Both platforms verified **60 HTML pages / 1,782 asset references**, environment
restoration and the static-directory copy.

[Browser and connector CI](https://github.com/jcsdxhe/DB-GPT/actions/runs/38029229054)
**passed** on the same revision: **54 Chromium cases in each of production and
development**, and **105 connector/database tests**. Archived browser JSON and
JUnit were inspected: no failures, errors, skipped or flaky cases.
Final review-head runs are recorded in the PR body.

Local focused backend tests: **88 passed / 4 deprecation warnings**, with Git
Bash on PATH and a task-owned pytest temporary directory. TypeScript passed;
ESLint reported **0 errors / 89 existing warnings**; **45 build contracts**,
**24 frontend unit tests** and Wiki assertions passed. Changed Python passed
Ruff **0.16.10** check/format; actionlint passed.

An expanded native Windows run initially produced 17 failures: 15 existing
attachment fixtures supply backslash paths to the forward-slash API contract,
and two shell cases selected the wrong environment before Git Bash was
configured. The latter two passed in the focused rerun. These initial failures
are retained; they are not reported as a successful Windows full-suite run.
The full contract suite is also run on Linux CI.

## Boundaries

A finite successful live run does not guarantee future model-provider
availability or the correctness/security of all generated code. The generated
skill is a validation artifact, not installed globally or committed to the
application. Financial narrative and ratios are not independently audited.

Earlier Copilot 403, full-core mypy, Windows Docker and other untested integrations
retain their dated status. The local Node dev-server approval block was not
retried; development-browser checks use CI. PR #3278 is unchanged. Maintainers
still decide merge order and shared-change ownership.

Current merge-tree comparison has no conflicts with main
`ad203de5c7301c9a103caa1198d17aaee18c6647`, but **16 shared paths conflict**
with unchanged #3278 `80c947d3d6e0753e188d72e0444f01f1576f74a3`.
The new lifecycle-status test is one of those paths. No merge order is assumed.

Compact results, hashes and conflict paths are in
[skill-offline-validation.json](evidence/pr-3277/skill-offline-validation.json).
