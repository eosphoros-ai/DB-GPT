# PR #3277 OAuth and connector validation — 2026-10-09/10

This follow-up tests the standalone toolchain branch based on
`f0c1d69fedb7cb6ac26acd73f1a0fb3318c42f30`. Application fixes are in
`a04e9568f4f0509439ef12561e5627dacb9be5e8`; workflow/test corrections extend
through `18a5527c2a929481bf5ac9f6a69bae863e8ed846`. The PR body records the final
documentation-inclusive SHA and its CI runs. These results do not validate
Dashboard PR #3278 or every DB-GPT product feature.

## Fixes found by the checks

- Implement the missing `dbgpt.model.utils.copilot_auth` module already imported
  by the provider API. Use the deployment's own Device Flow OAuth App Client ID,
  configured as documented in [model providers](../docs/getting-started/model-providers-ui.md).
  No client secret, access token or tester's Client ID is committed.
- Respect GitHub's device-code expiry and add five seconds to the polling
  interval after **each** `slow_down`. Cancelled dialogs stop polling. Show
  the backend's access-denied reason instead of treating a Copilot 401/403 as
  proof of an invalid API key.
- Persist MCP handshake failures as connector errors on create/update, including
  when the runtime manager records the failure without raising. Restore active
  connectors using the asynchronous startup hook so an already-running event
  loop does not prevent rehydration. Preserve legacy credential reactivation.
- Add repeatable OAuth protocol/browser tests, connector recovery tests and
  disposable MySQL/PostgreSQL integration tests. A dedicated CI workflow runs
  the backend suite and Chromium in production and development modes.

The missing OAuth module and connector lifecycle failures were found while
testing existing backend features. They are not attributed to the Next.js
upgrade without comparative evidence.

## Results and boundaries

