# test_tugraph_tugraph_store_adapter.py

import pytest

from dbgpt.storage.graph_store.tugraph_store import TuGraphStore, TuGraphStoreConfig
from dbgpt.storage.knowledge_graph.community.tugraph_store_adapter import (
    TuGraphStoreAdapter,
)


@pytest.fixture(scope="module")
def store():
    config = TuGraphStoreConfig(name="TestGraph", enable_summary=False)
    store = TuGraphStore(config=config)
    yield store
    store.conn.close()


@pytest.fixture(scope="module")
def tugraph_store_adapter(store: TuGraphStore):
    tugraph_store_adapter = TuGraphStoreAdapter(store)
    yield tugraph_store_adapter


def test_insert_and_get_triplets(tugraph_store_adapter: TuGraphStoreAdapter):
    tugraph_store_adapter.insert_triplet("A", "0", "A")
    tugraph_store_adapter.insert_triplet("A", "1", "A")
    tugraph_store_adapter.insert_triplet("A", "2", "B")
    tugraph_store_adapter.insert_triplet("B", "3", "C")
    tugraph_store_adapter.insert_triplet("B", "4", "D")
    tugraph_store_adapter.insert_triplet("C", "5", "D")
    tugraph_store_adapter.insert_triplet("B", "6", "E")
    tugraph_store_adapter.insert_triplet("F", "7", "E")
    tugraph_store_adapter.insert_triplet("E", "8", "F")
    triplets = tugraph_store_adapter.get_triplets("A")
    assert len(triplets) == 2
    triplets = tugraph_store_adapter.get_triplets("B")
    assert len(triplets) == 3
    triplets = tugraph_store_adapter.get_triplets("C")
    assert len(triplets) == 1
    triplets = tugraph_store_adapter.get_triplets("D")
    assert len(triplets) == 0
    triplets = tugraph_store_adapter.get_triplets("E")
    assert len(triplets) == 1
    triplets = tugraph_store_adapter.get_triplets("F")
    assert len(triplets) == 1


def test_query(tugraph_store_adapter: TuGraphStoreAdapter):
    query = "MATCH (n)-[r]->(n1) return n,n1,r limit 3"
    result = tugraph_store_adapter.query(query)
    v_c = result.vertex_count
    e_c = result.edge_count
    assert v_c == 3 and e_c == 3


def test_explore(tugraph_store_adapter: TuGraphStoreAdapter):
    subs = ["A", "B"]
    result = tugraph_store_adapter.explore(subs, depth=2, fan=None, limit=10)
    v_c = result.vertex_count
    e_c = result.edge_count
    assert v_c == 5 and e_c == 5


def test_delete_triplet(tugraph_store_adapter: TuGraphStoreAdapter):
    subj = "A"
    rel = "0"
    obj = "B"
    tugraph_store_adapter.delete_triplet(subj, rel, obj)
    triplets = tugraph_store_adapter.get_triplets(subj)
    assert len(triplets) == 0
