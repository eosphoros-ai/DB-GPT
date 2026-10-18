"""Read-only SQL guard for the benchmark pipeline.

The benchmark flow extracts a SQL statement from an LLM/agent HTTP
response (``_post_sql_query``) and executes it against the benchmark
SQLite database. That text is attacker-influenceable — in AGENT mode
the attacker controls the HTTP response outright — so it must never be
trusted as arbitrary SQL. Previously verified exploitation paths
included

* stacked statements via a second statement after a ``;``,
* ``ATTACH DATABASE '/any/path' AS x`` creating/opening arbitrary
  SQLite files (the attachment persists on the pooled connection, so a
  follow-up statement can write through it),
* plain DDL/DML against the shared benchmark database,
* ``WITH``-prefixed DML: SQLite's grammar allows ``WITH ... INSERT /
  UPDATE / DELETE / REPLACE INTO`` — starting with ``WITH`` does NOT
  make a statement read-only.

The guard therefore applies two independent checks on the top-level
token stream (string literals and comments excluded): the first
keyword must be ``SELECT`` or ``WITH``, and no top-level token may be a
write keyword (``REPLACE`` is only rejected in its ``REPLACE INTO``
DML form — ``REPLACE(...)`` is a legit string function).
"""

import logging
from typing import Iterator, List

logger = logging.getLogger(__name__)

_ALLOWED_FIRST_KEYWORDS = frozenset({"SELECT", "WITH"})

_WRITE_KEYWORDS = frozenset(
    {
        "INSERT",
        "UPDATE",
        "DELETE",
        "CREATE",
        "DROP",
        "ROLLBACK",
        "ALTER",
        "ATTACH",
        "DETACH",
        "PRAGMA",
        "VACUUM",
        "REINDEX",
        "ANALYZE",
        "EXPLAIN",
        "BEGIN",
        "COMMIT",
        "SAVEPOINT",
        "RELEASE",
    }
)
# REPLACE(...) is a string function; only the DML form is a write.
_WRITE_KEYWORD_PAIRS = {("REPLACE", "INTO")}


def _iter_top_level(sql: str) -> Iterator[str]:
    """Yield characters of ``sql`` that are top-level SQL tokens.

    Skips comments and the contents of quoted literals/identifiers
    (honoring doubled-quote escapes). Characters inside quotes therefore
    never contribute keywords or statement separators. Removed comments
    yield a space: SQLite treats a comment as a token boundary, so
    ``REPLACE/**/INTO`` must tokenize as two words — not merge into
    ``REPLACEINTO`` (which would bypass the multi-word write check).
    """
    i, n = 0, len(sql)
    while i < n:
        c = sql[i]
        # line comment
        if c == "-" and i + 1 < n and sql[i + 1] == "-":
            j = sql.find("\n", i)
            i = n if j == -1 else j + 1
            yield " "
            continue
        # block comment
        if c == "/" and i + 1 < n and sql[i + 1] == "*":
            j = sql.find("*/", i + 2)
            i = n if j == -1 else j + 2
            yield " "
            continue
        # quoted literal / quoted identifier / bracketed identifier
        if c in ("'", '"', "`", "["):
            closer = "]" if c == "[" else c
            i += 1
            while i < n:
                if sql[i] == closer:
                    # doubled quote inside the literal = escaped quote
                    if i + 1 < n and sql[i + 1] == closer:
                        i += 2
                        continue
                    i += 1
                    break
                i += 1
            continue
        yield c
        i += 1


def validate_read_only_sql(sql: str) -> str:
    """Validate that ``sql`` is a single read-only statement.

    Only a leading ``SELECT``/``WITH`` is allowed, no top-level write
    keyword may occur anywhere in the statement (catches
    ``WITH ... INSERT``), and no second statement may follow the
    (optional, trailing) semicolon. Returns ``sql`` unchanged on success
    so callers can log the validated statement; raises ``ValueError``
    otherwise.
    """
    if not isinstance(sql, str) or not sql.strip():
        raise ValueError("empty sql")

    words: List[str] = []
    current: List[str] = []
    after_semicolon = False
    non_space_after_semicolon = False

    def _flush() -> None:
        if current:
            words.append("".join(current).upper())
            current.clear()

    for c in _iter_top_level(sql):
        if after_semicolon:
            if not c.isspace() and c != ";":
                non_space_after_semicolon = True
            continue
        if c == ";":
            _flush()
            after_semicolon = True
            continue
        if c.isalpha() or c == "_":
            current.append(c)
        else:
            # whitespace or punctuation terminates the current word
            _flush()
    _flush()

    if not words:
        raise ValueError("no sql statement found")

    first_keyword = words[0]
    if first_keyword not in _ALLOWED_FIRST_KEYWORDS:
        raise ValueError(
            "benchmark sql must be a single read-only statement starting"
            f" with SELECT or WITH (got: {first_keyword[:16]!r})"
        )
    write_hits = [w for w in words if w in _WRITE_KEYWORDS]
    if write_hits:
        raise ValueError(f"benchmark sql contains write keyword: {write_hits[0]}")
    for first, second in zip(words, words[1:]):
        if (first, second) in _WRITE_KEYWORD_PAIRS:
            raise ValueError("benchmark sql contains write keyword: REPLACE INTO")
    if non_space_after_semicolon:
        raise ValueError("multiple sql statements are not allowed")
    return sql
