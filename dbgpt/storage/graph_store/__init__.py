"""Graph Store Module."""
from typing import Any


def _import_memgraph() -> Any:
    from dbgpt.storage.graph_store.memgraph_store import MemoryGraphStore
    return MemoryGraphStore


def _import_tugraph() -> Any:
    from dbgpt.storage.graph_store.tugraph_store import TuGraphStore
    return TuGraphStore


def _import_neo4j() -> Any:
    from dbgpt.storage.graph_store.neo4j_store import Neo4jStore
    return Neo4jStore


def __getattr__(name: str) -> Any:
    if name == "Memory":
        return _import_memgraph()
    elif name == "TuGraph":
        return _import_tugraph()
    elif name == "Neo4j":
        return _import_neo4j()
    else:
        raise AttributeError(f"Could not find: {name}")


__all__ = [
    "Memory", "TuGraph", "Neo4j"
]
