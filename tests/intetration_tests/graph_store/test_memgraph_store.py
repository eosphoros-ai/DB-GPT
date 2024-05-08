import pytest

from dbgpt.storage.graph_store.memgraph_store import MemoryGraphStore


@pytest.fixture
def graph_store():
    yield MemoryGraphStore()


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

    graph_store.explore(["A"])
