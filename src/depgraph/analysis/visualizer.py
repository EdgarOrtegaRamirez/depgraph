"""ASCII graph visualizer for dependency trees."""

from __future__ import annotations

from depgraph.analysis.graph import DependencyGraph


def visualize_tree(graph: DependencyGraph, root: str, max_depth: int | None = None) -> str:
    """Generate ASCII tree visualization of dependencies.

    Args:
        graph: The dependency graph.
        root: Root package name.
        max_depth: Maximum depth to display (None = unlimited).

    Returns:
        ASCII tree string.
    """
    if root not in graph.nodes:
        return f"Root '{root}' not found in graph"

    lines: list[str] = []
    visited: set[str] = set()

    def _build_tree(node: str, prefix: str, depth: int) -> None:
        if max_depth is not None and depth > max_depth:
            return

        dep = graph.nodes.get(node)
        version = dep.version if dep else "?"

        if node in visited:
            lines.append(f"{prefix}├── {node}@{version} (cycle)")
            return

        visited.add(node)
        children = graph.successors(node)

        if not children:
            lines.append(f"{prefix}└── {node}@{version} ({len(graph.predecessors(node))} dependents)")
        else:
            lines.append(f"{prefix}├── {node}@{version} ({len(children)} deps)")
            for i, child in enumerate(children):
                is_last = i == len(children) - 1
                connector = "└── " if is_last else "├── "
                child_prefix = prefix + ("    " if is_last else "│   ")

                if child in visited:
                    lines.append(f"{child_prefix}{connector}{child} → (seen above)")
                else:
                    _build_tree(child, child_prefix, depth + 1)

    lines.append(f"📦 {root}@{graph.nodes[root].version}")
    visited.add(root)

    children = graph.successors(root)
    for _i, child in enumerate(children):
        _build_tree(child, "", 1)

    return "\n".join(lines)


def visualize_flat(graph: DependencyGraph, root: str) -> str:
    """Generate flat dependency list with depth indicators.

    Args:
        graph: The dependency graph.
        root: Root package name.

    Returns:
        Flat dependency list string.
    """
    if root not in graph.nodes:
        return f"Root '{root}' not found in graph"

    depths = graph.bfs_depth(root)
    lines: list[str] = []

    # Sort by depth
    sorted_nodes = sorted(depths.items(), key=lambda x: (x[1], x[0]))

    for node, depth in sorted_nodes:
        dep = graph.nodes.get(node)
        version = dep.version if dep else "?"
        indent = "  " * depth
        markers = []
        if depth == 0:
            markers.append("ROOT")
        if not graph.successors(node):
            markers.append("leaf")
        deps_count = len(graph.successors(node))
        marker_str = f" [{', '.join(markers)}]" if markers else ""
        lines.append(f"{indent}{node}@{version} ({deps_count} deps){marker_str}")

    return "\n".join(lines)


def visualize_stats(graph: DependencyGraph, root: str | None = None) -> str:
    """Generate statistics summary.

    Args:
        graph: The dependency graph.
        root: Optional root package for depth stats.

    Returns:
        Statistics string.
    """
    lines: list[str] = []
    lines.append(f"Total packages: {graph.size}")
    lines.append(f"Total edges: {len(graph.edges)}")

    if root and root in graph.nodes:
        depths = graph.bfs_depth(root)
        max_d = max(depths.values()) if depths else 0
        lines.append(f"Max depth from '{root}': {max_d}")
        lines.append(f"Reachable from '{root}': {len(depths)}")

        orphans = graph.find_orphans([root])
        if orphans:
            lines.append(f"Orphaned packages: {len(orphans)}")

    # Ecosystem breakdown
    ecosystems: dict[str, int] = {}
    for dep in graph.nodes.values():
        eco = dep.ecosystem.value
        ecosystems[eco] = ecosystems.get(eco, 0) + 1
    if ecosystems:
        lines.append("By ecosystem:")
        for eco, count in sorted(ecosystems.items()):
            lines.append(f"  {eco}: {count}")

    # Version conflicts
    conflicts = graph.find_version_conflicts()
    if conflicts:
        lines.append(f"\n⚠ Version conflicts: {len(conflicts)}")
        for c in conflicts[:5]:
            lines.append(f"  {c['package']}: {', '.join(c['versions'])}")

    # Top dependents (most depended-on)
    dep_counts: dict[str, int] = {}
    for edge in graph.edges:
        dep_counts[edge.target] = dep_counts.get(edge.target, 0) + 1
    if dep_counts:
        lines.append("\nMost depended-on:")
        for name, count in sorted(dep_counts.items(), key=lambda x: -x[1])[:10]:
            lines.append(f"  {name}: {count} dependents")

    return "\n".join(lines)
