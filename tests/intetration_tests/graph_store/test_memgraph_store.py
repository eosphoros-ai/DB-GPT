import pytest

from dbgpt.storage.graph_store.memgraph_store import (
    MemoryGraphStore,
    MemoryGraphStoreConfig,
)
from dbgpt.storage.knowledge_graph.community.memgraph_store_adapter import (
    MemGraphStoreAdapter,
)


@pytest.fixture
def graph_store():
    yield MemoryGraphStore(MemoryGraphStoreConfig())


@pytest.fixture
def graph_store_adapter(graph_store: MemoryGraphStore):
    memgraph_store_adapter = MemGraphStoreAdapter(graph_store)
    yield memgraph_store_adapter


def test_graph_store(graph_store_adapter: MemGraphStoreAdapter):
    graph_store_adapter.insert_triplet("A", "0", "A")
    graph_store_adapter.insert_triplet("A", "1", "A")
    graph_store_adapter.insert_triplet("A", "2", "B")
    graph_store_adapter.insert_triplet("B", "3", "C")
    graph_store_adapter.insert_triplet("B", "4", "D")
    graph_store_adapter.insert_triplet("C", "5", "D")
    graph_store_adapter.insert_triplet("B", "6", "E")
    graph_store_adapter.insert_triplet("F", "7", "E")
    graph_store_adapter.insert_triplet("E", "8", "F")

    subgraph = graph_store_adapter.explore(["A"])
    print(f"\n{subgraph.format()}")
    assert subgraph.edge_count == 9

    graph_store_adapter.delete_triplet("A", "0", "A")
    graph_store_adapter.delete_triplet("B", "4", "D")
    subgraph = graph_store_adapter.explore(["A"])
    print(f"\n{subgraph.format()}")
    assert subgraph.edge_count == 7

    triplets = graph_store_adapter.get_triplets("B")
    print(f"\nTriplets of B: {triplets}")
    assert len(triplets) == 2

    schema = graph_store_adapter.get_schema()
    print(f"\nSchema: {schema}")
    assert len(schema) == 86
