"""Static risk analysis for code payloads (Python AST).

code executes **Python only**, and the tool rejects anything that
does not compile before running it — so the stdlib ``ast`` module gives exact
call/import/open-mode semantics with zero new dependencies. tree-sitter's
error-tolerant parsing would only help for snippets that cannot compile, and
those never execute; the analyzer therefore keeps a parser seam
(``parse_python``) so a tree-sitter backend can be plugged in if the sandbox
ever goes multi-language, while defaulting to ``ast``.

Verdict model (deliberately conservative in both directions):

- ``provably_safe``: parses, imports ⊆ allowlist, and no known sink → the
  builtin ``code.static_auto`` rule lets pure analysis code (pandas reads,
  math, print, matplotlib) pass without a card;
- ``has_sink``: exec/eval/subprocess/network/fs-write/db-write call present →
  the builtin ``code.static_sink`` rule confirms even when the fail-safe
  parameter is relaxed to auto;
- everything else (unknown imports, unparsable snippets) falls through to the
  gated-tool fail-safe tier, exactly as before.
"""

import ast
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

# ── import policy ───────────────────────────────────────────────────────────
# Analysis/computation stdlib + the data stack the tool preamble promises.
SAFE_IMPORT_ROOTS = {
    "pandas",
    "numpy",
    "matplotlib",
    "seaborn",
    "plotly",
    "json",
    "math",
    "cmath",
    "re",
    "datetime",
    "time",
    "calendar",
    "collections",
    "itertools",
    "functools",
    "statistics",
    "random",
    "string",
    "textwrap",
    "unicodedata",
    "pprint",
    "copy",
    "operator",
    "bisect",
    "heapq",
    "array",
    "decimal",
    "fractions",
    "hashlib",
    "base64",
    "csv",
    "io",
    "typing",
    "dataclasses",
    "warnings",
    "enum",
    "abc",
    "os",
    "sys",
    "pathlib",
    "ast",
    "inspect",
    "platform",
    "sqlite3",
    "glob",
    "fnmatch",
    "shutil",
    "logging",
    "struct",
    "zlib",
    "gzip",
    "zipfile",
    "tarfile",
    "tempfile",
    "uuid",
    "html",
    "xml",
}

# Importing these is itself a strong side-effect signal (exec / network /
# native code / deserialization), even before any call is seen.
CONFIRM_IMPORT_ROOTS = {
    "subprocess",
    "socket",
    "requests",
    "urllib",
    "http",
    "aiohttp",
    "httpx",
    "ftplib",
    "smtplib",
    "telnetlib",
    "ctypes",
    "pty",
    "pickle",
    "shelve",
    "marshal",
    "importlib",
    "paramiko",
    "sqlalchemy",
    "pymysql",
    "psycopg2",
    "multiprocessing",
    "asyncio",
}

# ── call sinks (confirm tier) ───────────────────────────────────────────────
_SINK_DOTTED = {
    "os.system",
    "os.popen",
    "os.exec",
    "os.execl",
    "os.execle",
    "os.execlp",
    "os.execv",
    "os.execve",
    "os.fork",
    "os.kill",
    "os.killpg",
    "os.remove",
    "os.unlink",
    "os.rmdir",
    "os.removedirs",
    "os.rename",
    "os.renames",
    "os.replace",
    "os.chmod",
    "os.chown",
    "os.symlink",
    "os.link",
    "shutil.rmtree",
    "shutil.move",
    "shutil.copy",
    "shutil.copy2",
    "shutil.copytree",
    "urllib.request.urlopen",
    "socket.socket",
    "socket.create_connection",
    "importlib.import_module",
    "pathlib.Path.write_text",
    "pathlib.Path.write_bytes",
    "asyncio.create_subprocess_exec",
    "asyncio.create_subprocess_shell",
}
_SINK_ROOTS = {"subprocess", "pty", "ftplib", "smtplib", "telnetlib", "requests"}
# Bare-name sinks (eval/exec/__import__/compile-exec patterns).
_SINK_NAMES = {"eval", "exec", "__import__"}
# Method-name sinks regardless of receiver (write/delete semantics).
_SINK_METHODS = {
    "write_text",
    "write_bytes",
    "to_sql",
    "to_excel",
    "to_parquet",
    "rmtree",
    "popen",
    "executescript",
}
# cursor.execute("DELETE …") with a literal write statement is a DB write;
# a literal SELECT/PRAGMA stays read-only. Non-literal SQL is not provable
# and falls to the fail-safe tier instead.
_SQL_WRITE_VERBS = (
    "insert",
    "update",
    "delete",
    "drop",
    "alter",
    "create",
    "replace",
    "attach",
    "detach",
    "vacuum",
    "reindex",
)
# df.to_csv() / df.to_json() with NO path argument return a string (a common
# print idiom); with a path they write a file.
_PATH_OPTIONAL_WRITES = {"to_csv", "to_json", "to_html"}
_PATH_KWARGS = {"path_or_buf", "path", "buf", "fh", "filename"}
# Directory creation inside the per-conversation sandbox is the designed
# artifact workflow (PLOT_DIR), so it stays neutral.
_NEUTRAL_DOTTED = {"os.mkdir", "os.makedirs", "os.getcwd", "os.chdir"}


