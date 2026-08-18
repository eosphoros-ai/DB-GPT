# AGENTS.md — DB-GPT Codebase Guide


## AI 编码注意规则（重要规则）
1. 如果需要读取或者写入的内容比较多，建议分批读取或者分批写入，而不是一次性操作，很容易导致卡死！
2. 实现新功能或修复 Bug 时，优先询问用户是否需要切换到新分支来实现，而不是直接在当前分支上开发。
   - 禁止使用临时目录（如 `/var/folders/.../T/`、`/tmp/` 等系统临时路径）存放代码。
   - 禁止使用 `git worktree` 创建独立工作区来开发，除非用户明确要求。
   - 所有代码改动必须在用户确认的持久分支上进行，确保代码不会因临时目录被清理而丢失。
3. 在分Task编码的时候，建议所有的小任务实现完成之后统一Review，而不是每实现一个小Task都单独Review

## Global AI Rules
### Language
Always respond in Chinese (简体中文), including all explanations, analysis, 
suggestions, and conversational replies — regardless of the language used 
in the user's message.
Exception: Code, variable names, file paths, and technical identifiers 
remain in English.
### Git Commits
1. NEVER create git commits unless the user explicitly asks with clear intent,
such as "帮我提交", "commit this", "git commit", or similar direct instructions.
Completing a task does NOT imply permission to commit. After finishing work,
report what was changed and wait for the user to decide whether to commit.
Do NOT run: git commit, git push, or any command that modifies git history,
unless explicitly instructed.

2. commit的message必须使用英文！

## Project Overview

DB-GPT is an AI-native data app development framework. Python 3.10+ monorepo managed by **uv** with a Next.js frontend in `web/`.

### Repository Layout

```
packages/
  dbgpt-core/       # Core library (published as "dbgpt") — AWEL, agents, model, RAG, storage, datasource
  dbgpt-ext/        # Extensions — additional RAG knowledge types, datasource connectors
  dbgpt-serve/      # Serve layer — REST API services (prompt, flow, file, conversation, etc.)
  dbgpt-app/        # Application entry point
  dbgpt-client/     # Python client SDK
  dbgpt-sandbox/    # Code execution sandbox
  dbgpt-accelerator/  # GPU acceleration packages
web/               # Next.js + Ant Design frontend
tests/             # Top-level integration tests
examples/          # Usage examples and notebooks
```

Each package uses `src/` layout (e.g., `packages/dbgpt-core/src/dbgpt/`). The core package is imported as `dbgpt`.

### Frontend Module Organization (web/)

Two coexisting styles — pick by the nature of the code, not by taste:

- `web/new-components/<domain>/` — pure UI components grouped by domain (chat,
  charts, connector, ...). No private state machine or wire protocol lives here.
- `web/modules/<feature>/` — a self-contained feature module that owns its
  domain logic (e.g. `session-files/`: reducer, upload queue, API seam) plus
  the React surface (hooks, components) and co-located tests (`*.test.ts`,
  executed with `node:test`).

Rules for `web/modules/`:

- Every module exposes a barrel `index.ts` as its only public API. Consumers
  import from `@/modules/<feature>` — never from deep paths like
  `@/modules/<feature>/internal-file`.
- Files not re-exported from the barrel (e.g. `reducer.ts`, `upload-queue.ts`)
  are private implementation details and may be reorganized freely.
- Litmus test: when the feature is retired, exactly one directory gets
  deleted. If that is not true, the code belongs in `new-components/` or
  `utils/` instead.

## Build & Dev Commands

### Package Manager: uv (NOT pip)

```bash
# Install all packages + dev dependencies
uv sync --all-packages --extra "base" --extra "proxy_openai" --extra "rag" --extra "storage_chromadb" --extra "dbgpts"

# Activate virtualenv
source .venv/bin/activate
```

### Makefile Targets (preferred interface)

```bash
make fmt          # Format code (ruff format + ruff check --fix)
make fmt-check    # Check formatting without changes (CI uses this)
make test         # Run unit tests (pytest --pyargs dbgpt)
make test-doc     # Run doctests
make mypy         # Type checking (dbgpt-core only currently)
make coverage     # Tests with coverage report
make pre-commit   # fmt-check + test + test-doc + mypy
make build        # Package for distribution (uv build --all-packages)
make clean        # Remove virtualenv and caches
```

### Running Tests

```bash
# All unit tests
make test
# OR directly:
pytest --pyargs dbgpt

# Single test file
pytest packages/dbgpt-core/src/dbgpt/core/awel/dag/tests/test_dag.py

# Single test function
pytest packages/dbgpt-core/src/dbgpt/core/awel/dag/tests/test_dag.py::test_dag_context_sync

# Single test by keyword
pytest --pyargs dbgpt -k "test_save_and_load"

# Tests for a specific subpackage
pytest packages/dbgpt-core/src/dbgpt/storage/

# With coverage
pytest --pyargs dbgpt --cov=dbgpt
```

pytest config is in root `pyproject.toml`:
- `pythonpath = ["packages"]`
- `addopts = ["--import-mode=importlib"]`
- Test files: `test_*.py` or `*_test.py`
- Async tests use `@pytest.mark.asyncio` with `pytest_asyncio`

