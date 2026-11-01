# F12 / F16 / F18 / F19 regression tests

Python tool regressions live beside the tools in
`packages/dbgpt-app/src/dbgpt_app/openapi/api_v1/tools/tests/`.
Live backend tests use the repository's existing `tests/intetration_tests/`
directory (the spelling is retained for consistency). Browser cases and their
fixtures live under `web/tests/report-e2e/` and use the Playwright test runner.

These tests use real file I/O and subprocesses, on-disk SQLite, the production
tool/assembler/DAO/download implementations, a live OceanBase server, a local
Spark JVM, and Chrome with the full React report component and actual G2 renderer.
They do not substitute fake Spark sessions or OceanBase clients.

## Python

Use the project's configured Python environment with its normal dependencies,
plus `pytest`, `pytest-asyncio`, `httpx`, `pyobvector==0.2.10` and `pyspark==3.5.2`.
Spark also needs Java and `SPARK_HOME` / `JAVA_HOME` configured. On Windows,
`SPARK_LOCAL_IP=127.0.0.1` avoids hostname binding problems. `PYSPARK_PYTHON`
should name the same Python executable used for the tests. An existing Spark
Python installation can be provided through `DBGPT_SPARK_PYTHON_PATH`.

File security tests do not need an external service:

```powershell
python -m pytest packages/dbgpt-app/src/dbgpt_app/openapi/api_v1/tools/tests/test_input_file_security.py -q
```

Real CSV analysis tests also run without OceanBase/Spark:

```powershell
python -m pytest packages/dbgpt-app/src/dbgpt_app/openapi/api_v1/tools/tests/test_analysis_integration.py -q
```

They use the public analysis tool, actual pandas CSV reads and the real local
Python executor. They cover legacy uploads, all attachments, ordered subsets
excluding the primary attachment, capture on/off, valid conversation IDs and
unsafe IDs rejected before creating the runner's working directory.

For the live database tests, use a disposable OceanBase tenant/database with
HNSW vector support. Verified server image: `oceanbase/oceanbase-ce:4.3.5-lts`.
For example:

```powershell
docker run -d --name dbgpt-report-regression-ob -p 127.0.0.1:12881:2881 -e MODE=mini oceanbase/oceanbase-ce:4.3.5-lts
```

After the tenant is ready, execute SQL as its administrator:

```sql
ALTER SYSTEM SET ob_vector_memory_limit_percentage=30;
CREATE DATABASE dbgpt_f16_regression;
```

Run the live backend regressions explicitly:

```powershell
$env:DBGPT_RUN_LIVE_REGRESSIONS='1'
$env:DBGPT_OB_HOST='127.0.0.1'
$env:DBGPT_OB_PORT='12881'
$env:DBGPT_OB_USER='root@test'
$env:DBGPT_OB_PASSWORD=''
$env:DBGPT_OB_DATABASE='dbgpt_f16_regression'
python -m pytest tests/intetration_tests/vector_store/test_oceanbase_identity_integration.py tests/intetration_tests/datasource/test_spark_chart_integration.py -q --junitxml=pytest.xml
```

Live tests are opt-in so routine test discovery does not require running
OceanBase/Spark. Once enabled, missing dependencies or unavailable services fail
the run; they are not replaced with mocks or silently skipped. Tests create
unique vector tables and drop only their own tables. They never modify production
knowledge records. SQLite is isolated under pytest's temporary directory.

The embedding vectors in the OceanBase test are small, deterministic numerical
inputs: the tested contract is source identity after real vector writes/searches,
not embedding model accuracy. Public search intentionally deduplicates equal
bodies; the test checks all three backend UUIDs before that step and every
reference retained by the public search afterward.

## Browser

Install the web workspace dependencies and Chrome, then from the `web` directory:

```powershell
npm run test:e2e:report
```

This bundles the working-tree `HtmlReportEvidence`, `ReportIframe`, `AutoChart`
and export implementations, then runs them in installed Chrome through Playwright.
An actual local HTTP fixture delays the report metadata response to trigger the
race. The HTTP response is controlled test data; this is a component integration
test, not a claim that the entire Next.js application/backend was deployed.

Assertions cover opaque-to-trusted, empty-to-untrusted and missing-trust metadata,
actual parent DOM access, child script execution, G2's real render observation,
native chart canvas, exported PNG snapshots, and standalone PDF generation.
The three transitions are separate Playwright test cases. Results, screenshots,
HTML exports and PDFs are saved under `web/node_modules/.cache/report-e2e/results/`.
Playwright also retains a trace when a case fails. Override the output directory
with `npm run test:e2e:report -- --output <artifact-directory>`.

For the same browser assertions against the audited iframe implementation:

```powershell
$env:DBGPT_BROWSER_BASELINE='1'
npm run test:e2e:report -- --grep opaque-to-trusted
npm run test:e2e:report -- --grep empty-to-untrusted
Remove-Item Env:DBGPT_BROWSER_BASELINE
```

Python tests import the installed project packages using the same environment as
the surrounding module tests. No audit-specific source-path override is needed.
