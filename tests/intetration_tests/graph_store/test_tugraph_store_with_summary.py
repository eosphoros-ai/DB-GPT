import pytest

from dbgpt.storage.graph_store.tugraph_store import TuGraphStore, \
    TuGraphStoreConfig
from dbgpt.storage.graph_store.graph import MemoryGraph, Edge, Vertex


@pytest.fixture(scope="module")
def store():
    config = TuGraphStoreConfig(name="TestSummaryGraph", summary_enabled=True)
    store_instance = TuGraphStore(config=config)
    yield store_instance
    store_instance.conn.close()


def test_insert_graph(store):
    graph = MemoryGraph(edge_label="name")
    vertex_list = [
        Vertex('A', description="Vertex A", _document_id="Test doc"),
        Vertex('B', description="Vertex B", _document_id="Test doc"),
        Vertex('C', description="Vertex C", _document_id="Test doc"),
        Vertex('D', description="Vertex D", _document_id="Test doc"),
        Vertex('E', description="Vertex E", _document_id="Test doc"),
        Vertex('F', description="Vertex F", _document_id="Test doc"),
        Vertex('G', description="Vertex G", _document_id="Test doc")
    ]
    edge_list = [
        Edge("A", "B", name='A-B', description="description of edge"),
        Edge("B", "C", name='B-C', description="description of edge"),
        Edge("C", "D", name='C-D', description="description of edge"),
        Edge("D", "E", name='D-E', description="description of edge"),
        Edge("E", "F", name='E-F', description="description of edge"),
        Edge("F", "G", name='F-G', description="description of edge")
    ]
    for vertex in vertex_list:
        graph.upsert_vertex(vertex)
    for edge in edge_list:
        graph.append_edge(edge)
    store.insert_graph(graph)


# def test_query_node_and_edge(store):
#     query = 'MATCH (n)-[r]->(m) WHERE n._community_id = "1" RETURN n,r,m'
#     result = store.query(query)
#     assert result.vertex_count == 7 and result.edge_count == 6

# def test_stream_query_path(store):
#     query = 'MATCH p=(n)-[r:relation*3]->(m) WHERE n._community_id = "1" RETURN p'
#     result = store.query(query)
#     assert result.vertex_count == 7 and result.edge_count == 6

def test_leiden_query(store):
    query = "CALL db.plugin.callPlugin('CPP','leiden','{\"leiden_val\":\"_community_id\"}',60.00,false)"
    result = store.query(query)
    print(result.get_vertex("json_node").get_prop('description'))
    assert result.vertex_count == 1

# def test_stream_query_path(store):
#     query = 'MATCH p=(n)-[r:relation*3]-(m) WHERE n._community_id = "1" RETURN p'
#     store.stream_query(query)
#     for graph in store.stream_query(query):
#         print(len(list(graph.vertices())))


# def test_stream_query_node_and_edge(store):
#     query = 'MATCH (n)-[r]-(m) WHERE n._community_id = "1" RETURN n,r,m'
#     store.stream_query(query)
#     for graph in store.stream_query(query):
#         print(len(list(graph.vertices())))


# def test_leiden_stream_query(store):
#     query = "CALL db.plugin.callPlugin('CPP','leiden','{\"leiden_val\":\"_community_id\"}',60.00,false)"
#     for graph in store.stream_query(query):
#         print(len(list(graph.vertices())))
