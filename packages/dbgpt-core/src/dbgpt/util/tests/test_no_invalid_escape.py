r"""Guard against invalid string-literal escape sequences.

Python emits a ``SyntaxWarning: invalid escape sequence`` for backslash
sequences that are not recognized escapes (e.g. ``"\\d"`` written as
``"\d"``). These have been deprecated for years and become a hard
``SyntaxError`` in newer CPython releases, so a single offending literal can
make an entire module fail to import.

This test compiles the source files that previously contained such literals
and asserts none of them emit an ``invalid escape sequence`` warning.
"""

import py_compile
import warnings
from pathlib import Path

import pytest

# Resolve the monorepo's ``packages`` directory from this test file's location:
# .../packages/dbgpt-core/src/dbgpt/util/tests/test_no_invalid_escape.py
_PACKAGES_DIR = Path(__file__).resolve().parents[5]

# Files that historically carried invalid escape sequences. Relative to the
# monorepo ``packages`` directory so the test works from any checkout.
_GUARDED_FILES = [
    "dbgpt-core/src/dbgpt/agent/util/api_call.py",
    "dbgpt-core/src/dbgpt/agent/expand/actions/websearch_action.py",
    "dbgpt-ext/src/dbgpt_ext/datasource/rdbms/conn_vertica.py",
    "dbgpt-ext/src/dbgpt_ext/rag/knowledge/pdf.py",
    "dbgpt-app/src/dbgpt_app/scene/operators/app_operator.py",
]


def _invalid_escape_warnings(path: Path):
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", SyntaxWarning)
        py_compile.compile(str(path), doraise=True)
        return [w for w in caught if "invalid escape sequence" in str(w.message)]


@pytest.mark.parametrize("rel_path", _GUARDED_FILES)
def test_no_invalid_escape_sequence(rel_path):
    path = _PACKAGES_DIR / rel_path
    if not path.exists():
        pytest.skip(f"{rel_path} not present in this checkout")
    warns = _invalid_escape_warnings(path)
    messages = "\n".join(f"  line {w.lineno}: {w.message}" for w in warns)
    assert not warns, f"invalid escape sequence(s) in {rel_path}:\n{messages}"
