# Repository Guidelines

## Project Structure & Module Organization

DB-GPT is a Python `uv` workspace with a Next.js web UI. Core Python packages live under `packages/`, including `dbgpt-core`, `dbgpt-ext`, `dbgpt-serve`, `dbgpt-client`, `dbgpt-app`, `dbgpt-sandbox`, and accelerators in `packages/dbgpt-accelerator/`. Tests are split between `tests/unit_tests/`, `tests/intetration_tests/`, and package-local tests such as `packages/dbgpt-ext/tests/`. The web client is in `web/`. Documentation is in `docs/`, examples in `examples/` and `docker/examples/`, configuration templates in `configs/`, schema assets in `assets/schema/`, and container tooling in `docker/`.

### Package dependency graph (top-to-bottom)

```
dbgpt-app  (top-level app, ships CLI entrypoint `dbgpt`)
├── dbgpt-serve
│   └── dbgpt-ext
│       └── dbgpt (dbgpt-core)
├── dbgpt-client
│   ├── dbgpt (dbgpt-core)
│   └── dbgpt-ext
├── dbgpt-sandbox
└── dbgpt-acc-auto (accelerator)
```

Each package's import name differs from its directory name:
- `packages/dbgpt-core/src/dbgpt/` → import as `dbgpt`
- `packages/dbgpt-ext/src/dbgpt_ext/` → import as `dbgpt_ext`
- `packages/dbgpt-serve/src/dbgpt_serve/` → import as `dbgpt_serve`
- `packages/dbgpt-client/src/dbgpt_client/` → import as `dbgpt_client`
- `packages/dbgpt-app/src/dbgpt_app/` → import as `dbgpt_app`
- `packages/dbgpt-sandbox/src/dbgpt_sandbox/` → import as `dbgpt_sandbox`

### Other key directories

- `pilot/` — workspace runtime data: Alembic migration templates (`pilot/meta_data/alembic/`), benchmark data, and example SQLite databases. These are bundled into `dbgpt-app` via `pyproject.toml` `force-include`.
- `skills/` — builtin skill packages (csv-data-analysis, financial-report-analyzer, etc.) bundled into `dbgpt-app` sdist.
- `configs/` — TOML config templates for various LLM providers and backends. Do not modify unless you are adding a new provider template.

## Build, Test, and Development Commands

### Initial setup

```bash
uv sync --all-packages --extra "base" --extra "proxy_openai" --extra "rag" --extra "storage_chromadb" --extra "dbgpts"
```

After `uv sync`, activate `source .venv/bin/activate` or prefix commands with `uv run`.

### Makefile commands

The Makefile creates its own tooling venv at `.venv.make/` (separate from the workspace `.venv/`). Run `make setup` first if the venv doesn't exist.

- `make fmt` — formats Python code with Ruff and sorts imports.
- `make fmt-check` — checks formatting and lint rules (CI gate).
- `make test` — runs unit tests with `pytest --pyargs dbgpt`. This imports `dbgpt` from the installed workspace, not from source directly.
- `make test-doc` — runs doctests under `packages/`.
- `make mypy` — type checks **only** `packages/dbgpt-core/`. Other packages are not yet covered.
- `make build` — builds all Python packages with `uv build --all-packages`.
- `make pre-commit` — runs `fmt-check`, `test`, `test-doc`, and `mypy` in sequence.
- `make coverage` — runs tests with `--cov=dbgpt`.

### Running a single test

```bash
# Run a specific test file
uv run pytest packages/dbgpt-core/src/dbgpt/util/tests/test_json_utils.py

# Run a specific test function
uv run pytest packages/dbgpt-core/src/dbgpt/util/tests/test_json_utils.py::test_some_function

# Run tests matching a keyword
uv run pytest --pyargs dbgpt -k "test_agent"
```

### Web UI (Next.js 13, uses **yarn** not npm)

```bash
cd web
yarn install
yarn dev          # dev server
yarn build        # production build
yarn lint         # ESLint
yarn format       # Prettier
```

The static web build output goes to `packages/dbgpt-app/src/dbgpt_app/static/web/` via `scripts/build_web_static.sh`.

## Coding Style & Naming Conventions

Python targets 3.10+ and uses Ruff with 88-character lines, spaces for indentation, double quotes, import sorting, and lint families `E`, `F`, and `I`. Follow existing module naming under `packages/*/src/`: snake_case for files, functions, and variables; PascalCase for classes. Pytest files should be named `test_*.py` or `*_test.py`. For web changes, use TypeScript/React conventions in `web/` and run ESLint/Prettier scripts.

### Ruff quirks

- `packages/dbgpt-serve/src/**` is excluded from the main `ruff check --fix` pass and is instead checked separately with `--ignore F811,F841` (unused import / variable warnings tolerated in that package).
- `examples/notebook/` is excluded from all formatting and linting.

## Testing Guidelines

Add focused tests near the changed behavior. Prefer `tests/unit_tests/` for fast isolated coverage and `tests/intetration_tests/` only when external services, databases, or storage backends are required. Keep optional service tests scoped so normal `make test` remains practical. Use `make coverage` for shared core behavior.

### Where tests live

Tests exist in two locations:
1. `tests/unit_tests/` and `tests/intetration_tests/` — legacy top-level test directories.
2. `packages/*/src/*/tests/` — package-local tests colocated with source code (the preferred pattern for new tests).

### pytest configuration

- `pyproject.toml` sets `pythonpath = ["packages"]` and `--import-mode=importlib`.
- Test files must match `test_*.py` or `*_test.py`.

## Commit & Pull Request Guidelines

Git history follows conventional-style messages such as `fix(rag): ...`, `feat: ...`, and `fix(agent): ...`; use the same pattern and reference issues when applicable, for example `fix(rag): handle empty markdown chunks (Fixes #1234)`. Before opening a PR, run `make fmt-check` and relevant tests. PRs should describe the problem, solution, validation commands, linked issues, and include screenshots or recordings for UI changes.

## Security & Configuration Tips

Do not commit secrets, local model keys, or generated private configs. Treat files under `configs/` as templates unless explicitly documented otherwise. Be careful with upload, filename, and skill execution paths; recent fixes emphasize validating user-supplied filenames and restricting personal skill script execution.

## Alembic Migrations

Database schema migrations live in `pilot/meta_data/alembic/`. The `alembic.ini` and `env.py` are bundled into `dbgpt-app` as workspace templates. When modifying models that affect the database schema, generate a new Alembic migration revision.
