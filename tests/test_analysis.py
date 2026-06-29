"""Tests for health scoring and unused detection."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from depgraph.analysis.graph import DependencyGraph
from depgraph.analysis.health import HealthScorer
from depgraph.analysis.unused import find_unused, get_import_coverage
from depgraph.models import Dependency, Ecosystem, Edge, Severity


@pytest.fixture
def healthy_graph() -> DependencyGraph:
    """Create a healthy dependency graph (no cycles)."""
    graph = DependencyGraph()
    graph.add_node(Dependency(name="A", version="1.0", ecosystem=Ecosystem.PIP))
    graph.add_node(Dependency(name="B", version="2.0", ecosystem=Ecosystem.PIP))
    graph.add_node(Dependency(name="C", version="3.0", ecosystem=Ecosystem.PIP))
    graph.add_edge(Edge(source="A", target="B"))
    graph.add_edge(Edge(source="A", target="C"))
    return graph


@pytest.fixture
def unhealthy_graph() -> DependencyGraph:
    """Create an unhealthy dependency graph (with cycles)."""
    graph = DependencyGraph()
    graph.add_node(Dependency(name="A", version="1.0", ecosystem=Ecosystem.PIP))
    graph.add_node(Dependency(name="B", version="2.0", ecosystem=Ecosystem.PIP))
    graph.add_node(Dependency(name="C", version="3.0", ecosystem=Ecosystem.PIP))
    graph.add_edge(Edge(source="A", target="B"))
    graph.add_edge(Edge(source="B", target="C"))
    graph.add_edge(Edge(source="C", target="A"))
    return graph


@pytest.fixture
def tmp_dir() -> Path:
    """Create a temporary directory."""
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


class TestHealthScorer:
    """Test the HealthScorer class."""

    def test_healthy_graph(self, healthy_graph: DependencyGraph) -> None:
        scorer = HealthScorer(graph=healthy_graph, root="A")
        health = scorer.score()

        assert health.overall == 100.0
        assert health.grade == "A+"
        assert len(health.issues) == 0

    def test_graph_with_cycles(self, unhealthy_graph: DependencyGraph) -> None:
        scorer = HealthScorer(graph=unhealthy_graph, root="A")
        health = scorer.score()

        assert health.overall < 100.0
        assert health.grade != "A+"
        assert len(health.issues) > 0

        # Check that cycle issue exists
        cycle_issues = [i for i in health.issues if i.category == "cycle"]
        assert len(cycle_issues) > 0
        assert cycle_issues[0].severity == Severity.HIGH

    def test_deep_graph(self) -> None:
        graph = DependencyGraph()
        # Create a deep chain: A -> B -> C -> ... -> N (15 nodes)
        for i in range(15):
            graph.add_node(Dependency(name=chr(65 + i), version="1.0", ecosystem=Ecosystem.PIP))
        for i in range(14):
            graph.add_edge(Edge(source=chr(65 + i), target=chr(66 + i)))

        scorer = HealthScorer(graph=graph, root="A")
        health = scorer.score()

        assert health.overall < 100.0
        depth_issues = [i for i in health.issues if i.category == "depth"]
        assert len(depth_issues) > 0

    def test_empty_graph(self) -> None:
        graph = DependencyGraph()
        scorer = HealthScorer(graph=graph)
        health = scorer.score()

        assert health.overall == 100.0
        assert health.grade == "A+"

    def test_health_score_grades(self) -> None:
        from depgraph.models import HealthScore
        # Test grade boundaries
        assert HealthScore.from_score(95).grade == "A+"
        assert HealthScore.from_score(90).grade == "A"
        assert HealthScore.from_score(85).grade == "B+"
        assert HealthScore.from_score(80).grade == "B"
        assert HealthScore.from_score(75).grade == "C+"
        assert HealthScore.from_score(70).grade == "C"
        assert HealthScore.from_score(60).grade == "D"
        assert HealthScore.from_score(50).grade == "F"


class TestUnusedDetection:
    """Test unused dependency detection."""

    def test_all_used(self, tmp_dir: Path) -> None:
        src_dir = tmp_dir / "src"
        src_dir.mkdir()
        (src_dir / "app.py").write_text("import requests\nimport flask\n")

        deps = [
            Dependency(name="requests", version="1.0", ecosystem=Ecosystem.PIP),
            Dependency(name="flask", version="2.0", ecosystem=Ecosystem.PIP),
        ]

        unused = find_unused(deps, [src_dir], Ecosystem.PIP)
        assert len(unused) == 0

    def test_some_unused(self, tmp_dir: Path) -> None:
        src_dir = tmp_dir / "src"
        src_dir.mkdir()
        (src_dir / "app.py").write_text("import requests\n")

        deps = [
            Dependency(name="requests", version="1.0", ecosystem=Ecosystem.PIP),
            Dependency(name="flask", version="2.0", ecosystem=Ecosystem.PIP),
            Dependency(name="sqlalchemy", version="3.0", ecosystem=Ecosystem.PIP),
        ]

        unused = find_unused(deps, [src_dir], Ecosystem.PIP)
        assert "flask" in unused
        assert "sqlalchemy" in unused
        assert "requests" not in unused

    def test_import_coverage(self, tmp_dir: Path) -> None:
        src_dir = tmp_dir / "src"
        src_dir.mkdir()
        (src_dir / "app.py").write_text("import requests\nimport flask\n")

        deps = [
            Dependency(name="requests", version="1.0", ecosystem=Ecosystem.PIP),
            Dependency(name="flask", version="2.0", ecosystem=Ecosystem.PIP),
            Dependency(name="unused", version="1.0", ecosystem=Ecosystem.PIP),
        ]

        coverage = get_import_coverage(deps, [src_dir], Ecosystem.PIP)
        assert coverage["total"] == 3
        assert coverage["used"] == 2
        assert coverage["unused"] == 1
        assert coverage["coverage"] == pytest.approx(66.67, abs=0.1)

    def test_missing_source_dir(self, tmp_dir: Path) -> None:
        deps = [
            Dependency(name="requests", version="1.0", ecosystem=Ecosystem.PIP),
        ]

        unused = find_unused(deps, [tmp_dir / "nonexistent"], Ecosystem.PIP)
        # All deps are considered unused when no source is found
        assert "requests" in unused

    def test_handles_syntax_errors(self, tmp_dir: Path) -> None:
        src_dir = tmp_dir / "src"
        src_dir.mkdir()
        (src_dir / "bad.py").write_text("def (\nimport requests\n")

        deps = [
            Dependency(name="requests", version="1.0", ecosystem=Ecosystem.PIP),
        ]

        # Should not crash
        unused = find_unused(deps, [src_dir], Ecosystem.PIP)
        assert isinstance(unused, list)

    def test_package_name_mapping(self, tmp_dir: Path) -> None:
        """Test that known package name mappings work."""
        src_dir = tmp_dir / "src"
        src_dir.mkdir()
        (src_dir / "app.py").write_text("from bs4 import BeautifulSoup\n")

        deps = [
            Dependency(name="beautifulsoup4", version="4.0", ecosystem=Ecosystem.PIP),
        ]

        unused = find_unused(deps, [src_dir], Ecosystem.PIP)
        assert "beautifulsoup4" not in unused
