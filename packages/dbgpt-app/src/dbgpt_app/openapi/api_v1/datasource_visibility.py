"""Datasource names that are reserved for DB-GPT itself.

These names are hidden from the datasource listing, so the same rule has to be
applied wherever a caller-supplied datasource name is turned into a connector.
Otherwise the internal metadata database (registered as ``dbgpt``) stays
reachable by name even though no user can see it.
"""

from typing import Any

HIDDEN_DATASOURCE_NAMES = frozenset({"auth", "dbgpt", "test", "public"})


def is_hidden_datasource(db_name: Any) -> bool:
    """Return True if ``db_name`` refers to a reserved, user-hidden datasource.

    The comparison ignores case and surrounding whitespace: the metadata
    database commonly uses a case-insensitive, pad-space collation, so a lookup
    for ``"DBGPT"`` or ``"dbgpt "`` resolves to the same ``dbgpt`` row.
    """
    if not isinstance(db_name, str):
        return False
    return db_name.strip().lower() in HIDDEN_DATASOURCE_NAMES
