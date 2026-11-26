# AGENTS.md

This file guides agentic coding assistants working in this repository.
Keep changes scoped, follow repo conventions, and prefer existing patterns.

## Repository Overview
- DB-GPT is a Python monorepo with multiple packages under `packages/`.
- Core modules live in `packages/dbgpt-core/src/dbgpt/`.
- Web UI is a Next.js app under `web/`.

## Setup
Install uv:
```
pipx install uv
# or: curl -LsSf https://astral.sh/uv/install.sh | sh
```

Sync packages and extras:
```
uv sync --all-packages \
  --extra "base" \
  --extra "proxy_openai" \
  --extra "rag" \
  --extra "storage_chromadb" \
  --extra "dbgpts"
```

Run commands without activating venv:
```
uv run <command>
```

Activate the venv if needed:
```
source .venv/bin/activate  # macOS/Linux
# or: .venv\Scripts\activate  # Windows
```

## Build / Lint / Test
Format and lint:
```
make fmt          # ruff + import fixes
make fmt-check    # formatting check only
make mypy         # type checking (dbgpt-core)
```

Tests:
```
make test         # pytest --pyargs dbgpt
make test-doc     # doctests
make coverage     # tests + coverage
```

Single test file:
```
pytest packages/dbgpt-core/src/dbgpt/util/tests/test_json_utils.py
```

Pre-commit:
```
make pre-commit   # fmt-check + test + test-doc + mypy
uv run pre-commit install
```

Build and publish:
```
make build
make publish
make clean
```

## Running the Server
```
python packages/dbgpt-app/src/dbgpt_app/dbgpt_server.py -c configs/dbgpt-proxy-siliconflow.toml
```

Config files live in `configs/` (e.g. `dbgpt-proxy-openai.toml`).

## Frontend (web/)
```
cd web
npm install
npm run dev
npm run build
npm run lint
npm run format
```

## Code Style (Python)
- Target: Python 3.10+.
- Line length: 88.
- Use double quotes for strings.
- Ruff enforces formatting and import order (isort rules).
- First-party modules: `dbgpt`, `dbgpt_client`, `dbgpt_ext`, `dbgpt_serve`,
  `dbgpt_app`, `dbgpt_sandbox`.

## Imports
- Keep imports sorted by Ruff/isort.
- Prefer explicit imports over wildcard.
- Group stdlib, third-party, first-party.

## Types and Interfaces
- Use type hints for public APIs and non-trivial functions.
- Prefer `Optional[T]` or `T | None` consistently with existing file style.
- Reuse existing dataclasses and pydantic models where available.

## Naming and Structure
- Follow existing module structure under `packages/`.
- Keep public APIs stable unless change is required.
- Use descriptive names; avoid abbreviations without context.

## Error Handling
- Raise meaningful exceptions with context.
- Log errors at the appropriate level (error/warn/info).
- Avoid swallowing exceptions unless there is a fallback path.

## Tests
- Tests live next to modules or in `tests/` subdirectories.
- Naming: `test_*.py` or `*_test.py`.
- Prefer pytest fixtures and parametrize for coverage.

## Web UI Conventions
- Use existing components in `web/components` and `web/new-components`.
- Keep UI styles consistent with current design tokens.
- Prefer inline Tailwind utility classes used in this repo.

## Architecture Notes
- Component system uses `SystemApp` lifecycle hooks.
- AWEL orchestrates workflows as DAGs.
- Agent framework uses `ConversableAgent`, actions, and memory.
- Model management via SMMF supports multiple providers.

## Repository Rules
- No Cursor rules found in `.cursor/rules/` or `.cursorrules`.
- No Copilot rules found in `.github/copilot-instructions.md`.

## Practical Guidance for Agents
- Keep changes minimal and scoped.
- Align with existing patterns and utilities.
- Update docs or tests when behavior changes.
- Avoid reformatting unrelated code.

## Quick Reference
- Core agent code: `packages/dbgpt-core/src/dbgpt/agent/`.
- Server entry: `packages/dbgpt-app/src/dbgpt_app/dbgpt_server.py`.
- Frontend: `web/`.
