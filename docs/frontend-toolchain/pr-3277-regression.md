# PR #3277 frontend regression — 2026-09-29

This is an independent validation of the toolchain PR. No Dashboard changes
from PR #3278 were included. Checked boxes refer only to the explicitly stated
scope; fixture-backed browser checks are not backend acceptance tests.

Application and backend source: `ae095321f2f93d1536fdead00b1484d2637b96d9`.
The regression follow-up changes the Next launcher to honor an explicit
`NODE_OPTIONS` heap limit, and adds tests and this report. No application UI or
Python backend source was changed by that follow-up.

Environment: Windows x64, Node **20.19.6**, npm **10.8.2**, Next **16.3.0**,
Playwright **1.62.1**, Chromium. Production used `npm run build` and `npm start`;
development used `npm run dev`. Separate build directories and an isolated PR
checkout were used. The browser suite uses local deterministic API fixtures.

## Build and tooling

- [x] Windows `npm run build`: exit 0; TypeScript checking and page generation
  completed; **60 HTML files and 1,755 local asset references** verified.
- [x] Windows production server started and served the built application.
- [x] Production browser suite: **40 / 40 passed**, no retries or skipped cases.
- [x] Updated build/compatibility contracts: **21 discovered, 19 passed,
  2 POSIX-only tests skipped on Windows**.
- [x] Launcher tests verify the actual child V8 heap limit, preservation of other
  Node flags, the 8 GB default, and explicit 12 GB / 2 GB settings. They pass on
  Node 20 and Node 24.