| Check | Accepted result | Scope |
| --- | --- | --- |
| Local TypeScript and ESLint | Pass; 0 errors / 89 lint warnings | Windows, Node 20.20.2, npm 10.8.2, Next.js 16.3.8 |
| Local frontend tests | 43 build contracts passed / 2 POSIX skips; 24 frontend tests plus Wiki assertions passed | Type checking remains enabled |
| Local production build / static export | Both passed; each verified 60 HTML files and 1,782 asset references | Current application source |
| Ubuntu and macOS frontend CI | Both passed on application commit `a04e9568` | [Run 37955936648](https://github.com/jcsdxhe/DB-GPT/actions/runs/37955936648); later changes are test/workflow/docs only |
| Local backend tests | 101 passed, 3 reported warnings | OAuth/provider, runtime connectors, connector service and DuckDB |
| Backend plus real MySQL/PostgreSQL CI | 105 passed, 0 failures/errors/skips | [Run 37958592040](https://github.com/jcsdxhe/DB-GPT/actions/runs/37958592040); includes 4 real database cases |
| Ruff / workflow syntax | Ruff 0.16.10 check and format pass on changed Python; actionlint 1.7.12 passes | No older Ruff version substituted |
| Production/development browser fixtures | 46 passed per mode; 0 failures/skips/retries in each | [Run 37958592040](https://github.com/jcsdxhe/DB-GPT/actions/runs/37958592040); Chromium, API fixtures; includes 4 new OAuth cases |
| Real GitHub device authorization | Device authorization approved; OAuth token issued | User completed GitHub consent from DB-GPT's provider dialog |
| Real Copilot connection | **Blocked: HTTP 403** from Copilot credential exchange | User has no confirmed Copilot entitlement; account/app permissions are unresolved. Model activation, inference and refresh are not verified |
| Actual local MCP transports | 15 protocol/API checks passed | Streamable HTTP without auth and with bearer auth; SSE with header auth; discovery, read-only calls, credential preservation, rejection/reactivation and API deletion |
| MCP restart recovery | Passed after async startup fix | Existing active connection and tools restored after backend restart |
| Real external DeepWiki MCP | Passed | Official public no-auth server; discover 3 tools, call `read_wiki_structure` on public `eosphoros-ai/DB-GPT`; remove isolated API connection |
| Real DuckDB through application API | 6 checks passed | Test/create/list, SQL sum, invalid SQL response, edit/persist, delete isolated connection |

In each browser mode, the 42 existing route/interaction records contain zero
console diagnostics, page errors, unexpected API calls, non-navigation network
failures or bad HTTP responses. The four new OAuth cases separately assert their
authorization behavior.

MySQL 8.4 and PostgreSQL 16 checks use actual DB-GPT connectors against isolated
CI service databases: create tables/data, rediscover schema, read/update/aggregate,
reject invalid SQL, recover with a valid query and drop only the test tables.
This is driver-level integration, not full browser CRUD for those databases.

The MCP create UI was exercised on the previous production frontend with the
candidate backend; connector frontend source did not change. The broader MCP and
DuckDB checks call the real application APIs and drivers. Prepared UI edit/delete
scripts were **not executed**. API deletion does not establish revocation of
already-issued runtime tool packs.

DuckDB deletion/index plumbing used the existing cached local RoBERTa model.
No external model key was introduced; retrieval quality and AI answer quality
are outside this round. No third-party write operation was performed.

## Initial failures retained

- The first workflow run stopped before tests because `collaboration` is not an
  extra in this standalone branch. It was corrected to the branch's locked
  `base` installation; the following backend run passed.
- The first production browser CI run had **44 passes / 2 failures**. The OAuth
  assertion advanced virtual time beyond the next permitted poll; the Monaco
  test used the Windows formatting shortcut on Linux. The corrected test uses
  bounded polling times and the platform's actual shortcut, without dropping
  either assertion. Development tests did not run in that failed job.
- Before the polling fix, the corrected baseline harness exposed three OAuth
  failures (backoff, expiry, error detail), with cancellation passing.
- Local backend setup initially hit Windows temporary-directory permissions and
  a missing embedding runtime; isolated temp paths and the existing cached
  embedding environment resolved those setup issues. Intermediate harness
  failures and raw logs remain in the local evidence directory.
- Automatic execution review rejected starting the new local dev frontend,
  returning only `blocked by policy`. That action was not retried by another
  local route. The new dev browser check runs in isolated GitHub CI; a fresh
  local dev/Fast Refresh run is **not** claimed.

## Remaining coverage and review decisions

The four new browser OAuth cases use API fixtures; they do not replace the real
GitHub/Copilot result above. This round does not repeat Firefox, WebKit, Fast
Refresh, the prior nine live model scenarios, full-core mypy, or Docker checks.
Their earlier dated results remain in the [regression record](pr-3277-regression.md).

Copilot inference/refresh still needs a legitimately entitled account and a
compatible authorized app. Authenticated Feishu/Notion/Linear/DingTalk/Tavily
accounts, Oracle/SQL Server and other unprovided database systems remain
unverified. Redis's connector is currently a placeholder, not a completed
integration.

The candidate merges without conflicts in a read-only merge-tree check against
upstream `ad203de5c7301c9a103caa1198d17aaee18c6647`. Against #3278
`80c947d3d6e0753e188d72e0444f01f1576f74a3`, **10 shared paths still conflict**.
The older combined preview `347b387a` predates this follow-up and does not
validate it. Maintainers must still decide ownership and merge order; reconcile
against the actual merged tree and rerun relevant checks afterward.

## Reproduction and evidence

- Backend/real databases: see
  [connectors-auth-validation.yml](../../.github/workflows/connectors-auth-validation.yml).
  Local live DB tests explicitly skip if their respective test URL is absent.
- Browser: build/start or run dev, then execute `npm test` from
  `tests/web-toolchain` with `REGRESSION_URL`, `REGRESSION_MODE` and
  `REGRESSION_OUTPUT`. No real account is used by these browser fixtures.
- [Sanitized result manifest](evidence/pr-3277/connectors-auth-validation.json)
  separates real services, fixtures, source revisions and blocked checks.
- Local raw logs are retained under
  `output/pr-preparation/20261009-connectors-auth`; this path is a local evidence
  archive, not a claim that all raw logs are committed.
