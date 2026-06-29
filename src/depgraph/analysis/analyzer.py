"""Main analyzer that orchestrates parsing, graph building, and analysis."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from depgraph.analysis.graph import DependencyGraph
from depgraph.analysis.health import HealthScorer
from depgraph.analysis.unused import find_unused
from depgraph.models import AnalysisResult, Ecosystem, GraphStats
from depgraph.parsers.registry import detect_ecosystem, get_parser_for_ecosystem

logger = logging.getLogger(__name__)


def analyze(
    directory: Path,
    ecosystem: Ecosystem | None = None,
    root_package: str | None = None,
    source_dirs: list[Path] | None = None,
    max_depth: int | None = None,
) -> AnalysisResult:
    """Run full dependency analysis on a directory.

    Args:
        directory: Directory containing dependency files.
        ecosystem: Force specific ecosystem (auto-detect if None).
        root_package: Override root package name.
        source_dirs: Directories to scan for unused detection.
        max_depth: Maximum tree depth for visualization.

    Returns:
        Complete analysis result.
    """
    directory = directory.resolve()

    # Detect or use specified ecosystem
    if ecosystem:
        parser = get_parser_for_ecosystem(ecosystem)
        if not parser:
            raise ValueError(f"No parser available for ecosystem: {ecosystem.value}")
        # Find the dependency file
        detected = detect_ecosystem(directory)
        if detected:
            _, dep_file = detected
        else:
            raise FileNotFoundError(f"No dependency file found for {ecosystem.value} in {directory}")
    else:
        result = detect_ecosystem(directory)
        if not result:
            raise FileNotFoundError(f"No recognized dependency file found in {directory}")
        parser, dep_file = result
        ecosystem = parser.ecosystem

    logger.info("Detected ecosystem: %s, file: %s", ecosystem.value, dep_file)

    # Parse dependencies
    deps, edges = parser.parse(dep_file, root_package)
    logger.info("Parsed %d dependencies, %d edges", len(deps), len(edges))

    # Build graph
    graph = DependencyGraph()
    for dep in deps:
        graph.add_node(dep)
    for edge in edges:
        graph.add_edge(edge)

    # Auto-detect root package if not provided
    if not root_package and deps:
        # Try to find root from dep_file name or directory
        root_package = _guess_root_package(directory, dep_file, ecosystem)

    # Calculate stats
    stats = GraphStats(
        total_packages=graph.size,
        direct_dependencies=len([d for d in deps if d.is_direct]),
        transitive_dependencies=graph.size - len([d for d in deps if d.is_direct]),
        total_edges=len(graph.edges),
    )

    if root_package and root_package in graph.nodes:
        stats.max_depth = graph.max_depth(root_package)
        stats.max_breadth = graph.max_breadth(root_package)

    # Health scoring
    scorer = HealthScorer(graph=graph, root=root_package)
    health = scorer.score()

    # Find unused dependencies
    unused: list[str] = []
    if source_dirs:
        unused = find_unused(deps, source_dirs, ecosystem)

    # Create result
    result = AnalysisResult(
        ecosystem=ecosystem,
        root_package=root_package,
        stats=stats,
        health=health,
        cycles=graph.detect_cycles(),
        issues=scorer.issues,
        unused=unused,
    )

    return result


def analyze_and_format(
    directory: Path,
    ecosystem: Ecosystem | None = None,
    root_package: str | None = None,
    source_dirs: list[Path] | None = None,
    output_format: str = "text",
    max_depth: int | None = None,
) -> str:
    """Run analysis and format output.

    Args:
        directory: Directory to analyze.
        ecosystem: Force ecosystem (auto-detect if None).
        root_package: Override root package name.
        source_dirs: Directories for unused detection.
        output_format: Output format (text, json, markdown).
        max_depth: Maximum tree depth.

    Returns:
        Formatted analysis string.
    """
    result = analyze(
        directory=directory,
        ecosystem=ecosystem,
        root_package=root_package,
        source_dirs=source_dirs,
        max_depth=max_depth,
    )

    if output_format == "json":
        return _format_json(result)
    elif output_format == "markdown":
        return _format_markdown(result)
    else:
        return _format_text(result, max_depth)


def _format_text(result: AnalysisResult, max_depth: int | None = None) -> str:
    """Format result as plain text."""
    lines: list[str] = []

    lines.append("=" * 60)
    lines.append(f"DepGraph Analysis — {result.ecosystem.value.upper()}")
    lines.append("=" * 60)

    if result.root_package:
        lines.append(f"\nRoot: {result.root_package}")

    # Stats
    lines.append("\n📊 Statistics:")
    lines.append(f"  Total packages: {result.stats.total_packages}")
    lines.append(f"  Direct dependencies: {result.stats.direct_dependencies}")
    lines.append(f"  Transitive dependencies: {result.stats.transitive_dependencies}")
    lines.append(f"  Total edges: {result.stats.total_edges}")
    if result.stats.max_depth:
        lines.append(f"  Max depth: {result.stats.max_depth}")
    if result.stats.max_breadth:
        lines.append(f"  Max breadth: {result.stats.max_breadth}")

    # Health
    lines.append(f"\n🏥 Health Score: {result.health.overall}/100 ({result.health.grade})")

    # Cycles
    if result.cycles:
        lines.append(f"\n🔄 Circular Dependencies: {len(result.cycles)}")
        for cycle in result.cycles:
            lines.append(f"  ⚠ {cycle.display}")

    # Issues
    if result.issues:
        lines.append(f"\n⚠ Issues: {len(result.issues)}")
        for issue in result.issues:
            icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🔵", "info": "⚪"}.get(
                issue.severity.value, "•"
            )
            lines.append(f"  {icon} [{issue.severity.value.upper()}] {issue.message}")

    # Unused
    if result.unused:
        lines.append(f"\n🧹 Unused Dependencies: {len(result.unused)}")
        for pkg in result.unused:
            lines.append(f"  • {pkg}")

    lines.append("")
    return "\n".join(lines)


def _format_json(result: AnalysisResult) -> str:
    """Format result as JSON."""
    data = {
        "ecosystem": result.ecosystem.value,
        "root_package": result.root_package,
        "stats": {
            "total_packages": result.stats.total_packages,
            "direct_dependencies": result.stats.direct_dependencies,
            "transitive_dependencies": result.stats.transitive_dependencies,
            "max_depth": result.stats.max_depth,
            "max_breadth": result.stats.max_breadth,
            "total_edges": result.stats.total_edges,
        },
        "health": {
            "score": result.health.overall,
            "grade": result.health.grade,
        },
        "cycles": [{"path": c.path, "length": c.length} for c in result.cycles],
        "issues": [
            {
                "severity": i.severity.value,
                "category": i.category,
                "message": i.message,
                "dependency": i.dependency,
            }
            for i in result.issues
        ],
        "unused": result.unused,
    }
    return json.dumps(data, indent=2)


def _format_markdown(result: AnalysisResult) -> str:
    """Format result as Markdown."""
    lines: list[str] = []

    lines.append(f"# DepGraph Analysis — {result.ecosystem.value.upper()}\n")

    if result.root_package:
        lines.append(f"**Root:** `{result.root_package}`\n")

    lines.append("## Statistics\n")
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append(f"| Total packages | {result.stats.total_packages} |")
    lines.append(f"| Direct dependencies | {result.stats.direct_dependencies} |")
    lines.append(f"| Transitive dependencies | {result.stats.transitive_dependencies} |")
    lines.append(f"| Max depth | {result.stats.max_depth} |")
    lines.append(f"| Max breadth | {result.stats.max_breadth} |")
    lines.append("")

    lines.append(f"## Health Score: {result.health.overall}/100 ({result.health.grade})\n")

    if result.cycles:
        lines.append(f"## 🔄 Circular Dependencies ({len(result.cycles)})\n")
        for cycle in result.cycles:
            lines.append(f"- `{cycle.display}`")
        lines.append("")

    if result.issues:
        lines.append(f"## ⚠ Issues ({len(result.issues)})\n")
        for issue in result.issues:
            lines.append(f"- **[{issue.severity.value.upper()}]** {issue.message}")
        lines.append("")

    if result.unused:
        lines.append(f"## 🧹 Unused Dependencies ({len(result.unused)})\n")
        for pkg in result.unused:
            lines.append(f"- `{pkg}`")
        lines.append("")

    return "\n".join(lines)


def _guess_root_package(directory: Path, dep_file: Path, ecosystem: Ecosystem) -> str | None:
    """Guess the root package name from directory/dep_file context."""
    if ecosystem == Ecosystem.PIP:
        # Try to read from pyproject.toml
        pyproject = directory / "pyproject.toml"
        if pyproject.exists():
            content = pyproject.read_text(encoding="utf-8")
            for line in content.splitlines():
                if line.strip().startswith("name"):
                    parts = line.split("=", 1)
                    if len(parts) == 2:
                        return parts[1].strip().strip('"').strip("'")
        # Try setup.py
        setup_py = directory / "setup.py"
        if setup_py.exists():
            content = setup_py.read_text(encoding="utf-8")
            for line in content.splitlines():
                if "name=" in line or "name =" in line:
                    import re

                    match = re.search(r'name=["\']([^"\']+)["\']', line)
                    if match:
                        return match.group(1)

    # Default to directory name
    return directory.name
