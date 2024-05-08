import pytest

from dbgpt.storage.graph_store.graph import MemoryGraph, Edge, Vertex, Direction


@pytest.fixture
def g():
    g = MemoryGraph()
    g.append_edge(Edge("A", "A", label='0'))
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


@pytest.mark.parametrize("action, rs_len", [
    (lambda g: g.del_vertex("G"), 185),
    (lambda g: g.del_vertex("C"), 151),
    (lambda g: g.del_edge("E", "F", label='8'), 170),
    (lambda g: g.del_edge("A", "B"), 170),
    (lambda g: g.del_edges("A", Direction.IN), 151),
])
def test_delete(g, action, rs_len):
    action(g)
    result = g.graphviz()
    print(f"\n{result}")
    assert len(result) == rs_len


@pytest.mark.parametrize("vids, dir, rs_len", [
    (["B"], Direction.OUT, 128),
    (["A"], Direction.IN, 52),
    (["F"], Direction.IN, 128),
    (["B"], Direction.BOTH, 185),
    (["A", "G"], Direction.BOTH, 189),
])
def test_bfs(g, vids, dir, rs_len):
    result = g.bfs(vids, dir).graphviz()
    print(f"\n{result}")
    assert len(result) == rs_len


@pytest.mark.parametrize("vids, dir, rs_lim", [
    (["B"], Direction.BOTH, 5),
    (["B"], Direction.OUT, 5),
    (["B"], Direction.IN, 3),
])
def test_bfs_result_limit(g, vids, dir, rs_lim):
    subgraph = g.bfs(vids, dir, result_limit=rs_lim)
    print(f"\n{subgraph.graphviz()}")
    assert sum(1 for _ in subgraph.edges()) == rs_lim


@pytest.mark.parametrize("vids, dir, fan_lim, rs_len", [
    (["A"], Direction.OUT, 1, 1),
    (["B"], Direction.OUT, 2, 3),
    (["F"], Direction.IN, 1, 4),
])
def test_bfs_fan_limit(g, vids, dir, fan_lim, rs_len):
    subgraph = g.bfs(vids, dir, fan_limit=fan_lim)
    print(f"\n{subgraph.graphviz()}")
    assert sum(1 for _ in subgraph.edges()) == rs_len


@pytest.mark.parametrize("vids, dir, dep_lim, rs_len", [
    (["A"], Direction.OUT, 1, 3),
    (["A"], Direction.OUT, 2, 6),
    (["B"], Direction.OUT, 2, 5),
    (["B"], Direction.IN, 1, 1),
    (["D"], Direction.IN, 2, 3),
    (["B"], Direction.BOTH, 1, 4),
    (["B"], Direction.BOTH, 2, 9),
])
def test_bfs_depth_limit(g, vids, dir, dep_lim, rs_len):
    subgraph = g.bfs(vids, dir, depth_limit=dep_lim)
    print(f"\n{subgraph.graphviz()}")
    assert sum(1 for _ in subgraph.edges()) == rs_len

# todo: bfs not real \ visitSet error?
