"""Tests for dependency graph data structure and algorithms."""

from __future__ import annotations

import pytest

from depgraph.analysis.graph import DependencyGraph
from depgraph.models import Dependency, Ecosystem, Edge


@pytest.fixture
def simple_graph() -> DependencyGraph:
    """Create a simple dependency graph: A -> B -> C."""
    graph = DependencyGraph()
    graph.add_node(Dependency(name="A", version="1.0", ecosystem=Ecosystem.PIP))
    graph.add_node(Dependency(name="B", version="2.0", ecosystem=Ecosystem.PIP))
    graph.add_node(Dependency(name="C", version="3.0", ecosystem=Ecosystem.PIP))
    graph.add_edge(Edge(source="A", target="B"))
    graph.add_edge(Edge(source="B", target="C"))
    return graph


@pytest.fixture
def cyclic_graph() -> DependencyGraph:
    """Create a graph with a cycle: A -> B -> C -> A."""
    graph = DependencyGraph()
    graph.add_node(Dependency(name="A", version="1.0", ecosystem=Ecosystem.PIP))
    graph.add_node(Dependency(name="B", version="2.0", ecosystem=Ecosystem.PIP))
    graph.add_node(Dependency(name="C", version="3.0", ecosystem=Ecosystem.PIP))
    graph.add_edge(Edge(source="A", target="B"))
    graph.add_edge(Edge(source="B", target="C"))
    graph.add_edge(Edge(source="C", target="A"))
    return graph


@pytest.fixture
def diamond_graph() -> DependencyGraph:
    """Create a diamond dependency graph.

        A
       / \\
      B   C
       \\ /
        D
    """
    graph = DependencyGraph()
    graph.add_node(Dependency(name="A", version="1.0", ecosystem=Ecosystem.PIP))
    graph.add_node(Dependency(name="B", version="2.0", ecosystem=Ecosystem.PIP))
    graph.add_node(Dependency(name="C", version="3.0", ecosystem=Ecosystem.PIP))
    graph.add_node(Dependency(name="D", version="4.0", ecosystem=Ecosystem.PIP))
    graph.add_edge(Edge(source="A", target="B"))
    graph.add_edge(Edge(source="A", target="C"))
    graph.add_edge(Edge(source="B", target="D"))
    graph.add_edge(Edge(source="C", target="D"))
    return graph


class TestDependencyGraph:
    """Test the DependencyGraph class."""

    def test_add_node(self, simple_graph: DependencyGraph) -> None:
        assert simple_graph.size == 3
        assert "A" in simple_graph.nodes
        assert "B" in simple_graph.nodes
        assert "C" in simple_graph.nodes

    def test_add_edge(self, simple_graph: DependencyGraph) -> None:
        assert len(simple_graph.edges) == 2
        assert simple_graph.successors("A") == ["B"]
        assert simple_graph.successors("B") == ["C"]
        assert simple_graph.successors("C") == []

    def test_predecessors(self, simple_graph: DependencyGraph) -> None:
        assert simple_graph.predecessors("A") == []
        assert simple_graph.predecessors("B") == ["A"]
        assert simple_graph.predecessors("C") == ["B"]

    def test_bfs_depth(self, simple_graph: DependencyGraph) -> None:
        depths = simple_graph.bfs_depth("A")
        assert depths == {"A": 0, "B": 1, "C": 2}

    def test_max_depth(self, simple_graph: DependencyGraph) -> None:
        assert simple_graph.max_depth("A") == 2

    def test_max_breadth(self, diamond_graph: DependencyGraph) -> None:
        # Diamond: A(1) -> B,C(2) -> D(1)
        breadth = diamond_graph.max_breadth("A")
        assert breadth == 2  # Level 1 has 2 nodes (B, C)

    def test_reachable_from(self, simple_graph: DependencyGraph) -> None:
        reachable = simple_graph.reachable_from("A")
        assert reachable == {"B", "C"}

    def test_reachable_from_leaf(self, simple_graph: DependencyGraph) -> None:
        reachable = simple_graph.reachable_from("C")
        assert reachable == set()

    def test_find_orphans(self, simple_graph: DependencyGraph) -> None:
        # Add an unreachable node
        simple_graph.add_node(Dependency(name="Z", version="1.0", ecosystem=Ecosystem.PIP))
        orphans = simple_graph.find_orphans(["A"])
        assert "Z" in orphans
        assert "A" not in orphans

    def test_no_cycles(self, simple_graph: DependencyGraph) -> None:
        cycles = simple_graph.detect_cycles()
        assert cycles == []

    def test_detect_cycle(self, cyclic_graph: DependencyGraph) -> None:
        cycles = cyclic_graph.detect_cycles()
        assert len(cycles) == 1
        assert cycles[0].length == 3

    def test_cycle_display(self, cyclic_graph: DependencyGraph) -> None:
        cycles = cyclic_graph.detect_cycles()
        display = cycles[0].display
        assert "A" in display
        assert "B" in display
        assert "C" in display
        assert "->" in display

    def test_toposort(self, simple_graph: DependencyGraph) -> None:
        order = simple_graph.toposort()
        # A must come before B, B before C
        assert order.index("A") < order.index("B")
        assert order.index("B") < order.index("C")

    def test_toposort_diamond(self, diamond_graph: DependencyGraph) -> None:
        order = diamond_graph.toposort()
        assert order.index("A") < order.index("B")
        assert order.index("A") < order.index("C")
        assert order.index("B") < order.index("D")
        assert order.index("C") < order.index("D")

    def test_toposort_raises_on_cycle(self, cyclic_graph: DependencyGraph) -> None:
        with pytest.raises(ValueError, match="cycles"):
            cyclic_graph.toposort()

    def test_version_conflicts(self) -> None:
        graph = DependencyGraph()
        graph.add_node(Dependency(name="pkg-a", version="1.0", ecosystem=Ecosystem.PIP))
        graph.add_node(Dependency(name="pkg-b", version="2.0", ecosystem=Ecosystem.PIP))
        graph.add_node(Dependency(name="pkg-c", version="1.0", ecosystem=Ecosystem.PIP))

        conflicts = graph.find_version_conflicts()
        # No conflicts - different packages
        assert len(conflicts) == 0

    def test_impact_score(self, diamond_graph: DependencyGraph) -> None:
        # D is depended on by B and C, which are depended on by A
        score_d = diamond_graph.impact_score("D")
        score_a = diamond_graph.impact_score("A")
        # D has higher impact than A (A has no dependents)
        assert score_d > score_a

    def test_repr(self, simple_graph: DependencyGraph) -> None:
        repr_str = repr(simple_graph)
        assert "3" in repr_str  # 3 nodes
        assert "2" in repr_str  # 2 edges

    def test_empty_graph(self) -> None:
        graph = DependencyGraph()
        assert graph.size == 0
        assert len(graph.edges) == 0
        assert graph.detect_cycles() == []