@dataclass
class CodeRisk:
    """Static analysis result for one code payload."""

    parse_ok: bool
    imports: Set[str] = field(default_factory=set)
    sinks: List[str] = field(default_factory=list)
    write_opens: List[int] = field(default_factory=list)
    # Statically opaque constructs (e.g. ``execute(variable_sql)``): not sinks
    # by themselves, but they void the provably-safe verdict.
    unprovable: List[str] = field(default_factory=list)

    @property
    def has_sink(self) -> bool:
        return (
            bool(self.sinks)
            or bool(self.write_opens)
            or bool(self.imports & CONFIRM_IMPORT_ROOTS)
        )

    @property
    def provably_safe(self) -> bool:
        return (
            self.parse_ok
            and not self.has_sink
            and not self.unprovable
            and not (self.imports - SAFE_IMPORT_ROOTS)
        )


def parse_python(code: str) -> Optional[ast.Module]:
    """Parser seam: stdlib ast today, tree-sitter backend tomorrow."""
    try:
        return ast.parse(code)
    except (SyntaxError, ValueError, RecursionError):
        return None


def _dotted(node: ast.AST) -> str:
    parts: List[str] = []
    cur = node
    while isinstance(cur, ast.Attribute):
        parts.append(cur.attr)
        cur = cur.value
    if isinstance(cur, ast.Name):
        parts.append(cur.id)
    return ".".join(reversed(parts))


def _open_mode(node: ast.Call) -> Optional[str]:
    if len(node.args) >= 2 and isinstance(node.args[1], ast.Constant):
        return str(node.args[1].value)
    for kw in node.keywords:
        if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
            return str(kw.value.value)
    return None


def _is_write_mode(mode: Optional[str]) -> bool:
    if not mode:
        return False  # open() defaults to read
    return bool(set(mode) & {"w", "a", "x", "+"})


def analyze_python(code: str) -> CodeRisk:
    tree = parse_python(code or "")
    if tree is None:
        return CodeRisk(parse_ok=False)
    risk = CodeRisk(parse_ok=True)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                risk.imports.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                risk.imports.add(node.module.split(".")[0])
        elif isinstance(node, ast.Call):
            name = _dotted(node.func)
            base = name.split(".")[0]
            method = name.split(".")[-1] if "." in name else ""
            if isinstance(node.func, ast.Name) and name in _SINK_NAMES:
                risk.sinks.append(name)
            elif name in _SINK_DOTTED:
                risk.sinks.append(name)
            elif base in _SINK_ROOTS:
                risk.sinks.append(name or base)
            elif method in _SINK_METHODS:
                risk.sinks.append(name)
            elif method in ("execute", "executemany"):
                sql = node.args[0] if node.args else None
                if isinstance(sql, ast.Constant) and isinstance(sql.value, str):
                    head = sql.value.strip().split(None, 1)[:1]
                    if head and head[0].lower() in _SQL_WRITE_VERBS:
                        risk.sinks.append(f"{name}:{head[0].upper()}")
                else:
                    # Non-literal SQL is not statically provable; the
                    # fail-safe tier decides those.
                    risk.unprovable.append(name)
            elif method in _PATH_OPTIONAL_WRITES:
                has_path = bool(node.args) or any(
                    kw.arg in _PATH_KWARGS for kw in node.keywords
                )
                if has_path:
                    risk.sinks.append(name)
            elif name == "open" or (base == "io" and method == "open"):
                if _is_write_mode(_open_mode(node)):
                    risk.write_opens.append(getattr(node, "lineno", 0))
    return risk


_CACHE: Dict[str, CodeRisk] = {}


def analyze_args(args: dict) -> CodeRisk:
    """Analyze the code payload of a code args dict (memoized)."""
    code = ""
    if isinstance(args, dict):
        value = args.get("code") or args.get("query") or ""
        code = value if isinstance(value, str) else str(value)
    hit = _CACHE.get(code)
    if hit is None:
        hit = analyze_python(code)
        _CACHE[code] = hit
        if len(_CACHE) > 512:
            _CACHE.clear()
            _CACHE[code] = hit
    return hit


def code_has_sink(args: dict) -> bool:
    return analyze_args(args).has_sink


def code_provably_safe(args: dict) -> bool:
    return analyze_args(args).provably_safe


def describe(args: dict) -> Tuple[bool, List[str]]:
    """(provably_safe, sink list) for traces / playground display."""
    risk = analyze_args(args)
    return risk.provably_safe, list(dict.fromkeys(risk.sinks))
