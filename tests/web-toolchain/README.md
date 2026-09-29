# Frontend toolchain browser regression

This suite checks the existing DB-GPT frontend with deterministic API fixtures.
It contains 29 page-entry cases and 11 interaction cases. The application runs
from `web/`; this separate package does not change its dependency installation.

## Run

Use Node 20.19.6 and npm 10.8.2 to match the recorded validation.

1. In `web/`, install with `npm ci`. Start `npm run dev`, or run
   `npm run build` followed by `npm start` for production verification.
2. Wait for the first requested page to finish compiling. The Windows cold
   compilation can exceed the suite's 120-second navigation timeout.
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

The Windows validation also records a separate development run started with
`$env:NODE_OPTIONS = '--max-old-space-size=12288'`. This is a documented test
environment adjustment after a default-heap restart, not evidence that the
default development configuration passed. See the regression report.

## Evidence and limits

Each case saves its URL, API requests, console warnings/errors, uncaught
exceptions, failed requests, HTTP errors, accessibility snapshot and screenshot.
The JSON reporter saves assertion outcomes; failed cases also save traces.
Chart and workflow exports are saved and checked for successful download.

The assertions retain two explicitly disclosed resource exceptions: missing
`/images/bg.png` and the existing external iconfont script. Neither is mocked or
removed from the records. Passing means that the asserted UI behavior works
and no additional HTTP/network failures or uncaught exceptions were observed;
it does **not** mean that the console was empty. Console diagnostics still
require review, especially development-only component deprecations.

API fixtures exercise browser rendering, forms, uploads, downloads and request
construction. They do not prove backend persistence, model inference, database
execution, authorization, connectors or scheduled-job execution. Those need
separate live-service checks. Tests never contact a real backend.

Recorded findings and remaining coverage are in
[the PR #3277 regression report](../../docs/frontend-toolchain/pr-3277-regression.md).