### Frontend (web/)

```bash
cd web
npm install          # or yarn install
npm run dev          # Dev server
npm run build        # Production build
npm run lint         # ESLint
npm run format       # Prettier
```

## Linting & Formatting

### Primary: Ruff (replaces black + isort + flake8)

Config in root `pyproject.toml`:
```toml
[tool.ruff]
line-length = 88
target-version = "py310"

[tool.ruff.lint]
select = ["E", "F", "I"]    # errors, pyflakes, isort

[tool.ruff.lint.isort]
known-first-party = ["dbgpt", "dbgpt_acc_auto", "dbgpt_client", "dbgpt_ext", "dbgpt_serve", "dbgpt_app", "dbgpt_sandbox"]
```

### Type Checking: mypy

Config in `.mypy.ini`. Currently only checks `packages/dbgpt-core/`. Many third-party libs have `ignore_missing_imports = True`.

### Pre-commit

```bash
uv run pre-commit install    # One-time setup
# Hooks run: fmt-check + test on commit
```

## Code Style Guidelines

### Imports

Order enforced by ruff isort: **stdlib → third-party → first-party (`dbgpt.*`) → relative**

```python
import asyncio                                    # stdlib
import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Type

import pytest                                     # third-party
from pydantic import BaseModel

from dbgpt.core.interface.storage import ...      # first-party (absolute)
from dbgpt.util.annotations import PublicAPI

from ..awel.flow import Parameter                  # relative (within same package)
```

Relative imports are used within the same sub-package. Cross-package imports use absolute `dbgpt.*` paths.

### Naming Conventions

- **Classes**: `PascalCase` — `StorageItem`, `ResourceIdentifier`, `BaseComponent`
- **Functions/methods**: `snake_case` — `get_current_dag()`, `split_text()`
- **Constants**: `UPPER_SNAKE_CASE` — `_CORE_LIBS`, `_LIBS`
- **Private**: leading underscore — `_create_stream()`, `_identifier`
- **Type variables**: single uppercase or `PascalCase` — `T`, `ID`, `TDataRepresentation`

### Type Annotations

- Use `typing` module types: `Optional[str]`, `List[int]`, `Dict[str, Any]`
- Annotate all public method parameters and return types
- Use `TypeVar` for generics: `T = TypeVar("T", bound=StorageItem)`
- Use `TYPE_CHECKING` guard for imports only needed for type hints:
  ```python
  from typing import TYPE_CHECKING
  if TYPE_CHECKING:
      from fastapi import FastAPI
  ```

### Docstrings — Google Style

```python
def save(self, item: StorageItem) -> None:
    """Save the storage item.

    Args:
        item (StorageItem): The storage item to save

    Returns:
        None

    Raises:
        StorageError: If the item already exists
    """
```

Module-level docstrings on every file:
```python
"""The storage interface for storing and loading data."""
```

### Logging

```python
import logging
logger = logging.getLogger(__name__)
```

Always use `__name__` for the logger. Use `logger.info/warning/error/debug`.

### Error Handling

- Custom exceptions inherit from domain-specific base classes (e.g., `StorageError`)
- Use `raise ValueError(...)` for input validation
- Use `pytest.raises(ErrorType)` in tests
- Avoid bare `except:` — always catch specific exceptions

### Class Patterns

- **ABC for interfaces**: `class StorageItem(Serializable, ABC):`
- **@abstractmethod** for required overrides
- **@property** for computed attributes
- **Pydantic BaseModel** for data classes / API schemas
- **LifeCycle mixin** for component lifecycle hooks
- **@PublicAPI(stability="beta")** decorator to mark public APIs

### Async Patterns

- `async def` methods paired with sync versions: `before_start()` / `async_before_start()`
- `@pytest.mark.asyncio` for async test functions
- `pytest_asyncio.fixture` for async fixtures
- `@asynccontextmanager` for async context managers

### `__init__.py` Patterns

- Lazy loading via `__getattr__` for heavy submodules
- Explicit `__ALL__` for public API surface
- `# noqa: F401` on re-exports

```python
from dbgpt.component import BaseComponent, SystemApp  # noqa: F401
```

### Test Conventions

- Test files: `test_*.py` inside `tests/` directories co-located with source
- Fixtures in `conftest.py` at each test directory level
- Mock classes prefixed with `Mock`: `MockStorageItem`, `MockResourceIdentifier`
- Test function names: `test_<what_it_tests>` — `test_save_and_load`, `test_duplicate_save`
- Use `pytest.fixture` for setup, `pytest.raises` for expected errors
- Integration tests live in `tests/intetration_tests/` (note: typo is intentional — matches actual directory)

## Python Version

- Required: **>= 3.10** (set in pyproject.toml)
- Default dev: **3.11** (set in `.python-version`)

## Key Dependencies

- **pydantic** >= 2.6.0 (data models, validation)
- **SQLAlchemy** >= 2.0.25 (database ORM)
- **FastAPI** (REST API framework)
- **aiohttp** (async HTTP)
- **pytest** + **pytest-asyncio** (testing)
- **ruff** (linting/formatting)
- **mypy** (type checking)
