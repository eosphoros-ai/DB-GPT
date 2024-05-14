"""Graph Store Module."""
from typing import Type


def _import_memgraph() -> (Type, Type):
    from dbgpt.storage.graph_store.memgraph_store import MemoryGraphStore
    from dbgpt.storage.graph_store.memgraph_store import MemoryGraphStoreConfig
    return MemoryGraphStore, MemoryGraphStoreConfig


def _import_tugraph() -> (Type, Type):
    from dbgpt.storage.graph_store.tugraph_store import TuGraphStore
    from dbgpt.storage.graph_store.tugraph_store import TuGraphStoreConfig
    return TuGraphStore, TuGraphStoreConfig


def _import_neo4j() -> (Type, Type):
    from dbgpt.storage.graph_store.neo4j_store import Neo4jStore
    from dbgpt.storage.graph_store.neo4j_store import Neo4jStoreConfig
    return Neo4jStore, Neo4jStoreConfig


def __getattr__(name: str) -> (Type, Type):
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
