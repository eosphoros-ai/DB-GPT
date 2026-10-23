# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

DB-GPT is an AI-native data app development framework with AWEL (Agentic Workflow Expression Language) and agents. It is organized as a Python monorepo using `uv` as the package manager.

## Package Structure

The monorepo is organized under `packages/`:

- **dbgpt-core**: Core framework (agent system, RAG, storage, models, datasource). Most agent-related code lives here under `src/dbgpt/agent/`.
- **dbgpt-app**: Web server entry point (`dbgpt_server.py`) and HTTP API routes. Use `-c <config_file>` to specify configuration.
- **dbgpt-serve**: Service layer implementations (agents, conversations, datasources, prompts).
- **dbgpt-client**: Client SDK for interacting with the API.
- **dbgpt-ext**: Extensions including additional data source connectors and RAG knowledge parsers.
- **dbgpt-sandbox**: Sandbox execution environment.
- **dbgpt-accelerator**: Optional accelerator packages (flash-attention).

## Development Environment Setup

Install `uv` (package manager):
```bash
pipx install uv
# or: curl -LsSf https://astral.sh/uv/install.sh | sh
```

Sync all packages and install dependencies:
```bash
uv sync --all-packages \
  --extra "base" \
  --extra "proxy_openai" \
  --extra "rag" \
  --extra "storage_chromadb" \
  --extra "dbgpts"
```

Activate the virtual environment:
```bash
source .venv/bin/activate  # macOS/Linux
# or: .venv\Scripts\activate  # Windows
```

Use `uv run <command>` to execute commands in the virtual environment without activating it.

## Build and Development Commands

Code formatting and linting:
```bash
make fmt          # Format code with ruff and fix imports
make fmt-check    # Check formatting without making changes
make mypy         # Run type checking on dbgpt-core
```

Testing:
```bash
make test         # Run unit tests (pytest --pyargs dbgpt)
make test-doc     # Run doctests
make coverage     # Run tests with coverage report
```

To run a single test file:
```bash
pytest packages/dbgpt-core/src/dbgpt/util/tests/test_json_utils.py
```

Pre-commit (runs all checks):
```bash
make pre-commit   # Runs fmt-check, test, test-doc, mypy
uv run pre-commit install  # Install git hooks
```

Building and publishing:
```bash
make build        # Build all packages for distribution
make publish      # Publish to PyPI
make clean        # Clean build artifacts
```

## Running the Server

```bash
python packages/dbgpt-app/src/dbgpt_app/dbgpt_server.py -c configs/dbgpt-proxy-siliconflow.toml
```

Configuration files are in `configs/`. Common options include `dbgpt-proxy-openai.toml`, `dbgpt-proxy-siliconflow.toml`.

## Frontend (Web UI)

The frontend is a Next.js application in the `web/` directory:

```bash
cd web
npm install
npm run dev       # Development server
npm run build     # Production build
npm run lint      # ESLint check
npm run format    # Prettier format
```

## Code Style

- Python 3.10+ target version
- Line length: 88 characters
- Use double quotes
- Import order enforced via ruff (isort rules)
- First-party modules: `dbgpt`, `dbgpt_client`, `dbgpt_ext`, `dbgpt_serve`, `dbgpt_app`, `dbgpt_sandbox`

## Testing Conventions

- Test files: `test_*.py` or `*_test.py`
- Located in `tests/` subdirectories or inline next to source files
- Uses pytest with asyncio support
- Run tests with `pytest --pyargs dbgpt` from repo root
- Python path includes `packages/` directory

## Architecture Notes

- **Component System**: Uses a `SystemApp` with lifecycle hooks (`on_init`, `after_init`, `before_start`).
- **AWEL**: Agentic Workflow Expression Language for orchestrating workflows as DAGs.
- **Agent Framework**: Multi-agent system with `ConversableAgent`, `UserProxyAgent`, action-based execution, and memory management.
- **Model Management**: SMMF (Service-oriented Multi-model Management Framework) supports multiple LLM providers via proxy or local deployment.
- **RAG**: Built-in RAG framework with vector stores, embedding models, and knowledge assemblers.
- **Storage**: Unified storage abstraction with support for ChromaDB, and various databases.
