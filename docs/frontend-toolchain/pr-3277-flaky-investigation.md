# PR #3277 development timeout investigation — 2026-09-30

**Both original failures were wait/deadline expirations; no mismatched business
value was observed before either failure.** The unchanged two cases subsequently
passed **20 rounds each (40/40)**, including four fresh development servers.
These observations do not establish a product defect introduced by Next.js 16.
The investigation is closed within its verified scope: failure classification,
recorded timing relative to the unchanged deadlines, and targeted repetition.

This PR contains no Python/backend source changes. The skills request was
intercepted by a test fixture; the SQL failure waited for frontend completion
to become visible. These measurements do not measure real backend first-query
latency. No backend first-query latency investigation was performed as part of
this frontend-toolchain closeout.

Application source: `763eba34c31a0ce4b07742bdcdfb05474f85f733`. Repeated-test checkout:
`1401f85150d47852732c6aa6fc3e73f53e1cb475`; the commits between them change reports/evidence only.
Windows x64, Node 20.19.6, npm 10.8.2, Next 16.3.0, Playwright 1.62.1 Chromium.
[Machine-readable timings and all 40 case results](evidence/pr-3277/flaky-investigation.json).

## Original errors and affected pages

| Case | Page | Original error | Classification |
| --- | --- | --- | --- |
| `skill-search-toggle-and-markdown` | `/construct/skills/` | `TimeoutError: locator.click: Timeout 15000ms exceeded`, waiting for the last switch | Element wait timed out after the list request failed; no wrong switch state was observed |
| `monaco-sql-run-and-save` | `/chat/?scene=chat_dashboard&id=regression-editor&db_name=regression` | `expect(locator).toBeVisible() failed`, `Timeout: 15000ms`, `element(s) not found` for the `SELECT` option | Visibility assertion exhausted its polling timeout; completion still showed `Loading...`; no wrong SQL value was observed |

The second error uses an assertion API, but its actual failure condition is
**the option never becoming visible before the deadline**. The Run/Save SQL value
assertions occur later and were not reached in that failed attempt.

## What the original timeline establishes

**Skills:** the page was revisited partway through the 42-case suite, not merely
on server startup. Its recompilation took about 37.2 seconds. The subsequent
fixture-backed `/api/v1/skills/list` request started at **04:18:16.642 UTC**;
the test runner began `route.fulfill()` at about **04:18:27.470 UTC** — a
**10.828-second delay**. The browser recorded
`AxiosError: timeout of 10000ms exceeded`, and the page's existing error path
left the skill list empty. Consequently there was no skill switch to click.
The response was intercepted by the test fixture; no real backend was contacted.
The recorded chain is therefore: delayed fixture response exceeds the existing
Axios deadline, the list is left empty, and the switch wait expires.

**SQL completion:** Next served the HTML in **16 ms**; the browser's complete
document request took about **31 ms**. The completion-plugin chunk took about
4.2 seconds and the editor worker request about 5.5 seconds. The MySQL worker
asset was recorded as HTTP 200, but a successful asset response does not prove
that the worker has initialized or completed its RPC. At **04:19:53.147 UTC**,
the test began waiting for `SELECT`; the 15-second deadline expired with
`Loading...` still visible and no browser console/uncaught error recorded.
This establishes a completion-availability deadline failure. It does not locate
the wait at a real backend query.

Thus “first cold compilation took longer than 15 seconds” is not an adequate
root-cause statement. The tests separately allow **120 seconds for navigation**
and **15 seconds for interaction/assertion waits**.

## Repetition design and observed results

- No application, fixture, assertion or timeout changes.
- **20 consecutive rounds**, each executing the two original cases once.
- **Four blocks of five rounds**. Each block starts `npm run dev` with a new
  output directory. Round one is cold for that server; the next four reuse it.
  Totals: **4 cold-server rounds + 16 warm-server rounds**.
- A fresh browser context for each case, one worker, **zero automatic retries**.
- Full Playwright traces retained for every run; distinct output folders prevent
  a later pass from overwriting an earlier result.
- One Next serving process per block; no restart during its five rounds.
- **40 passed, 0 failed, 0 skipped**. The diagnostics in these cases contain no
  console warnings/errors, uncaught exceptions, HTTP errors, unexpected fixture
  paths or non-aborted network failures.

The 40 executions comprise **20 skills cases and 20 SQL-editor cases**. Each
timing series below has 20 samples; SQL completion waiting is not an HTTP
response-time measurement. All values come from the existing recorded runs.

