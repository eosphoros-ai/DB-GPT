# PR #3277 baseline comparison follow-up — 2026-09-30

**The old toolchain installed and its dev server started, but neither target
page reached the measurement checkpoint. There are zero comparable baseline
latency samples.** The old-version navigation failures do not reproduce the
original fixture-response or SELECT-completion failures. This attempt cannot
determine whether the upgrade introduced those delays; upgrade involvement
cannot be excluded.

The existing upgraded-version evidence remains **20 skills cases + 20 SQL cases,
40/40 passed**. Those cases were not rerun for this follow-up. A separate direct
backend probe returned **10/10 successful skills responses**, but measures a
different path and cannot fill the missing browser comparison.

The [machine-readable evidence](evidence/pr-3277/baseline-followup.json) records
the commands, errors, timings, source versions and raw-log/trace hashes. This
report supplements the accepted [timeout investigation](pr-3277-flaky-investigation.md);
that earlier report and its evidence remain unchanged.

## Baseline preparation and stopping point

Official baseline: **`d1d398eb7ab2b2b3c9dc53fa376594a3600a7458`**.
Managed-worktree creation failed with `No space left on device` on D:.
The complete commit was instead exported with `git archive` into a separate
directory on C:, with its own dependencies, cache and runtime outputs. This
directory is an archive export, not a Git worktree. All **560 web files** match
the baseline Git blobs after normalizing Windows line endings; all **4,670
archived files** remained unchanged after the attempt.

| Step | Configuration and observed result |
| --- | --- |
| Runtime | Windows x64; Node **18.20.8**, Yarn Classic **1.22.22** |
| Install | Original `yarn install --frozen-lockfile --non-interactive`; exit **0**; unchanged `yarn.lock` and `package-lock.json` |
| Resolved application | Next **13.4.7**, React **18.3.1** |
| Dev | Original `NODE_OPTIONS=--max_old_space_size=16384 next dev`; server reported ready on localhost:5795 |
| Browser harness | Existing unchanged two cases; Node **20.19.6**, Playwright **1.62.1** Chromium; one worker, zero automatic retries |
| Deadlines | Navigation **120 s**, interaction/assertion **15 s**, Axios **10 s**, whole test **180 s**; all unchanged |

Yarn retained the existing mixed-lockfile and peer-dependency warnings; no
engine checks were bypassed and no dependency overrides were applied. Git Bash
interpreted the original POSIX-style dev script on Windows, without editing it.
Node/Yarn downloads were checked against their published checksums/integrity.

The intended design was ten sequential paired rounds on one fresh baseline dev
server, with a fresh browser context per case and no concurrent build or
production tests. The first pair failed before either timing checkpoint, so
sampling stopped instead of changing the baseline, tests or waiting limits.

| Baseline case | Route | Original error | Comparable samples |
| --- | --- | --- | ---: |
| `skill-search-toggle-and-markdown` | `/construct/skills/` | `TimeoutError: page.goto: Timeout 120000ms exceeded.` Waiting for `domcontentloaded`; zero recorded API requests | 0 |
| `monaco-sql-run-and-save` | `/chat/?scene=chat_dashboard&id=regression-editor&db_name=regression` | `TimeoutError: page.goto: Timeout 120000ms exceeded.` Waiting for `domcontentloaded`; zero recorded API requests | 0 |

The dev process stayed running during both attempts. Its log also contains
`Attempted import error: 'medianIndex' is not exported from 'd3-array' (imported as 'medianIndex').`
and `Error: read ECONNRESET`. These are contemporaneous diagnostics, **not a
verified cause** of the navigation timeouts. No repair or further cause
investigation was attempted. Both temporary services used in this follow-up
were stopped afterward.

## Disk/environment limitation — follow-up snapshot, not a historical sample

A single read-only capacity query during this documentation follow-up returned:

