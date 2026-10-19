# F12 / F16 / F18 / F19 regression tests

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
python -m pytest tests/report_regressions/test_input_file_security.py -q
```

Real CSV analysis tests also run without OceanBase/Spark:

```powershell
python -m pytest tests/report_regressions/test_analysis_integration.py -q
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

Run all Python regressions explicitly:

```powershell
$env:DBGPT_RUN_LIVE_REGRESSIONS='1'
$env:DBGPT_OB_HOST='127.0.0.1'
$env:DBGPT_OB_PORT='12881'
$env:DBGPT_OB_USER='root@test'
$env:DBGPT_OB_PASSWORD=''
$env:DBGPT_OB_DATABASE='dbgpt_f16_regression'
python -m pytest tests/report_regressions -q --junitxml=pytest.xml
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

Install the web workspace dependencies and Chrome, then from the repository root:

```powershell
node tests/report_regressions/test_iframe_browser.cjs C:\temp\dbgpt-report-browser
```

This bundles the working-tree `HtmlReportEvidence`, `ReportIframe`, `AutoChart`
and export implementations, then runs them in installed Chrome through Playwright.
An actual local HTTP fixture delays the report metadata response to trigger the
race. The HTTP response is controlled test data; this is a component integration
test, not a claim that the entire Next.js application/backend was deployed.

Assertions cover opaque-to-trusted, empty-to-untrusted and missing-trust metadata,
actual parent DOM access, child script execution, G2's real render observation,
native chart canvas, exported PNG snapshots, and standalone PDF generation.
Results, screenshots, HTML exports and PDFs are saved in the requested directory.

For the same browser assertions against the audited iframe implementation:

```powershell
$env:DBGPT_BROWSER_BASELINE='1'
node tests/report_regressions/test_iframe_browser.cjs C:\temp\dbgpt-report-before
$env:DBGPT_BROWSER_CASE='untrusted'
node tests/report_regressions/test_iframe_browser.cjs C:\temp\dbgpt-report-before-reverse
Remove-Item Env:DBGPT_BROWSER_BASELINE, Env:DBGPT_BROWSER_CASE
```

`DBGPT_TEST_SOURCE_ROOT` optionally points the Python regressions at a separate
checkout for before/after comparisons without changing the working tree.
