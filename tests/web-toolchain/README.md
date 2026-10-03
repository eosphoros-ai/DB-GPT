# Frontend toolchain browser regression

This suite checks the existing DB-GPT frontend with deterministic API fixtures.
It contains 29 page-entry cases and 13 interaction cases. The application runs
from `web/`; this separate package does not change its dependency installation.

## Run

Use Node 20.19.6 and npm 10.8.2 to match the recorded validation.

1. In `web/`, install with `npm ci`. Start `npm run dev`, or run
   `npm run build` followed by `npm start` for production verification.
2. Wait for Next to report that the server is ready. The suite allows 120
   seconds for navigation and 180 seconds per case, including cold compilation.
3. In this directory:

   ```sh
   npm ci
   npx playwright install chromium
   npm test
   ```

`REGRESSION_URL` overrides `http://127.0.0.1:3000`; `REGRESSION_MODE` names the
result folder, and `REGRESSION_OUTPUT` changes its root directory. For example,
in PowerShell:

```powershell
$env:REGRESSION_URL = 'http://127.0.0.1:5790'
$env:REGRESSION_MODE = 'dev'
npm test
```

Development validation uses the launcher's default 8 GB heap. An explicit
`NODE_OPTIONS` heap setting remains supported. Development disables Webpack's
cache to prevent retained editor/chart modules accumulating during navigation;
production retains caching. SQL formatting uses the existing `sql-formatter`,
and completion still uses the unchanged OB SQL workers. The SQL case exercises
completion, formatting, execution and saving the edited query. Shared zero-step
replay verifies final-answer formatting and restarting the replay. A separate
JSON-answer case preserves closing delimiters and escape sequences across page
reloads and replay restarts.

`REGRESSION_BROWSER` selects `chromium` (default), `firefox` or `webkit` after
installing that Playwright browser. For a portable page-entry pass, use
`npm test -- --grep 'route:'`. The full Chromium suite additionally checks
clipboard permissions and downloads. `REGRESSION_NAVIGATION_TIMEOUT` can override
the navigation timeout for diagnostics; record any override with the results.

Firefox and WebKit do not accept Chromium's clipboard permission pair. Run their
41 portable cases with `npm test -- --grep-invert markdown-chart-sql-data-and-download`.
That excluded compound case covers clipboard, chart tabs and PNG download in
Chromium; it is not reported as passed in the other browsers. SQL editing uses
the browser's shortcut convention, including Windows WebKit's macOS key bindings.

## Evidence and limits

Each case saves its URL, API requests, console warnings/errors, uncaught
exceptions, failed requests, HTTP errors, accessibility snapshot and screenshot.
The JSON reporter saves assertion outcomes; failed cases also save traces.
Chart and workflow exports are saved and checked for successful download.

Assertions require zero console warnings/errors, uncaught exceptions, failed
HTTP responses or unexpected fixture requests. Network failures are also fatal,
apart from navigation-cancelled `ERR_ABORTED` requests. Missing images and external
icon scripts have no allowlist. Raw observations remain in each case's record.

API fixtures exercise browser rendering, forms, uploads, downloads and request
construction. They do not prove backend persistence, model inference, database
execution, authorization, connectors or scheduled-job execution. Those need
separate live-service checks. Tests never contact a real backend.

Recorded findings and remaining coverage are in
[the PR #3277 regression report](../../docs/frontend-toolchain/pr-3277-regression.md).
