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

The source comparison against `d1d398eb7ab2b2b3c9dc53fa376594a3600a7458`
uses the same ESLint 9.39.5 configuration and dependency installation on both
revisions. Lint reports 0 errors and 87 warnings in this candidate; all 87
also reproduce on the baseline source, with 0 added and 0 removed warnings.
Matching includes the file, rule, complete diagnostic and source line text,
allowing for formatting-only line movement. Warnings in the 16 changed files
also match the baseline. This does not claim the old ESLint configuration
reported the same diagnostics.

The 87 warnings comprise 64 exhaustive-deps, 11 no-img-element, 10 unused
disable directives, one alt-text and one no-anonymous-default-export warning.
The unused directives exposed by the new tooling remain a maintenance item;
they are not counted as newly introduced application-code warnings.
CI explicitly selects the Node 20.19 line and npm 10.8.2; local results must
still identify their actual runtime and must not be labelled Actions results.
