# Offline financial reports

From the repository root, install the web dependencies and prepare the Python
workspace following `CONTRIBUTING.md`, including the companion backend from
PR #3310. Run:

```sh
npm --prefix web run test:e2e:financial -- --grep-invert "saved real"
```

The npm prerequisite builds the offline runtime and regenerates all synthetic
JSON/HTML fixtures before Playwright starts. It does not invoke a model or read
the application's database. To test the frontend before merging its backend,
set `FINANCIAL_FIXTURE_BACKEND_ROOT` to the prepared backend checkout. The normal
merged checkout needs no override.

For a deployable runtime without fixtures:

```sh
node standalone/financial-analysis/build.cjs web/node_modules/.cache/financial-comparison/runtime.html
```

Set `DBGPT_FINANCIAL_EXPORT_RUNTIME` to that runtime's path in the backend.
HTML export requests include the application's current `language` (`en` or `zh`);
the downloaded file uses it for controls, Ant Design and the HTML `lang` attribute.
Report facts, findings and the pinned revision remain unchanged. The JSON export
is language independent. Existing clients default to Chinese. Rebuild the runtime
after updating the frontend to enable English exports.
