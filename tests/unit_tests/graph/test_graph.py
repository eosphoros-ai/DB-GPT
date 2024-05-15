import pytest

from dbgpt.storage.graph_store.graph import MemoryGraph, Edge, Vertex, Direction


@pytest.fixture
def g():
    g = MemoryGraph()
    g.append_edge(Edge("A", "A", label="0"))
    g.append_edge(Edge("A", "A", label="1"))
    g.append_edge(Edge("A", "B", label="2"))
    g.append_edge(Edge("B", "C", label="3"))
    g.append_edge(Edge("B", "D", label="4"))
    g.append_edge(Edge("C", "D", label="5"))
    g.append_edge(Edge("B", "E", label="6"))
    g.append_edge(Edge("F", "E", label="7"))
    g.append_edge(Edge("E", "F", label="8"))
    g.upsert_vertex(Vertex("G"))
    yield g


@pytest.mark.parametrize(
    "action, vc, ec",
    [
        (lambda g: g.del_vertices("G", "G"), 6, 9),
        (lambda g: g.del_vertices("C"), 6, 7),
        (lambda g: g.del_vertices("A", "G"), 5, 6),
        (lambda g: g.del_edges("E", "F", label="8"), 7, 8),
        (lambda g: g.del_edges("A", "B"), 7, 8),
        (lambda g: g.del_neighbor_edges("A", Direction.IN), 7, 7),
    ],
)
def test_delete(g, action, vc, ec):
    action(g)
    result = g.graphviz()
    print(f"\n{result}")
    assert g.vertex_count == vc
    assert g.edge_count == ec


@pytest.mark.parametrize(
    "vids, dir, vc, ec",
    [
        (["B"], Direction.OUT, 5, 6),
        (["A"], Direction.IN, 1, 2),
        (["F"], Direction.IN, 4, 6),
        (["B"], Direction.BOTH, 6, 9),
        (["A", "G"], Direction.BOTH, 7, 9),
    ],
)
def test_search(g, vids, dir, vc, ec):
    subgraph = g.search(vids, dir)
    print(f"\n{subgraph.graphviz()}")
    assert subgraph.vertex_count == vc
    assert subgraph.edge_count == ec


@pytest.mark.parametrize(
    "vids, dir, ec",
    [
        (["B"], Direction.BOTH, 5),
        (["B"], Direction.OUT, 5),
        (["B"], Direction.IN, 3),
    ],
)
def test_search_result_limit(g, vids, dir, ec):
    subgraph = g.search(vids, dir, limit=ec)
    print(f"\n{subgraph.graphviz()}")
    assert subgraph.edge_count == ec


@pytest.mark.parametrize(
    "vids, dir, fan, ec",
    [
        (["A"], Direction.OUT, 1, 1),
        (["B"], Direction.OUT, 2, 3),
        (["F"], Direction.IN, 1, 4),
    ],
)
def test_search_fan_limit(g, vids, dir, fan, ec):
    subgraph = g.search(vids, dir, fan=fan)
    print(f"\n{subgraph.graphviz()}")
    assert subgraph.edge_count == ec


@pytest.mark.parametrize(
    "vids, dir, dep, ec",
    [
        (["A"], Direction.OUT, 1, 3),
        (["A"], Direction.OUT, 2, 6),
        (["B"], Direction.OUT, 2, 5),
        (["B"], Direction.IN, 1, 1),
        (["D"], Direction.IN, 2, 4),
        (["B"], Direction.BOTH, 1, 4),
        (["B"], Direction.BOTH, 2, 9),
    ],
)
def test_search_depth_limit(g, vids, dir, dep, ec):
    subgraph = g.search(vids, dir, depth=dep)
    print(f"\n{subgraph.graphviz()}")
    assert subgraph.edge_count == ec
