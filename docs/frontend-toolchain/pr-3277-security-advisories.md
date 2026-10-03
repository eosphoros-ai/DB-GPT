# PR #3277 Next.js security applicability — updated 2026-10-03

## Current patch: Next.js 16.3.8

The current dependency declarations pin **Next.js and eslint-config-next 16.3.8**.
The patch is applied separately to PRs #3277 and #3278 without deciding their merge
order. The dependency lockfiles are regenerated with npm 10.8.2; regression results
are recorded in the respective PR validation reports and current-head CI links.

The matching Windows server advisory
[CVE-2026-75604](https://github.com/vercel/next.js/security/advisories/GHSA-p293-qw3h-jr36)
was first fixed in 16.3.3. The
[September release](https://nextjs.org/blog/september-2026-security-release) identifies
16.3.8 as the patch for the self-hosted Pages Router/SSG issue (CVE-2026-94543) and
development MCP disclosure (CVE-2026-94486). This upgrade includes those fixes.
The server advisories are not attributed to Python-only static-file deployments;
the MCP endpoint is a development-only feature. No exploit payload is executed.

The release notes disclose postponed fixes, so this is not a blanket security
clearance. The tables below retain the original 13.4.7/16.3.0 comparison and its
configuration evidence. Their references to an unresolved **16.3.0 candidate** and
the October 1 pending patch decision describe that historical review, superseded
by this patch; their historical regression results are not reused for 16.3.8.

## Historical assessment through 2026-10-01

**There is a concrete security reason to leave Next.js 13.4.7 for this project's
self-hosted Next server mode:** the baseline falls within the affected range of
a server crash/DoS advisory and two request-smuggling advisories, and its actual
configuration uses the affected rewrite proxy path. These are scoped
code/configuration matches, not successful exploit demonstrations. A deployment
that serves exported files through Python without running a Next server does
not expose those Next server paths.

The matching advisories are **CVE-2024-39693** (fixed in 13.5.0),
**CVE-2024-34350** (13.5.1) and **CVE-2026-29057** (15.5.13 / 16.1.7).
Their prerequisites and official links are retained individually in the table.

**The candidate pin, 16.3.0, is not fully patched as of this review.** In
particular, the later Windows-server RCE advisory includes Pages Router and
still affects 16.3.0; its fix is 16.3.3. The recorded Windows Next server mode
matches the advisory's deployment conditions. That unresolved issue is disclosed
separately below, not counted as a benefit of this PR.
[Official Windows advisory](https://github.com/vercel/next.js/security/advisories/GHSA-p293-qw3h-jr36).

The [September 30 follow-up](#september-30-release-follow-up--checked-2026-10-01)
also identifies **CVE-2026-94543** as a configuration match for this candidate's
self-hosted Pages Router/SSG production mode, and **CVE-2026-94486** for its
MCP-enabled development mode. Neither is fixed by the current 16.3.0 pin.
**CVE-2026-94483 does not apply:** no remote image patterns are configured, and
the existing build records an empty pattern list with Image Optimization disabled.

This is a read-only advisory/code review. No dependency, source, test or runtime
configuration was changed, and no vulnerability payload or regression was run.

## Scope and source versions

- Official baseline: `d1d398eb7ab2b2b3c9dc53fa376594a3600a7458`, Next **13.4.7**.
- PR head inspected: `7ac93ead9154ba28e1a325979b4cc73a75910e99`; latest application
  source is `763eba34c31a0ce4b07742bdcdfb05474f85f733`, Next **16.3.0**.
- The inventory uses the [Next.js maintainers' advisory list](https://github.com/vercel/next.js/security/advisories)
  and their [public advisory API](https://api.github.com/repos/vercel/next.js/security-advisories?per_page=100),
  checked against official release/security posts. The original September 30 snapshot has
  51 advisories in the interval, eight older entries and three later entries.
  A cross-check adds CVE-2023-46298, backed by the maintainers' [merged fix](https://github.com/vercel/next.js/pull/54732)
  and [release](https://github.com/vercel/next.js/releases/tag/v13.4.20-canary.13).
  Thus the original main table has **52 entries**, plus three later entries separately.
  The October 1 follow-up adds the seven September-release entries in a separate
  table; it does not alter the original snapshot's 52 + 3 inventory or credit
  those later fixes to 16.3.0.
  This is a catalogue count, **not a count of DB-GPT vulnerabilities fixed**.
- The interval ends at the [16.3.0 release](https://github.com/vercel/next.js/releases/tag/v16.3.0),
  published August 3, 2026. Representative stable fix versions are listed below;
  the linked advisories contain additional supported-branch/canary fixes.
  Later publications are not silently credited to 16.3.0.
- NextAuth-specific advisories and an audit of every transitive dependency are
  outside this Next.js inventory. A declared dependency is not evidence that
  the corresponding framework feature is used.

The [machine-readable review](evidence/pr-3277/security-review.json) retains the
official version fields, classification for every row, source-snapshot hash and
the inspected commit identities.

## Actual project usage

| Capability | Evidence in both inspected source versions | Applicability consequence |
| --- | --- | --- |
| Pages Router | Application routes are in `web/pages/`; `web/app/` contains only `chat-context.tsx` and `i18n.ts`, with no App Router page/layout/route entries | Pages Router does not imply use of RSC or Server Actions |
| App Router, Server Actions, PPR, Cache Components | No corresponding route entries, server/action/cache directives or enabling configuration found | Advisories requiring these capabilities are not project benefits |
| Middleware / Proxy authorization | No `middleware.*`, `_middleware.*` or `proxy.*` entry, `withAuth`, or `next-auth/middleware` use found | Do not attribute Middleware authentication bypass fixes to this application |
| NextAuth | `next-auth` is declared in `package.json`, but no import, NextAuth handler or `pages/api/auth` route was found in either tracked tree; `web/lib/session.ts` supplies iron-session helpers | The premise “NextAuth is configured as authorization Middleware” is not supported by this source |
| API proxy | `next.config.js` rewrites `/api/v1/:path*` to **`http://127.0.0.1:5670/api/v1/:path*`** in Node server mode | Request-smuggling advisories concerning external rewrite proxies apply to this shape; hostname-injection SSRF does not, because the hostname is literal |
| Image Optimization | `images: { unoptimized: true }` in baseline and candidate; no `remotePatterns`/`images.domains` configuration | Importing `next/image` does not enable the vulnerable optimization service in this configuration |
| Existing production image settings | The retained build's resolved config has `remotePatterns: []`, `domains: []`, `unoptimized: true` | CVE-2026-94483 is not applicable; do not count its fix as a DB-GPT benefit |
| Internationalization | `web/app/i18n.ts` uses client-side i18next; no Next config `i18n` exists | This is not Next's locale routing required by the Pages/Middleware i18n advisory |
| Pages data/cache behavior | No page-level `getServerSideProps`; the prompt route has `getStaticProps` plus `getStaticPaths` with `fallback: 'blocking'`; custom `_document` uses `Document.getInitialProps` | Do not infer arbitrary SSR/CDN cache conditions from Pages Router alone; deployment cache settings were not established |
| Existing SSG artifact | `/construct/prompt/add` and `/construct/prompt/edit` have `compute: static`, `srcRoute: /construct/prompt/[type]`, `initialRevalidateSeconds: false` in the retained prerender manifest | Matches the SSG prerequisite of CVE-2026-94543 when served by a self-hosted Next server; not attributed to Python-only static serving |
| Development MCP | `npm run dev` selects Webpack; the installed Next 16.3.0 Webpack hot reloader mounts MCP when `experimental.mcpServer` is enabled; its default and the retained resolved config are `true`, with no project override found | CVE-2026-94486 cannot be excluded by Pages Router or Webpack use; production does not serve this dev endpoint. No exploit/exposure request was performed |
| Script / generated social images | No `next/script` / `beforeInteractive` or `next/og` / `ImageResponse` use found | The corresponding script/OG input vulnerabilities are not used capabilities |
| Serving mode | `npm start` runs Next; static compile exports files, and `dbgpt_server.py` can mount those through FastAPI `StaticFiles` | Security exposure depends on which server actually accepts requests; the rewrite risks are not attributed to Python-only static serving |

Source references: [candidate config](../../web/next.config.js),
[baseline config](https://github.com/eosphoros-ai/DB-GPT/blob/d1d398eb7ab2b2b3c9dc53fa376594a3600a7458/web/next.config.js),
[package declaration](../../web/package.json), [session helpers](../../web/lib/session.ts),
[client i18n](../../web/app/i18n.ts),
[prompt static-data functions](../../web/pages/construct/prompt/%5Btype%5D/index.tsx),
[Python static serving](../../packages/dbgpt-app/src/dbgpt_app/dbgpt_server.py).

## Advisories fixed after 13.4.7 and by 16.3.0

“Applies” below means the old version and inspected Node deployment shape meet
the stated prerequisites. Reachability through an actual deployment's ingress
was not tested. “Not affected” is limited to this source/configuration and must
be reassessed if the omitted capability is enabled later. Unconfirmed items
are explicitly excluded from the security-benefit claim.

| Advisory / source | Fix version(s) | Impact | DB-GPT applicability |
| --- | --- | --- | --- |
| CVE-2023-46298<br>[GHSA-c59h-r6p8-q9wc](https://github.com/advisories/GHSA-c59h-r6p8-q9wc); [upstream fix](https://github.com/vercel/next.js/pull/54732) | 13.4.20-canary.13 (first published fix; included in later stable lines) | Missing cache-control on empty prefetch responses can let a CDN cache an unusable response. | Unconfirmed, not counted: 13.4.7 is in range, but the required empty-prefetch/CDN caching deployment is not established. The official upstream fix is PR #54732, commit 20d05958ff853e9c9e42139ffec294336881c648. |
| CVE-2024-34351<br>[GHSA-fr5h-rqp8-mj6g](https://github.com/vercel/next.js/security/advisories/GHSA-fr5h-rqp8-mj6g) | 14.1.1 | Server Action redirects can induce server-side requests to an attacker-controlled destination. | Not affected: this project does not use Server Actions. |
| CVE-2024-34350<br>[GHSA-77r5-gw3j-2mpf](https://github.com/vercel/next.js/security/advisories/GHSA-77r5-gw3j-2mpf) | 13.5.1 | Ambiguous HTTP request boundaries on rewritten routes can poison the response queue. | Applies to the self-hosted Next server path: 13.4.7 is affected and both inspected versions proxy /api/v1/:path* through rewrites. Static files served only by Python do not use this path. Exploitability behind a particular ingress was not tested. |
| CVE-2024-39693<br>[GHSA-fq54-2j52-jc42](https://github.com/vercel/next.js/security/advisories/GHSA-fq54-2j52-jc42) | 13.5.0 | Crafted requests can crash the Next server and deny service. | Applies to the Next server path: 13.4.7 is in the affected range and the official advisory does not require App Router or another optional feature. A Python-only static deployment does not run this Next server. |
| CVE-2024-46982<br>[GHSA-gp8f-8m3g-qvj9](https://github.com/vercel/next.js/security/advisories/GHSA-gp8f-8m3g-qvj9) | 13.5.7; 14.2.10 | A non-dynamic Pages Router SSR response can be incorrectly marked cacheable. | Not a 13.4.7 upgrade benefit: the impact description starts at 13.5.1. Pages Router alone is insufficient; no page-level getServerSideProps implementation was found. |
| CVE-2024-47831<br>[GHSA-g77x-44xx-532m](https://github.com/vercel/next.js/security/advisories/GHSA-g77x-44xx-532m) | 14.2.7 | Image optimization can consume excessive CPU and deny service. | Not affected: built-in Image Optimization is disabled with images.unoptimized: true in both versions; the advisory explicitly excludes this setting. |
| CVE-2024-51479<br>[GHSA-7gfc-8cq8-jh5f](https://github.com/vercel/next.js/security/advisories/GHSA-7gfc-8cq8-jh5f) | 14.2.15 | Path-based authorization in Middleware can be bypassed. | Not affected: this project does not implement Next Middleware authorization; a next-auth dependency declaration does not establish that usage. |
| CVE-2024-56332<br>[GHSA-7m27-7ghc-44w9](https://github.com/vercel/next.js/security/advisories/GHSA-7m27-7ghc-44w9) | 13.5.8; 14.2.21; 15.1.2 | Server Action requests can remain open and consume connection capacity. | Not affected: this project does not use Server Actions. |
| CVE-2025-29927<br>[GHSA-f82v-jwr5-mffw](https://github.com/vercel/next.js/security/advisories/GHSA-f82v-jwr5-mffw) | 13.5.9; 14.2.25; 15.2.3 (also 12.3.5) | A crafted internal header can bypass authorization performed in Middleware. | Not affected: no middleware, proxy authorization entry or next-auth/middleware usage exists in either inspected version. |
| CVE-2025-30218<br>[GHSA-223j-4rm8-mrmf](https://github.com/vercel/next.js/security/advisories/GHSA-223j-4rm8-mrmf) | 13.5.10; 14.2.26; 15.2.4 (also 12.3.6) | Middleware subrequest identifiers can leak to external hosts. | Not affected: this project does not use Next Middleware subrequests. |
| CVE-2025-32421<br>[GHSA-qpjv-v59x-3qc4](https://github.com/vercel/next.js/security/advisories/GHSA-qpjv-v59x-3qc4) | 14.2.24; 15.1.6 | A race between page/data requests can poison a CDN cache with the wrong response body. | Unconfirmed, not counted: Pages Router is present, but the required CDN/cache misconfiguration is not established. Official sources disagree on the affected version wording; see the source notes. |
| CVE-2025-48068<br>[GHSA-3h52-269p-cp9r](https://github.com/vercel/next.js/security/advisories/GHSA-3h52-269p-cp9r) | 14.2.30; 15.2.2 | Missing development-server origin checks can expose source information to a malicious site. | Not counted: the GHSA scopes source exposure to App Router, which this project does not route through. Vercel also describes development-script inclusion; that separate exposure was not verified. The candidate explicitly configures allowedDevOrigins. |
| CVE-2025-49826<br>[GHSA-67rr-84xm-4c7r](https://github.com/vercel/next.js/security/advisories/GHSA-67rr-84xm-4c7r) | 15.2.0 is the GHSA safe stable boundary; see source note on 15.1.8 | A cached HTTP 204 response can deny access to a page under particular ISR/CDN conditions. | Not a 13.4.7 upgrade benefit: the affected versions are on the 15.x line. The required ISR/CDN conditions were not established either. |
| CVE-2025-49005<br>[GHSA-r2fc-ccr8-96c4](https://github.com/vercel/next.js/security/advisories/GHSA-r2fc-ccr8-96c4) | 15.3.3 | Missing Vary behavior can let a cache serve RSC payloads in place of HTML. | Not affected: this project does not use App Router/RSC responses; 13.4.7 is also outside the stated 15.3.x range. |
| CVE-2025-57822<br>[GHSA-4342-x723-ch2f](https://github.com/vercel/next.js/security/advisories/GHSA-4342-x723-ch2f) | 14.2.32; 15.4.7 | Reflecting request headers through Middleware can cause server-side request forgery. | Not affected: this project does not implement Middleware or pass incoming headers to NextResponse.next(). Its fixed rewrites rule is a different feature. |
| CVE-2025-55173<br>[GHSA-xv57-4mr9-wg8v](https://github.com/vercel/next.js/security/advisories/GHSA-xv57-4mr9-wg8v) | 14.2.31; 15.4.5 | External image sources can trigger downloads with attacker-controlled content or names. | Not affected: built-in Image Optimization is disabled and neither images.domains nor remotePatterns is configured. |
| CVE-2025-57752<br>[GHSA-g5qg-72qw-gw5v](https://github.com/vercel/next.js/security/advisories/GHSA-g5qg-72qw-gw5v) | 14.2.31; 15.4.5 | An image cache key can confuse responses that vary by authentication headers. | Not affected: built-in Image Optimization is disabled; no authenticated image API route is present in the inspected source. |
| CVE-2025-55182<br>[GHSA-9qr9-h5gf-34mp](https://github.com/vercel/next.js/security/advisories/GHSA-9qr9-h5gf-34mp)<br>[CVE-2025-66478 tracking post](https://nextjs.org/blog/CVE-2025-66478) | 16.0.7; 15.0.5 / 15.1.9 / 15.2.6 / 15.3.6 / 15.4.8 / 15.5.7 | Unsafe RSC deserialization can permit remote code execution. | Not affected: this project does not use App Router/RSC. Official guidance also explicitly excludes Next 13.x and Pages Router. CVE-2025-66478 is the downstream Next.js tracking ID, not a second counted benefit. |
| CVE-2025-55184<br>[GHSA-mwv6-3258-q52c](https://github.com/vercel/next.js/security/advisories/GHSA-mwv6-3258-q52c) | 14.2.34; 16.0.9 (15.x fixes in advisory) | RSC deserialization can hang the server and consume CPU. | Not affected: this project does not use App Router/RSC. Later incomplete-fix advisories remain separate rows below. |
| CVE-2025-55183<br>[GHSA-w37m-7fhw-fmv9](https://github.com/vercel/next.js/security/advisories/GHSA-w37m-7fhw-fmv9) | 16.0.9 (15.x fixes in advisory) | App Router requests can expose compiled Server Function source. | Not affected: this project does not use App Router or Server Functions. |
| CVE-2025-67779<br>[GHSA-5j59-xgg2-r9c4](https://github.com/vercel/next.js/security/advisories/GHSA-5j59-xgg2-r9c4) | 14.2.35; 16.0.10 (15.x fixes in advisory) | An incomplete RSC DoS fix leaves additional payloads able to trigger an infinite loop. | Not affected: this project does not use App Router/RSC. |
| CVE-2025-59471<br>[GHSA-9g9p-9gw9-jx7f](https://github.com/vercel/next.js/security/advisories/GHSA-9g9p-9gw9-jx7f) | 15.5.10; 16.1.5 | Oversized remote images can exhaust Image Optimizer memory. | Not affected: built-in Image Optimization is disabled and remotePatterns is not configured. |
| CVE-2025-59472<br>[GHSA-5f7q-jpqc-wp7h](https://github.com/vercel/next.js/security/advisories/GHSA-5f7q-jpqc-wp7h) | 16.1.5; 15.x/canary branch details in advisory | PPR resume buffering or decompression can exhaust memory in minimal mode. | Not affected: this project does not use App Router PPR or Cache Components. |
| CVE-2026-23864<br>[GHSA-h25m-26qc-wcjf](https://github.com/vercel/next.js/security/advisories/GHSA-h25m-26qc-wcjf) | 16.0.11; 16.1.5 (15.x fixes in advisory) | RSC payloads can cause excessive CPU use, memory exhaustion or a server crash. | Not affected: this project does not use App Router/RSC. |
| CVE-2026-29057<br>[GHSA-ggv3-7p47-pfv8](https://github.com/vercel/next.js/security/advisories/GHSA-ggv3-7p47-pfv8) | 15.5.13; 16.1.7 | Chunked requests through external rewrites can desynchronize proxy/backend request boundaries. | Applies to the self-hosted Next proxy shape: the fixed loopback backend is external to Next's router and 13.4.7 is affected. A constant hostname does not remove request-boundary ambiguity. Static-only serving and CDN-handled rewrites are different deployment paths; no exploit was attempted. |
| CVE-2026-27979<br>[GHSA-h27x-g6w4-24gq](https://github.com/vercel/next.js/security/advisories/GHSA-h27x-g6w4-24gq) | 16.1.7 | PPR resume bodies can be buffered without a size bound outside minimal mode. | Not affected: this project does not use App Router PPR or Cache Components; 13.4.7 also predates the affected 16.1.x path. |
| CVE-2026-27977<br>[GHSA-jcc7-9wpm-mj36](https://github.com/vercel/next.js/security/advisories/GHSA-jcc7-9wpm-mj36) | 16.1.7 | An opaque Origin can bypass internal dev-endpoint origin protections. | Not a 13.4.7 upgrade benefit: the affected range starts at 16.0.1. The candidate uses allowedDevOrigins and already includes this fix. |
| CVE-2026-27978<br>[GHSA-mq59-m269-xvcx](https://github.com/vercel/next.js/security/advisories/GHSA-mq59-m269-xvcx) | 16.1.7 | Opaque-origin requests can bypass Server Action CSRF checks. | Not affected: this project does not use Server Actions; 13.4.7 also predates the stated affected range. |
| CVE-2026-27980<br>[GHSA-3x4c-7xq6-9pq8](https://github.com/vercel/next.js/security/advisories/GHSA-3x4c-7xq6-9pq8) | 15.5.14; 16.1.7 | Unbounded image-variant cache growth can exhaust disk storage. | Not affected: this project disables the built-in Image Optimization endpoint; existing build-directory disk usage is not evidence of this vulnerability. |
| CVE-2026-23869<br>[GHSA-q4gf-8mx6-v5v3](https://github.com/vercel/next.js/security/advisories/GHSA-q4gf-8mx6-v5v3) | 15.5.15; 16.2.3 | RSC Server Function payloads can cause excessive CPU consumption. | Not affected: this project does not use App Router/RSC. |
| CVE-2026-23870<br>[GHSA-8h8q-6873-q5fj](https://github.com/vercel/next.js/security/advisories/GHSA-8h8q-6873-q5fj) | 15.5.16; 16.2.5 | Additional RSC payloads can deny service through excessive CPU consumption. | Not affected: this project does not use App Router/RSC. |
| CVE-2026-44572<br>[GHSA-3g8h-86w9-wvmq](https://github.com/vercel/next.js/security/advisories/GHSA-3g8h-86w9-wvmq) | 15.5.16; 16.2.5 | Internal data headers can turn Middleware redirects into unusable cached redirects. | Not affected: this project does not use Middleware/proxy redirects. Its Next config rewrites are not authorization/redirect Middleware. |
| CVE-2026-44573<br>[GHSA-36qx-fr4f-26g5](https://github.com/vercel/next.js/security/advisories/GHSA-36qx-fr4f-26g5) | 15.5.16; 16.2.5 | Locale-less Pages data routes can bypass Middleware authorization. | Not affected: there is no Next Middleware authorization or Next config i18n. Client-side i18next translations do not enable Next's i18n routing. |
| CVE-2026-44574<br>[GHSA-492v-c6pp-mqqv](https://github.com/vercel/next.js/security/advisories/GHSA-492v-c6pp-mqqv) | 15.5.16; 16.2.5 | Dynamic route parameter injection can bypass Middleware checks. | Not affected: this project does not use Middleware authorization; 13.4.7 is also below the affected 15.4.x start. |
| CVE-2026-44575<br>[GHSA-267c-6grr-h53f](https://github.com/vercel/next.js/security/advisories/GHSA-267c-6grr-h53f) | 15.5.16; 16.2.5 | App Router transport variants can evade Middleware matching. | Not affected: this project does not use App Router or Middleware authorization. |
| CVE-2026-44576<br>[GHSA-wfc6-r584-vfw7](https://github.com/vercel/next.js/security/advisories/GHSA-wfc6-r584-vfw7) | 15.5.16; 16.2.5 | RSC header interpretation can poison shared response caches. | Not affected: this project does not use App Router/RSC responses. |
| CVE-2026-44578<br>[GHSA-c4j6-fc7j-m34r](https://github.com/vercel/next.js/security/advisories/GHSA-c4j6-fc7j-m34r) | 15.5.16; 16.2.5 | Crafted WebSocket upgrades can make a self-hosted Next server proxy arbitrary destinations. | Not a 13.4.7 upgrade benefit: the affected range begins at 13.4.13. The self-hosted server shape is relevant, but the old pinned version is outside the range and 16.3.0 includes the fix. |
| CVE-2026-44577<br>[GHSA-h64f-5h5j-jqjh](https://github.com/vercel/next.js/security/advisories/GHSA-h64f-5h5j-jqjh) | 15.5.16; 16.2.5 | Large local images can exhaust Image Optimizer memory. | Not affected: images.unoptimized is true; the advisory explicitly excludes this configuration. |
| CVE-2026-44579<br>[GHSA-mg66-mrh9-m8jx](https://github.com/vercel/next.js/security/advisories/GHSA-mg66-mrh9-m8jx) | 15.5.16; 16.2.5 | Cache Components/Server Action requests can deadlock and exhaust connections. | Not affected: this project does not use Cache Components, PPR or Server Actions. |
| CVE-2026-44580<br>[GHSA-gx5p-jg67-6x7h](https://github.com/vercel/next.js/security/advisories/GHSA-gx5p-jg67-6x7h) | 15.5.16; 16.2.5 | Untrusted content in beforeInteractive scripts can escape serialization and execute script. | Not affected: this project does not use next/script beforeInteractive or supply untrusted data to that feature. |
| CVE-2026-44582<br>[GHSA-vfv6-92ff-j949](https://github.com/vercel/next.js/security/advisories/GHSA-vfv6-92ff-j949) | 15.5.16; 16.2.5 | RSC cache-busting collisions can poison shared response variants. | Not affected: this project does not use App Router/RSC responses. |
| CVE-2026-44581<br>[GHSA-ffhc-5mcf-pf4q](https://github.com/vercel/next.js/security/advisories/GHSA-ffhc-5mcf-pf4q) | 15.5.16; 16.2.5 | Malformed CSP nonces in App Router responses can enable cached cross-site scripting. | Not affected: this project does not use App Router nonce-based rendering. |
| CVE-2026-45109<br>[GHSA-26hh-7cqf-hhc6](https://github.com/vercel/next.js/security/advisories/GHSA-26hh-7cqf-hhc6) | 15.5.18; 16.2.6 | The segment-prefetch authorization fix was incomplete for Turbopack Middleware. | Not affected: this project uses Pages Router and Webpack, with no Middleware authorization. |
| CVE-2026-64641<br>[GHSA-m99w-x7hq-7vfj](https://github.com/vercel/next.js/security/advisories/GHSA-m99w-x7hq-7vfj) | 15.5.21; 16.2.11 | Server Action requests can exhaust CPU in App Router applications. | Not affected: this project does not use App Router/Server Actions; the advisory explicitly excludes Pages Router. |
| CVE-2026-64642<br>[GHSA-6gpp-xcg3-4w24](https://github.com/vercel/next.js/security/advisories/GHSA-6gpp-xcg3-4w24) | 16.2.11 | A single-locale App Router/Turbopack setup can bypass Middleware authorization. | Not affected: this project uses Pages Router/Webpack and has no Next i18n or authorization Middleware. |
| CVE-2026-64643<br>[GHSA-955p-x3mx-jcvp](https://github.com/vercel/next.js/security/advisories/GHSA-955p-x3mx-jcvp) | 15.5.21; 16.2.11 | Public client artifacts can reveal internal Server Function endpoint identifiers. | Not affected: this project does not use App Router Server Actions or use-cache endpoints. |
| CVE-2026-64645<br>[GHSA-p9j2-gv94-2wf4](https://github.com/vercel/next.js/security/advisories/GHSA-p9j2-gv94-2wf4) | 15.5.21; 16.2.11 | Request-controlled hostname segments in rewrites/redirects can cause SSRF or open redirects. | Not affected by this specific advisory: both versions use the literal hostname 127.0.0.1:5670. Only the path is dynamic; the project does not use request-controlled destination hostnames. |
| CVE-2026-64644<br>[GHSA-q8wf-6r8g-63ch](https://github.com/vercel/next.js/security/advisories/GHSA-q8wf-6r8g-63ch) | 15.5.21; 16.2.11 | Malicious remote image/SVG metadata can exhaust Image Optimizer CPU. | Not affected: built-in Image Optimization is disabled and remotePatterns is absent; the advisory explicitly excludes unoptimized images. |
| CVE-2026-64646<br>[GHSA-4c39-4ccg-62r3](https://github.com/vercel/next.js/security/advisories/GHSA-4c39-4ccg-62r3) | 15.5.21; 16.2.11 | Edge-runtime Server Action payloads can consume unbounded memory. | Not affected: this project does not use App Router Server Actions or Edge Server Actions. |
| CVE-2026-64648<br>[GHSA-68g3-v927-f742](https://github.com/vercel/next.js/security/advisories/GHSA-68g3-v927-f742) | 15.5.21; 16.2.11 | Mismatched server fetch request/init bodies can return another request's cached response. | Not affected: this project uses Pages Router, which the advisory explicitly excludes; browser Axios requests are not this server fetch cache. |
| CVE-2026-64647<br>[GHSA-4633-3j49-mh5q](https://github.com/vercel/next.js/security/advisories/GHSA-4633-3j49-mh5q) | 15.5.21; 16.2.11 | Non-UTF-8 server fetch bodies can collide in the response cache and disclose data. | Not affected: this project uses Pages Router, which the advisory explicitly excludes. |
| CVE-2026-64649<br>[GHSA-89xv-2m56-2m9x](https://github.com/vercel/next.js/security/advisories/GHSA-89xv-2m56-2m9x) | 15.5.21; 16.2.11 | Host-controlled Server Action forwarding on custom servers can cause SSRF. | Not affected: this project does not use Server Actions or their forwarding/redirect path. |

### Source qualifications

- **CVE-2023-46298:** this older record appears in the advisory database rather
  than the repository's current advisory listing. The row is grounded in
  [upstream PR #54732](https://github.com/vercel/next.js/pull/54732), commit
  `20d05958ff853e9c9e42139ffec294336881c648`, and its first patched canary release.
  Listing that first fix is not a recommendation to install a canary build.
- **CVE-2025-32421:** the GHSA and [Vercel's write-up](https://vercel.com/changelog/cve-2025-32421)
  disagree on affected-range wording. Both identify fixes at 14.2.24 / 15.1.6.
  The CDN configuration required for exploitation is not established here;
  the item is not counted as an applicable baseline fix.
- **CVE-2025-49826:** the GHSA's version fields use a safe boundary of 15.2.0,
  while its description and [Vercel's write-up](https://vercel.com/changelog/cve-2025-49826)
  describe an affected interval ending before 15.1.8. This discrepancy does not
  change the conclusion that baseline 13.4.7 is outside the affected 15.x line.
- **CVE-2025-48068:** the GHSA identifies App Router source exposure;
  [Vercel's account](https://vercel.com/changelog/cve-2025-48068) also discusses
  development-script inclusion. No App Router routes exist here, and no separate
  dev-script exposure verification was performed. This row is not promoted to
  a confirmed benefit or a blanket claim that every dev-origin issue is absent.
- **CVE-2025-55182 / CVE-2025-66478:** the [Next.js security post](https://nextjs.org/blog/CVE-2025-66478)
  explains the upstream/downstream tracking relationship and explicitly excludes
  Pages Router. They are presented together in one GHSA row, not counted twice.
- Earlier fixes for RSC DoS have follow-up advisories because some fixes were
  incomplete. Their separate rows record the patch history; none is counted as
  an application benefit for this Pages Router project.

## Later fixes that 16.3.0 does not contain

These entries fall **outside** the requested fixed-by-16.3.0 interval. They are
included to avoid suggesting that the candidate is currently free of known
security issues.

| Advisory / source | Fix version(s) | Impact | DB-GPT applicability |
| --- | --- | --- | --- |
| CVE-2026-75604<br>[GHSA-p293-qw3h-jr36](https://github.com/vercel/next.js/security/advisories/GHSA-p293-qw3h-jr36) | 15.5.24; 16.3.3 | Pages/App Router servers on Windows filesystems can allow unauthenticated remote code execution. | Outside the requested fixed-by-16.3.0 set, and unresolved in this candidate. The recorded Windows Next server deployment matches the stated conditions; both 13.4.7 and 16.3.0 are affected. Python-only static serving is a different path. No exploit was run. |
| No CVE assigned in official record<br>[GHSA-2xp9-vwfh-vxw4](https://github.com/vercel/next.js/security/advisories/GHSA-2xp9-vwfh-vxw4) | 15.5.24; 16.3.3 | AVIF processing through the Image Optimizer can trigger upstream remote code execution. | Outside the interval, not an upgrade benefit. Not affected in this project because built-in Image Optimization is disabled. |
| CVE-2026-94545<br>[GHSA-vcvr-r3jv-pc5j](https://github.com/vercel/next.js/security/advisories/GHSA-vcvr-r3jv-pc5j) | 16.3.6 | Attacker-controlled SVG input to Node next/og ImageResponse can trigger remote code execution. | Outside the interval, not an upgrade benefit. Not affected in this project because next/og ImageResponse is not used. |

The [August security release](https://nextjs.org/blog/august-2026-security-release)
confirms the 16.3.3 / 15.5.24 fixes. The Windows advisory's prerequisites do not
require App Router or Image Optimization, so those exclusions cannot be used to
dismiss it. The recorded Windows environment uses Pages Router without Cache
Components. Actual exploitability was not tested, but the affected deployment
shape and unpatched version are sufficient to disclose this as unresolved.
No package update was performed in this documentation-only review.

## September 30 release follow-up — checked 2026-10-01

The [official September release](https://nextjs.org/blog/september-2026-security-release)
names **16.3.8** (and 15.5.27 on its supported branch) as the update for that
release. Some individual GHSA version fields still contain `16.3.?`; the concrete
16.x fix below comes from the release post, not an invented replacement of those
fields. The post also says two previously announced fixes were postponed; this
review does not claim that 16.3.8 fixes every announced security issue.

**Patch chronology:** CVE-2026-75604 was first fixed in **16.3.3**, not newly fixed
by the September 30 batch. A direct move to **16.3.8** includes that earlier fix
and the September fixes; an intermediate upgrade to 16.3.3 is unnecessary.
No dependency change is authorized in this documentation follow-up. Any future
version change needs separate confirmation and validation on the new candidate.

| Advisory / official source | 16.x fix | Impact | DB-GPT applicability at 16.3.0 |
| --- | --- | --- | --- |
| CVE-2026-94483 / [GHSA-cjq9-62q9-8jv4](https://github.com/vercel/next.js/security/advisories/GHSA-cjq9-62q9-8jv4) | 16.3.8 | Allowed remote image URLs can induce requests to unintended hosts during optimization. | **Not affected: capability not used.** No `images.remotePatterns` configuration; resolved `remotePatterns: []`, `domains: []`, `unoptimized: true`. Not counted as an upgrade benefit. |
| CVE-2026-94543 / [GHSA-4jqv-mc3x-m676](https://github.com/vercel/next.js/security/advisories/GHSA-4jqv-mc3x-m676) | 16.3.8 | A self-hosted SSG/ISR page cache can serve content from another route. | **Matches self-hosted Next server configuration; unresolved.** Pages Router plus the two prompt SSG routes satisfy the stated prerequisites. Python-only static-file serving is outside this Next server path. No exploit was run. The GHSA lists affected 15.x/16.x lines, not baseline 13.4.7; do not present this as a vulnerability removed by 13.4.7 → 16.3.0. |
| CVE-2026-94484 / [GHSA-mcj8-r9mp-w47p](https://github.com/vercel/next.js/security/advisories/GHSA-mcj8-r9mp-w47p) | 16.3.8 | A root-level catch-all route combined with SSG/ISR can enable cache poisoning. | **Not affected: required route shape not used.** No root-level catch-all page exists in the tracked `web/pages` tree. The nested prompt `[type]` route is not a root catch-all. |
| CVE-2026-94485 / [GHSA-f87g-xv8r-7p7x](https://github.com/vercel/next.js/security/advisories/GHSA-f87g-xv8r-7p7x) | 16.3.8 | App Router metadata image routes built with Webpack can bypass excluded dynamic parameters. | **Not affected: capability not used.** No App Router metadata routes. Webpack alone is not an exclusion: this advisory specifically concerns Webpack plus App Router. |
| No CVE listed / [GHSA-h694-7cp9-m8p3](https://github.com/vercel/next.js/security/advisories/GHSA-h694-7cp9-m8p3) | 16.3.8 | Nested cached functions can reuse content across different root parameters. | **Not affected: capability not used.** Cache Components and `use cache` are not enabled. |
| CVE-2026-94544 / [GHSA-3w37-wq28-93x7](https://github.com/vercel/next.js/security/advisories/GHSA-3w37-wq28-93x7) | 16.3.8 | Shared pending cache fills can expose unpublished Draft Mode content. | **Not affected: capability not used.** No Cache Components / `experimental.useCache` with Draft Mode previews. |
| CVE-2026-94486 / [GHSA-39w2-rjm5-chcv](https://github.com/vercel/next.js/security/advisories/GHSA-39w2-rjm5-chcv) | 16.3.8 | A malicious site visited by a developer can read development metadata/logs through the dev server MCP endpoint. | **Matches MCP-enabled development configuration; unresolved.** The installed Webpack hot reloader includes this middleware and the default is enabled. Pages Router does not exclude it. The announcement limits this to `next dev`; production deployments do not serve the endpoint. No exploit was run. |

The source check reads `web/next.config.js` and searches tracked web code for
`remotePatterns` / `images.domains`; neither is configured. The already-built
`.next-pr3277-review-build/required-server-files.json` confirms the resolved image
settings above, and its `prerender-manifest.json` records both prompt pages as
static. These are reads of the accepted artifact, not a fresh build. The scoped
[October 1 evidence](evidence/pr-3277/closeout-documentation.json) retains selected
configuration, artifact hashes, the two route entries and official sources.

The September batch is therefore **not wholly inapplicable**: the SSG server
case and development MCP case have matching prerequisites. Conversely, unused
features remain explicitly excluded. Neither an exploit demonstration nor a
new-version regression result is claimed, and the original 16.3.0 benefit count
is not increased by these still-unresolved issues.

## What the upgrade justification can say

For a deployment running DB-GPT through a Next Node server, staying on 13.4.7
retains a known server DoS issue and known rewrite-proxy request-smuggling
issues that the candidate release contains fixes for. The exact scope is the
three matching rows above; unused App Router, Server Action, Middleware and
Image Optimization capabilities must not be added to that claim. For a
Python-only static deployment, use the maintenance/build rationale instead of
claiming those Next server paths are exposed.

[Next's support policy](https://nextjs.org/support-policy) lists 13.x as
unsupported, 16.x as Active LTS and 15.x as Maintenance LTS at collection time.
That supports moving to a supported, patched release, **not a claim that 16.3.0
is the only security solution or is already fully patched**. The earlier
request-smuggling/DoS fixes also exist in earlier releases.

The [16.3 release notes](https://nextjs.org/blog/next-16-3) describe Turbopack and
App Router improvements. This PR continues to use Pages Router and Webpack;
those advertised gains and Instant Navigations are not claimed as measured
DB-GPT benefits. Its build reliability claims remain bounded by the existing
[regression evidence](pr-3277-regression.md), rather than a new performance test.