| Volume | Free space | Total capacity | Role |
| --- | ---: | ---: | --- |
| D: | 7.573 GiB | 624.999 GiB | Existing project and unchanged browser harness |
| C: | 3.675 GiB | 301.172 GiB | Independent baseline source, dependencies, dev output and probe runtime |

These are **current follow-up values**, not measurements taken during the earlier
120-second navigation attempts. No contemporaneous free-byte sample for those
attempts was retained, so the current values must not be backdated. The retained
historical evidence does establish `No space left on device` during the initial
D: worktree/export attempt; the actual baseline dev experiment then ran on C:.

Disk exhaustion can prevent filesystem-cache/output writes and may materially
affect cold compilation. Webpack's [filesystem-cache documentation](https://webpack.js.org/configuration/cache/#cachetype)
describes its disk-backed cache path. Here, however, there is no measured disk-I/O
breakdown or demonstrated C: cache-write failure tying disk pressure to either
navigation timeout. Storage headroom is an environment limitation and a possible
confounder, **not an established cause**. The navigation-timeout cause remains
unlocated. This attempt is **not an old-version performance conclusion**; it
records only that the control produced no valid comparable samples. No cleanup
or repeat baseline experiment was attempted in this follow-up.

## What the two timing series measure

The skills test intercepts `/api/v1/skills/list` and returns fixed JSON through
Playwright's `route.fulfill()`. Its response-time series measures that
fixture-backed request, not a real backend request.

The SQL test uses the same interceptor, including the
`/api/v1/editor/db/tables` metadata response. The editor supplies in-memory
schema/table/column data to its completion service. The recorded interval begins
at the visibility assertion after typing `SEL` and triggering completion; it
ends when the `SELECT` option appears. It is a frontend completion wait involving
the plugin/worker, not a SQL-query duration or a backend-response duration.
The normal application does load metadata through an API; the absence of a real
backend here is specific to these fixture tests.

The interception and payloads can be inspected in the
[browser harness](../../tests/web-toolchain/toolchain.spec.cjs) and
[fixtures](../../tests/web-toolchain/fixtures.cjs), and the metadata callbacks in
[the SQL editor](../../web/components/chat/db-editor.tsx).

## Side-by-side timing evidence

Upgraded application: **`763eba34c31a0ce4b07742bdcdfb05474f85f733`**,
Node 20.19.6 / npm 10.8.2 / Next 16.3.0, development mode. Values below reuse
the existing [20 paired rounds](evidence/pr-3277/flaky-investigation.json),
including four fresh-server rounds and sixteen warm-server rounds. Each series
has **20 samples**, not 40. The requested baseline series has **0 samples**.

| Timing series | Version | Comparable samples | Minimum | Median | Maximum |
| --- | --- | ---: | ---: | ---: | ---: |
| Complete skills fixture request | Baseline | 0 | N/A | N/A | N/A |
| Complete skills fixture request | Upgraded, existing runs | 20 | 501.603 ms | 557.224 ms | 8,268.187 ms |
| SELECT visibility assertion wait | Baseline | 0 | N/A | N/A | N/A |
| SELECT visibility assertion wait | Upgraded, existing runs | 20 | 846.787 ms | 882.929 ms | 4,251.342 ms |

| Series / version | ≤ 1 s | > 1–5 s | > 5 s and below deadline | At/above deadline | Deadline |
| --- | ---: | ---: | ---: | ---: | ---: |
| Skills / baseline | N/A | N/A | N/A | N/A | 10 s |
| Skills / upgraded | 18 | 1 | 1 | 0 | 10 s |
| SELECT / baseline | N/A | N/A | N/A | N/A | 15 s |
| SELECT / upgraded | 13 | 7 | 0 | 0 | 15 s |

The original baseline runtime defaults were retained, including its 16 GiB heap
option; the upgraded runs used their 8 GiB default. With no usable baseline
observations, this is neither a performance benchmark nor evidence that the
old version did or did not share the original delays. A 120-second navigation
failure must not be counted as a 10-second skills-response or 15-second
completion failure.