- [x] Earlier Linux/macOS CI on `ae095321` passed clean `npm ci`, type checking,
  lint, 18 previous build/compatibility tests, 20 existing frontend tests,
  production build and static export. [Actions evidence](https://github.com/jcsdxhe/DB-GPT/actions/runs/36565457316).
- [ ] Development suite after the launcher correction: validation in progress.
- [ ] Default 8 GB development configuration passes a complete cold traversal:
  **not established**; the observed run triggered Next's memory-threshold restart.
- [ ] Browser console is completely clean: **not passed**; see findings below.

The 60 generated HTML files include framework/component routes. They are not
claimed as 60 independently tested user workflows.

## Browser functionality checklist

All checked items below passed in the **production browser with API fixtures**.
The suite contains **29 page-entry cases and 11 interaction cases**. It verifies
page bodies, uncaught exceptions, HTTP/network failures, and fixture coverage;
interactions assert visible outcomes and/or the expected request or download.

| Module | Verified behavior | Production |
| --- | --- | --- |
| Home and navigation | Home renders; sidebar navigation; construct tabs; return home | Pass |
| Conversations | Conversation list page and existing chat history render | Pass |
| Desktop chat | Human/assistant messages, Markdown, SQL syntax highlighting, table and math render | Pass |
| Chat clipboard | Copy SQL and verify clipboard contents | Pass |
| Chat visualization | AntV canvas renders; Chart / SQL / Data tabs switch; PNG download succeeds | Pass |
| Mobile chat | Mobile app route with valid `chat_scene` and `app_code` renders | Pass |
| Data sources | List/type cards; required-field validation; select SQLite; submit connection test and create request; dialog closes | Pass |
| Knowledge spaces | List, search control, detail route and graph route render | Pass |
| Knowledge upload | Create form, Markdown file selection, advanced settings, upload and sync requests, completion closes dialog | Pass |
| Applications | List/filter controls render; create app; navigate to configuration with saved app name | Pass |
| AWEL workflows | List and ReactFlow canvas render; node search and mode switch; JSON export downloads and parses | Pass |
| Models | Model list and provider configuration render; required API-key validation; fixture connection feedback | Pass |
| Plugins and DBGPTs | Plugin and DBGPT entry pages render | Pass |
| Prompts | Prompt list and dynamic Markdown editor load | Pass |
| Connectors | Connector management page renders | Pass |
| Skills | Search filters the list; enable switch changes; detail Markdown renders | Pass |
| Scheduled tasks | List/run-history routes; search; enable toggle; name/question/frequency edit and save request | Pass |
| SQL/chart editor | Monaco initializes; edit SQL; Run renders a result table; Save sends the updated chart-editor request | Pass |
| Evaluation | Evaluation/model-evaluation/dataset routes; switch dataset/evaluation tabs; launch form opens | Pass |
| Observability | Overview, traces and data-index pages render | Pass |

- [x] All 29 production page-entry assertions passed.
- [x] All 11 production interaction assertions passed.
- [x] No uncaught browser JavaScript exception in these 40 production cases.
- [x] No additional asset/network failures beyond the disclosed background image
  and external iconfont exceptions; those exceptions remain in the records.
- [x] Browser console, request failures and failed HTTP responses were recorded.

## Checks against existing live resources

The backend was loaded from the independent PR checkout, using the project's
existing external test configuration and its configured model. A separate
metadata database and a copy of the existing Walmart SQLite example were used.
The test launcher bootstrapped ORM tables because that configuration disables
automatic migrations; it served APIs while Next served the actual frontend.
Credentials were not copied into the repository or this report.

- [x] **19 live-service page entries** render without an uncaught exception.
  This is a render check, not proof that every page's API succeeded.
- [x] Real configured model **deepseek-v4-flash**: browser sends a short normal
  chat prompt, receives `PR3277_OK`, and restores the response after refreshing
  from persisted conversation history. No API fixture intercepted this test.
- [x] Real SQLite: create a connection through the browser to an isolated copy
  of the project's Walmart example; verify the saved connection; execute a
  read-only query through the existing SQL endpoint and receive one table.
- [x] Real knowledge space: create through the browser, upload a small Markdown
  document, and verify the space/document in the live APIs. The document API
  reports `FINISHED`. This does not prove semantic retrieval quality.
- [ ] Evaluation end-to-end: `/api/v1/evaluate/evaluations` and
  `/api/v1/evaluate/datasets` return **404** from the current test backend.
- [ ] Semantic knowledge retrieval: the configured `text-embedding-3-small`
  endpoint returns **404** on a real embedding request. The isolated backend
  therefore runs without an embedding worker.
- [ ] Third-party OAuth, connector authorization/synchronization and non-SQLite
  database engines: no matching usable test credentials/resources were found.
- [ ] Agent/tool execution, published-app execution, non-empty AWEL workflows,
  scheduled execution, full benchmark jobs and all destructive CRUD variants:
  not covered end-to-end by this frontend regression.
- [ ] Firefox, WebKit/Safari and real mobile devices: not covered by this run.

## Findings that must remain visible

1. **Development memory restart.** A cold traversal under the default 8 GB
   launcher setting triggered Next's memory-threshold restart. The first cold
   navigation also exceeded the browser timeout. The attempted 12 GB run initially
   suffered the same issue because `run-next.cjs` silently replaced the supplied
   limit. The follow-up fixes that override and adds child-process tests. It does
   not claim a memory-use reduction or prove that 8 GB is sufficient.
2. **Missing background image.** `/images/bg.png` returns 404 on several pages.
   The reference in `tailwind.config.js` and the missing public file also exist in
   the base source `d1d398eb`. This is not a new reference introduced by the PR.
3. **External iconfont.** The existing `at.alicdn.com` script intermittently
   returns a network/chunked-encoding error or 503 in this environment. The script
   reference is identical in the base source. It is not stubbed to hide the error.
4. **Development console diagnostics.** Image sizing/LCP warnings and an HMR
   `isrManifest` warning with a `TypeError` were observed. They require explicit
   disclosure even when a page assertion passes; production cases did not show
   this HMR diagnostic.
5. **Evaluation backend routes.** The frontend request paths and backend source
   are unchanged by this PR, but live evaluation APIs failed as described above.
   No old-toolchain browser run was performed, so source comparison alone is not
   presented as a full before/after behavioral comparison.

The browser suite explicitly retains known resource exceptions in its evidence.
A green suite therefore means the listed assertions passed, **not** that every
feature is fully accepted or that all console/network diagnostics are absent.

## Reproduction

See [the isolated browser test package](../../tests/web-toolchain/README.md).
It has its own pinned Playwright dependency and does not alter the application
dependency graph. The fixture suite requires no model key or backend.

Live checks additionally require the existing private test configuration; that
configuration, its credentials, runtime databases and raw backend logs are not
committed. Preserve fixture/live distinctions when repeating the checklist.
