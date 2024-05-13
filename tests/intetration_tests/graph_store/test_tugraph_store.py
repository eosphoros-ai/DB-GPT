# test_tugraph_store.py

import pytest

from dbgpt.storage.graph_store.tugraph_store import TuGraphStore


@pytest.fixture(scope="module")
def store():
    store = TuGraphStore(
        host="localhost", port=7687, user="admin", pwd="123456", graph_name="RAG_1"
    )
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
    assert len(triplets) == 3
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


def test_get_rel_map(store):
    subjs = ["A", "B"]
    rel_map = store.get_rel_map(subjs, depth=2, limit=10)
    assert len(rel_map) == 10


def test_explore(store):
    subs = ["A", "B"]
    result = store.explore(subs, depth=2, fan=None, limit=10)
    v_c = result.vertex_count
    e_c = result.edge_count
    assert v_c == 2 and e_c == 4


def test_delete_triplet(store):
    subj = "A"
    rel = "0"
    obj = "B"
    store.delete_triplet(subj, rel, obj)
    triplets = store.get_triplets(subj)
    assert len(triplets) == 0


# def test_query(store):
#     query = "MATCH (n) RETURN n LIMIT 10"
#     result = store.query(query)
#     # Add your assertions here
