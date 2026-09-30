# Frontend tooling migration

This candidate updates Next.js 13.4.7 to 16.3.0, TypeScript to 5.9.3, ESLint
to 9.39.5 and the web dependency workflow to npm 10 / Node >=20.19. It does
not contain the new Dashboard module. The existing UI, model choices and
backend default address are retained. Small changes to existing components
make their actual props, response shapes and DOM APIs type-safe.

## Compatibility changes

- Native `transpilePackages` replaces `next-transpile-modules`. AntV and code
  highlighting use their ESM entry points. Production still uses Webpack so
  Monaco's worker plugins retain their existing behavior.
- The Pages Router session wrappers use iron-session 8's `getIronSession`;
  handlers receive a session before they execute.
- Production and standalone type checking both check application sources.
  Temporary configs exclude other build directories' generated declarations;
  the checked-in TypeScript config is not rewritten to skip errors.
- `npm run compile` replaces removed `next export` with `output: 'export'`.
  Server builds retain the API rewrite. Static builds have no server rewrite.
- ESLint uses flat config. The existing Rules of Hooks and exhaustive-deps
  checks remain. React Compiler is not enabled; its additional lint family is
  deferred rather than expanding this migration into a rewrite of all pages.
  Formatting uses Prettier independently of ESLint.
- The docs website has its own dependency graph and retains its package manager.
- The Next CLI wrapper forwards shutdown signals and preserves the child's exit
  status. Task views unsubscribe from the shared event emitter when unmounted.
  Download errors are recognized even when a proxy omits the JSON media type;
  successful XLSX responses are not decoded in full. Clipboard feedback uses the
  existing translation key.

## Validation commands

```sh
npm ci
npm run typecheck
npm run lint
npm run test:build
npm test
npm run build
npm run compile
```

The workflow keeps the upstream Ubuntu/macOS matrix and existing action major
versions. Manual dispatch and `codex/**` branch pushes can run it in a fork;
enabling those triggers does not mean an Actions run has occurred.

Local validation records, including remaining lint warnings and browser or
platform gaps, are supplied with the review snapshot. Results for the separate
Dashboard integration candidate must not be used as results for this candidate.

The original source comparison for `b6f0c2ae` against `d1d398eb7ab2b2b3c9dc53fa376594a3600a7458`
uses the same ESLint 9.39.5 configuration and dependency installation on both
revisions. That comparison reported 0 errors and 87 warnings; all 87
also reproduced on the baseline source, with 0 added and 0 removed warnings.
Matching includes the file, rule, complete diagnostic and source line text,
allowing for formatting-only line movement. Warnings in the 16 changed files
also match the baseline. This does not claim the old ESLint configuration
reported the same diagnostics.

Those 87 warnings comprised 64 exhaustive-deps, 11 no-img-element, 10 unused
disable directives, one alt-text and one no-anonymous-default-export warning.
The subsequent Monaco dependency fix in `80d7c703` removes one exhaustive-deps
warning. The final recorded application run has **0 errors and 86 warnings**:
63 exhaustive-deps, 11 no-img-element, 10 unused disable directives, one alt-text
and one no-anonymous-default-export. See the
[regression report](../docs/frontend-toolchain/pr-3277-regression.md) for current
results, coverage limits and pending review findings.
The unused directives exposed by the new tooling remain a maintenance item;
they are not counted as newly introduced application-code warnings.
CI explicitly selects the Node 20.19 line and npm 10.8.2; local results must
still identify their actual runtime and must not be labelled Actions results.

The final build-contract command discovers 24 tests, including process shutdown,
download error handling and subscription cleanup. Two POSIX signal-delivery
tests intentionally skip on Windows and execute on the Ubuntu/macOS matrix.
