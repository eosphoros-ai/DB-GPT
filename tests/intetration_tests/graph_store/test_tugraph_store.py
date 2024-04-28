# test_tugraph_store.py

import pytest
from dbgpt.storage.graph_store.tugraph_store import TuGraphStore  

@pytest.fixture(scope="module")
def tugraph_store():
    store = TuGraphStore(
        host='100.88.118.28',
        port=37687,
        user='admin',
        pwd='123456',
        db_name='RAG_1'
    )
    yield store
    store.conn.close()

def test_insert_and_get_triplets(tugraph_store):
    subj = "test_subject"
    obj = "test_object"
    rel = "test_relation"

    tugraph_store.delete_triplets(subj, obj)
    tugraph_store.insert_triplet(subj, rel, obj)
    results = tugraph_store.get_triplets(subj)
    print(results)
    expected = [[rel, obj]]
    assert results == expected, "The returned triplets should match the inserted data."

    tugraph_store.delete_triplets(subj, obj)