| Measured interval across the repeats | Samples | Minimum | Median | Maximum |
| --- | ---: | ---: | ---: | ---: |
| Skills request → fixture starts fulfilling | 20 | 495.5 ms | 550.6 ms | 8254.7 ms |
| Skills complete request | 20 | 501.6 ms | 557.2 ms | 8268.2 ms |
| SELECT visibility assertion wait | 20 | 846.8 ms | 882.9 ms | 4251.3 ms |

| Timing series | Samples | ≤ 1 s | > 1–5 s | > 5 s and below deadline | At/above deadline | Deadline |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Skills fixture request | 20 | 18 | 1 | 1 | 0 | 10 s |
| SELECT completion visibility wait | 20 | 13 | 7 | 0 | 0 | 15 s |

Five slowest recorded samples in each series:

| Rank | Skills request (round; status) | SELECT visibility wait (round; status) |
| --- | --- | --- |
| 1 | 8.268 s (round 12; passed) | 4.251 s (round 11; passed) |
| 2 | 3.297 s (round 11; passed) | 1.422 s (round 8; passed) |
| 3 | 0.608 s (round 9; passed) | 1.417 s (round 10; passed) |
| 4 | 0.588 s (round 19; passed) | 1.387 s (round 9; passed) |
| 5 | 0.572 s (round 15; passed) | 1.383 s (round 12; passed) |

The SELECT measurement starts at the assertion, after typing `SEL` and triggering
completion. It is not the total editor/worker initialization time. Timings and
sampled memory/event-loop metrics describe these runs; they are not a benchmark.
The slowest skills response took **8.268 seconds** in round 12, below the
unchanged **10-second** limit, and that case passed. In the original failed run,
fixture fulfillment only began after **10.828 seconds**, already beyond that
same deadline. Together these observations support the threshold explanation
for the skills failure: a slow response can pass while it stays within the
deadline, and the original delayed fixture response crossed it. The 20 recorded
skills responses range from 0.502 to 8.268 seconds, demonstrating timing
variation in this local test environment. No pre-upgrade timing baseline was
recorded, so the data do not date the origin of that variation.

SQL completion waits in the successful rounds range from **0.847 to 4.251
seconds**, within their unchanged **15-second** deadline. The original SQL
failure exhausted that visibility deadline. This supports its classification
as a wait timeout; it does not turn the measurement into backend response time.

## Reproduction

Use the dependency/runtime versions above and the existing
[isolated test package](../../tests/web-toolchain/README.md). In each block, start
the unmodified app with a distinct `NEXT_DIST_DIR`, then execute the following
command five times, assigning each invocation a distinct `REGRESSION_MODE` and
`REGRESSION_OUTPUT` directory. Stop that server before the next block. The actual
investigation used port 5794 and fresh `.next-pr3277-flaky-block-1` through `-4`.

```sh
# From tests/web-toolchain; REGRESSION_URL points to the current dev server.
npx playwright test --grep 'interaction: (skill-search-toggle-and-markdown|monaco-sql-run-and-save)$' --trace=on
```

The application receives its normal heap default. An external diagnostic preload
samples process memory and event-loop delay once a second; it does not change
page logic or test assertions. Original traces remain local; the public evidence
includes their SHA-256 digests and sanitized relevant timestamps.

## Conclusion and scope of closeout

- [x] Identify both pages and original errors: both are wait/deadline failures.
- [x] Establish the skill failure's immediate chain: fixture response missed
      Axios's deadline → empty list → missing switch.
- [x] Repeat both unchanged cases 20 times with cold and warm development runs:
      **40/40 passed**.
- [x] Document the recorded timing distribution and threshold behavior while
      preserving the original **10-second / 15-second** limits and assertions.

The verified failure classification and repeated results are complete for this
closeout. They do not establish a Next.js 16-induced product defect. Backend
first-query latency attribution, a controlled reconstruction of the original
concurrent workload, and a pre-upgrade timing comparison are outside this
closeout; no further investigation or additional test rounds were performed.
No backend code, timeout, assertion or case code was changed for this closeout.

The previously recorded nine real-backend integration checks remain evidence for
`80d7c703`, before the review fixes. The review fixes concern `NODE_OPTIONS`
handling and JSON answer/replay presentation, with accompanying tests and
documentation. They do not change API request construction, transport, or backend
source. Based on that scope, the nine integration checks were **not rerun**;
their source version is identified separately. JSON presentation does execute
in the application, so these earlier integration results are not relabeled as
a fresh run of the later code.
