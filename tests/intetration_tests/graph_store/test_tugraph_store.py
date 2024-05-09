# test_tugraph_store.py

import pytest

from dbgpt.storage.graph_store.tugraph_store import TuGraphStore


@pytest.fixture(scope="module")
def store():
    store = TuGraphStore(
        host='localhost',
        port=7687,
        user='admin',
        pwd='73@TuGraph',
        db_name='RAG_1'
    )
    yield store
    store.conn.close()


def test_insert_and_get_triplets(store):
    subj = 'Tom'
    rel = 'is'
    obj = 'Cat'
    store.insert_triplet(subj, rel, obj)
    triplets = store.get_triplets(subj)
    assert len(triplets) == 1
    assert triplets[0] == [rel, obj]

def test_get_rel_map(store):
    subjs = ['Tom', 'Cat']
    rel_map = store.get_rel_map(subjs, depth=2, limit=10)
    assert len(rel_map) > 0

def test_delete_triplets(store):
    subj = 'Tom'
    obj = 'Cat'
    store.delete_triplets(subj, obj)
    triplets = store.get_triplets(subj)
    assert len(triplets) == 0

# def test_explore(store):
#     subs = ['subj1', 'subj2']
#     result = store.explore(subs, depth_limit=2, fan_limit=None, result_limit=30)
#     # Add your assertions here

# def test_query(store):
#     query = "MATCH (n) RETURN n LIMIT 10"
#     result = store.query(query)
#     # Add your assertions here