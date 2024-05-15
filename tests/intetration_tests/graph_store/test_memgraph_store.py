import pytest

from dbgpt.storage.graph_store.memgraph_store import (
    MemoryGraphStore,
    MemoryGraphStoreConfig,
)


@pytest.fixture
def graph_store():
    yield MemoryGraphStore(MemoryGraphStoreConfig())


def test_graph_store(graph_store):
    graph_store.insert_triplet("A", "0", "A")
    graph_store.insert_triplet("A", "1", "A")
    graph_store.insert_triplet("A", "2", "B")
    graph_store.insert_triplet("B", "3", "C")
    graph_store.insert_triplet("B", "4", "D")
    graph_store.insert_triplet("C", "5", "D")
    graph_store.insert_triplet("B", "6", "E")
    graph_store.insert_triplet("F", "7", "E")
    graph_store.insert_triplet("E", "8", "F")

    subgraph = graph_store.explore(["A"])
    print(f"\n{subgraph.graphviz()}")
    assert subgraph.edge_count == 9

    graph_store.delete_triplet("A", "0", "A")
    graph_store.delete_triplet("B", "4", "D")
    subgraph = graph_store.explore(["A"])
    print(f"\n{subgraph.graphviz()}")
    assert subgraph.edge_count == 7

    triplets = graph_store.get_triplets("B")
    print(f"\nTriplets of B: {triplets}")
    assert len(triplets) == 2

    schema = graph_store.get_schema()
    print(f"\nSchema: {schema}")
    assert len(schema) == 138
