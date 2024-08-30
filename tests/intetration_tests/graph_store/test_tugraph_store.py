# test_tugraph_store.py

import pytest

from dbgpt.storage.graph_store.tugraph_store import TuGraphStore, TuGraphStoreConfig


@pytest.fixture(scope="module")
def store():
    config = TuGraphStoreConfig(name="TestGraph", summary_enabled=False)
    store = TuGraphStore(config=config)
    yield store
    store.conn.close()


def test_insert_and_get_triplets(store):
    store.insert_triplet("A", "0", "A")
    store.insert_triplet("A", "1", "A")
    store.insert_triplet("A", "2", "B")
    store.insert_triplet("B", "3", "C")
    store.insert_triplet("B", "4", "D")
    store.insert_triplet("C", "5", "D")
    store.insert_triplet("B", "6", "E")
    store.insert_triplet("F", "7", "E")
    store.insert_triplet("E", "8", "F")
    triplets = store.get_triplets("A")
    assert len(triplets) == 2
    triplets = store.get_triplets("B")
    assert len(triplets) == 3
    triplets = store.get_triplets("C")
    assert len(triplets) == 1
    triplets = store.get_triplets("D")
    assert len(triplets) == 0
    triplets = store.get_triplets("E")
    assert len(triplets) == 1
    triplets = store.get_triplets("F")
    assert len(triplets) == 1


def test_query(store):
    query = "MATCH (n)-[r]->(n1) return n,n1,r limit 3"
    result = store.query(query)
    v_c = result.vertex_count
    e_c = result.edge_count
    assert v_c == 3 and e_c == 3


def test_explore(store):
    subs = ["A", "B"]
    result = store.explore(subs, depth=2, fan=None, limit=10)
    v_c = result.vertex_count
    e_c = result.edge_count
    assert v_c == 5 and e_c == 5


def test_delete_triplet(store):
    subj = "A"
    rel = "0"
    obj = "B"
    store.delete_triplet(subj, rel, obj)
    triplets = store.get_triplets(subj)
    assert len(triplets) == 0
