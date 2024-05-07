import pytest

from dbgpt.storage.graph_store.graph import MemoryGraph, Edge, Vertex, Direction


@pytest.fixture
def g():
    g = MemoryGraph()
    g.append_edge(Edge("A", "A", laben='0'))
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


def print_check(text, length=None, validator=None):
    if not length and not validator:
        sep = '' if text.endswith("\n") else '\n'
        print(f"\n{text}{sep}>>> output length: {len(text)}")
    else:
        print(f"\n{text}")
        if length:
            assert len(text) == length
        if validator:
            assert validator(text)


def test_traverse(g):
    sub = g.traverse(["A", "G"], direction=Direction.OUT)
    print_check(sub.graphviz(), 189)

    sub = g.traverse(["A"], direction=Direction.IN)
    print_check(sub.graphviz(), 52)

    sub = g.traverse(["F"], direction=Direction.IN)
    print_check(sub.graphviz(), 128)

    sub = g.traverse(["B"], direction=Direction.OUT)
    print_check(sub.graphviz(), 128)

    sub = g.traverse(["B"], direction=Direction.BOTH)
    print_check(sub.graphviz(), 185)


def test_delete(g):
    g.del_vertex("G")
    print_check(g.graphviz(), 185)

    g.del_vertex("F")
    g.del_vertex("E")
    print_check(g.graphviz(), 128)

    g.del_edges("A", Direction.IN)
    print_check(g.graphviz(), 90)