## Alternative evidence: direct real-backend skills requests

The existing API-only regression launcher was copied unchanged and used to load
the official baseline Python source. Its existing test configuration was reused
in memory, with fresh isolated metadata/home storage. The launcher's existing
runtime setup disables the static frontend mount, embeddings and rerankers and
initializes the isolated metadata schema; endpoint code was unchanged. The
imported server path was verified to be inside the baseline export.

Ten sequential `GET /api/v1/skills/list` requests bypassed the browser, Next and
the fixture interceptor. Timing used a monotonic clock through receipt of each
complete body, a 10-second request timeout and 200 ms between requests. All ten
returned **HTTP 200**, `success: true`, five items and the same body hash.

| Sample | Response time |
| --- | ---: |
| 1 | 417.173 ms |
| 2 | 21.587 ms |
| 3 | 12.900 ms |
| 4 | 21.945 ms |
| 5 | 15.674 ms |
| 6 | 18.224 ms |
| 7 | 23.907 ms |
| 8 | 432.523 ms |
| 9 | 13.513 ms |
| 10 | 1,463.170 ms |

Minimum **12.900 ms**, median **21.766 ms**, maximum **1,463.170 ms**;
**9** responses at or below 1 s, **1** above 1 s and at or below 5 s, **0** above
5 s. These observations establish the response times of this backend endpoint
under this isolated configuration only. Payload/runtime state differ from the
browser fixtures; they do not measure fixture dispatch, Axios/UI behavior,
worker initialization or SELECT visibility. They do not explain the original
timeouts, support attributing them to the backend, or support any conclusion
about upgrade correlation in either direction.

### Why 8.27 seconds and 21.766 milliseconds are not comparable

The complete browser scenario includes page loading, component mounting and
potentially serial dependent requests. A direct HTTP probe omits that surrounding
work. **The specific 8,268.187 ms value, however, times only the skills request
from its recorded start to completion; it is not the whole page-load duration.**
Navigation or mounting that finished before that request cannot be added to its
measured interval. Concurrent browser/test-runner work can affect scheduling,
but its contribution was not measured.

The 8.27-second observation is the **maximum of 20 fixture-backed browser
requests**, whereas 21.766 ms is the **median of 10 real-backend direct requests**
(whose maximum is 1,463.170 ms). These differ in both measurement path and
summary statistic. The fixture returns a different payload from the real probe;
no backend handles that intercepted browser request at all.

Existing timestamps locate about **8,254.688 ms** between request start and the
beginning of fixture fulfillment. They do not break that delay down into browser
work, test-process scheduling, I/O or other contributors; its detailed cause is
**unconfirmed**. The direct-backend measurements therefore **cannot explain the
8.27-second observation** and **do not support “the delay came from the backend.”**
No inference about association with the Next.js upgrade is drawn from this
probe. All timing values in this clarification reuse the previous records;
no additional samples were collected.

No direct SQL request was substituted for the missing SELECT timings: a backend
query would measure a different event. No backend latency root cause was
investigated and the nine earlier live integration checks were not rerun.

## Existing warning and browser-mode evidence

The [regression checklist](pr-3277-regression.md) now states prominently that,
under the same **ESLint 9.39.5 configuration**, all **86** current warnings match
the official baseline, with **0 added**. The earlier 87-warning baseline loses
one Monaco dependency warning in the candidate. This reconciles existing logs;
it is not a new lint run or a claim about the baseline's old ESLint 8 config.

The recorded Chromium **42/42**, Firefox **41/41** and WebKit **41/41** suites
used **`npm run build` output served by `npm start`**. A separate **development**
Chromium run passed **42/42**. Existing command/server logs confirm these modes;
none of those complete suites was rerun for this follow-up.

This follow-up changes documentation and evidence only. It changes no application
source, fixtures, assertions or timeout, and does not alter PR #3278 code. The
accepted flaky investigation remains intact. These previously local findings
are included in the documentation publication; no comparison or regression was
rerun for publication.
