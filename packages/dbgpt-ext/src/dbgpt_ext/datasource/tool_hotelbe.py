"""Hotel-be project file read tools for DB-GPT.

Provides safe, read-only file operations to query hotel-be source code.
Files are read from HOTELBE_PROJECT_ROOT (default: PROJECT_PATH env var).
"""

import fnmatch
import json
import os
from pathlib import Path
from typing import List

from dbgpt.agent.resource.tool.base import tool


_KNOWLEDGE_ROOT = Path(os.environ.get("HOTELBE_PROJECT_ROOT", os.environ.get("PROJECT_PATH", "/knowledge/hotel-be")))

_READABLE_EXTENSIONS = {
    ".go", ".md", ".yaml", ".yml", ".json", ".toml",
    ".proto", ".sql", ".sh", ".mk", ".mod", ".sum",
    ".dockerfile", ".env", ".gitignore",
}

_SKIP_DIRS = {
    ".git", "node_modules", "vendor", "dist", "build",
    ".claude", ".artifacts", ".auto-coder", ".cursor",
    "__pycache__", ".pytest_cache", ".mypy_cache",
}


def _is_readable(path: Path) -> bool:
    """Check if a file is safe and useful to read."""
    if not path.is_file():
        return False
    if path.stat().st_size > 1024 * 1024:
        return False
    ext = path.suffix.lower()
    if ext and ext not in _READABLE_EXTENSIONS:
        return False
    return True


def _collect_files(root: Path, pattern: str = "*") -> List[str]:
    """Collect readable files matching a glob pattern."""
    results = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
        for filename in filenames:
            if not fnmatch.fnmatch(filename, pattern):
                continue
            full_path = Path(dirpath) / filename
            if _is_readable(full_path):
                rel = full_path.relative_to(root)
                results.append(str(rel))
    return results[:100]


@tool(
    description="Read the full contents of a single file in the hotel-be project. "
    "Use this to inspect source code, configs, or documentation.",
)
def hotelbe_read_file(relative_path: str) -> str:
    """Read the contents of a file in the hotel-be project.

    Args:
        relative_path: Relative path from the hotel-be root, e.g. 'agent/config/llm.go'.
    """
    target = _KNOWLEDGE_ROOT / relative_path
    try:
        target.resolve().relative_to(_KNOWLEDGE_ROOT.resolve())
    except ValueError:
        return json.dumps({"error": "Path traversal not allowed"}, ensure_ascii=False)

    if not target.exists():
        return json.dumps(
            {"error": f"File not found: {relative_path}"}, ensure_ascii=False
        )
    if not _is_readable(target):
        return json.dumps(
            {"error": f"File is not readable or too large: {relative_path}"},
            ensure_ascii=False,
        )

    try:
        content = target.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)

    return json.dumps(
        {"path": relative_path, "size": len(content), "content": content},
        ensure_ascii=False,
    )


@tool(
    description="List files in the hotel-be project matching a glob pattern. "
    "Use this to discover files before reading them.",
)
def hotelbe_list_files(pattern: str = "*.go") -> str:
    """List files in the hotel-be project matching a glob pattern.

    Args:
        pattern: Glob pattern, e.g. '*.go', '**/*.md', 'agent/**/*.go'.
    """
    files = _collect_files(_KNOWLEDGE_ROOT, pattern)
    return json.dumps(
        {"pattern": pattern, "count": len(files), "files": files},
        ensure_ascii=False,
    )


@tool(
    description="Search for files in hotel-be whose content contains a keyword. "
    "Use this to find files related to a topic before reading them.",
)
def hotelbe_search_files(keyword: str, max_results: int = 20) -> str:
    """Search for files in hotel-be whose content contains a keyword.

    Args:
        keyword: The keyword to search for.
        max_results: Maximum number of matching files to return (default 20).
    """
    results = []
    for dirpath, dirnames, filenames in os.walk(_KNOWLEDGE_ROOT):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
        for filename in filenames:
            full_path = Path(dirpath) / filename
            if not _is_readable(full_path):
                continue
            try:
                content = full_path.read_text(encoding="utf-8", errors="replace")
                if keyword in content:
                    rel = full_path.relative_to(_KNOWLEDGE_ROOT)
                    lines = content.splitlines()
                    match_line = next(
                        (i + 1 for i, line in enumerate(lines) if keyword in line),
                        0,
                    )
                    results.append(
                        {
                            "path": str(rel),
                            "line": match_line,
                            "snippet": lines[match_line - 1].strip()
                            if match_line
                            else "",
                        }
                    )
                    if len(results) >= max_results:
                        break
            except Exception:
                continue
        if len(results) >= max_results:
            break

    return json.dumps(
        {"keyword": keyword, "count": len(results), "matches": results},
        ensure_ascii=False,
    )


@tool(
    description="Search for a Go symbol (function, struct, interface, method) "
    "in hotel-be source code. Returns file paths and matching line contexts.",
)
def hotelbe_grep_code(symbol: str) -> str:
    """Search for a Go symbol in hotel-be source.

    Args:
        symbol: The symbol name, e.g. 'KnowledgeSyncConfig' or 'func Sync'.
    """
    results = []
    for dirpath, dirnames, filenames in os.walk(_KNOWLEDGE_ROOT):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
        for filename in filenames:
            if not filename.endswith(".go"):
                continue
            full_path = Path(dirpath) / filename
            try:
                content = full_path.read_text(encoding="utf-8", errors="replace")
                if symbol in content:
                    rel = full_path.relative_to(_KNOWLEDGE_ROOT)
                    lines = content.splitlines()
                    matches = []
                    for i, line in enumerate(lines):
                        if symbol in line:
                            context_start = max(0, i - 2)
                            context_end = min(len(lines), i + 3)
                            context = "\n".join(lines[context_start:context_end])
                            matches.append({"line": i + 1, "context": context})
                            if len(matches) >= 3:
                                break
                    results.append({"path": str(rel), "matches": matches})
                    if len(results) >= 10:
                        break
            except Exception:
                continue
        if len(results) >= 10:
            break

    return json.dumps(
        {"symbol": symbol, "count": len(results), "files": results},
        ensure_ascii=False,
    )
