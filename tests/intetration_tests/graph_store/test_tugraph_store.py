# test_tugraph_store.py

import pytest

from dbgpt.storage.graph_store.tugraph_store import TuGraphStore, TuGraphStoreConfig
from dbgpt.storage.graph_store.graph import MemoryGraph,Edge,Vertex




@pytest.fixture(scope="module")
def store():
    config = TuGraphStoreConfig(name="TestGraph",summary_enabled=True)
    store = TuGraphStore(config=config)
    yield store
    store.conn.close()


# def test_insert_and_get_triplets(store):
#     store.insert_triplet("A", "0", "A")
#     store.insert_triplet("A", "1", "A")
#     store.insert_triplet("A", "2", "B")
#     store.insert_triplet("B", "3", "C")
#     store.insert_triplet("B", "4", "D")
#     store.insert_triplet("C", "5", "D")
#     store.insert_triplet("B", "6", "E")
#     store.insert_triplet("F", "7", "E")
#     store.insert_triplet("E", "8", "F")
#     triplets = store.get_triplets("A")
#     assert len(triplets) == 3
#     triplets = store.get_triplets("B")
#     assert len(triplets) == 3
#     triplets = store.get_triplets("C")
#     assert len(triplets) == 1
#     triplets = store.get_triplets("D")
#     assert len(triplets) == 0
#     triplets = store.get_triplets("E")
#     assert len(triplets) == 1
#     triplets = store.get_triplets("F")
#     assert len(triplets) == 1


# def test_query(store):
#     query = "MATCH (n)-[r]->(n1) return n,n1,r limit 3"
#     result = store.query(query)
#     v_c = result.vertex_count
#     e_c = result.edge_count
#     assert v_c == 2 and e_c == 3


# def test_explore(store):
#     subs = ["A", "B"]
#     result = store.explore(subs, depth=2, fan=None, limit=10)
#     v_c = result.vertex_count
#     e_c = result.edge_count
#     assert v_c == 2 and e_c == 3


# def test_delete_triplet(store):
#     subj = "A"
#     rel = "0"
#     obj = "B"
#     store.delete_triplet(subj, rel, obj)
#     triplets = store.get_triplets(subj)
#     assert len(triplets) == 0


def test_insert_graph(store):
    graph = MemoryGraph()
    vertex_G = Vertex('G', description="Vertex G", _document_id="Test doc")
    vertex_H = Vertex('H', description="Vertex H", _document_id="Test doc")
    edge = Edge("G","H",label='G_H', description = "G rel H")
    graph.upsert_vertex(vertex_G)
    graph.upsert_vertex(vertex_H)
    graph.append_edge(edge)
    store.insert_graph(graph)

def test_stream_query(store):
    query = 'MATCH p=(n)-[r]-(m) WHERE n._community_id = 1 RETURN n,r,m,p'
    store.stream_query(query)
    for record in store.stream_query(query):
        for node in record.vertices():
            pass
            # print(node)
        for edge in record.edges():
            pass
            # print(edge)
