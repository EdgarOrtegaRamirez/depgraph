"""Dependency graph data structure and algorithms."""

from __future__ import annotations

from collections import defaultdict, deque

from depgraph.models import Cycle, Dependency, Ecosystem, Edge


class DependencyGraph:
    """Directed graph of dependencies with algorithm support.

    Uses adjacency list representation for efficient traversal.
    """

    def __init__(self) -> None:
        self._nodes: dict[str, Dependency] = {}
        self._adj: dict[str, list[str]] = defaultdict(list)
        self._reverse_adj: dict[str, list[str]] = defaultdict(list)
        self._edges: list[Edge] = []

    def add_node(self, dep: Dependency) -> None:
        """Add a dependency node."""
        self._nodes[dep.name] = dep

    def add_edge(self, edge: Edge) -> None:
        """Add a dependency edge (source depends on target)."""
        self._adj[edge.source].append(edge.target)
        self._reverse_adj[edge.target].append(edge.source)
        self._edges.append(edge)

        # Ensure both nodes exist
        if edge.source not in self._nodes:
            target_dep = self._nodes.get(edge.target)
            eco = target_dep.ecosystem if target_dep else Ecosystem.PIP
            self._nodes[edge.source] = Dependency(name=edge.source, version="*", ecosystem=eco)

    @property
    def nodes(self) -> dict[str, Dependency]:
        """All nodes in the graph."""
        return dict(self._nodes)

    @property
    def edges(self) -> list[Edge]:
        """All edges in the graph."""
        return list(self._edges)

    @property
    def size(self) -> int:
        """Number of nodes."""
        return len(self._nodes)

    def successors(self, node: str) -> list[str]:
        """Get nodes that `node` depends on."""
        return list(self._adj.get(node, []))

    def predecessors(self, node: str) -> list[str]:
        """Get nodes that depend on `node`."""
        return list(self._reverse_adj.get(node, []))

    def detect_cycles(self) -> list[Cycle]:
        """Detect all cycles in the graph using DFS.

        Returns:
            List of detected cycles.
        """
        cycles: list[Cycle] = []
        visited: set[str] = set()
        rec_stack: list[str] = []

        def _dfs(node: str) -> None:
            visited.add(node)
            rec_stack.append(node)

            for neighbor in self._adj.get(node, []):
                if neighbor not in visited:
                    _dfs(neighbor)
                elif neighbor in rec_stack:
                    # Found a cycle
                    cycle_start = rec_stack.index(neighbor)
                    cycle_path = rec_stack[cycle_start:] + [neighbor]
                    cycles.append(Cycle(path=cycle_path, length=len(cycle_path) - 1))

            rec_stack.pop()

        for node in self._nodes:
            if node not in visited:
                _dfs(node)

        return cycles

    def bfs_depth(self, root: str) -> dict[str, int]:
        """Calculate BFS depth from root node.

        Returns:
            Dictionary mapping node names to their depth from root.
        """
        depths: dict[str, int] = {root: 0}
        queue: deque[str] = deque([root])

        while queue:
            current = queue.popleft()
            current_depth = depths[current]

            for neighbor in self._adj.get(current, []):
                if neighbor not in depths:
                    depths[neighbor] = current_depth + 1
                    queue.append(neighbor)

        return depths

    def max_depth(self, root: str) -> int:
        """Calculate maximum dependency depth from root."""
        depths = self.bfs_depth(root)
        return max(depths.values()) if depths else 0

    def max_breadth(self, root: str) -> int:
        """Calculate maximum dependency breadth at any level."""
        depths = self.bfs_depth(root)
        if not depths:
            return 0

        level_counts: dict[int, int] = defaultdict(int)
        for depth in depths.values():
            level_counts[depth] += 1

        return max(level_counts.values()) if level_counts else 0

    def reachable_from(self, node: str) -> set[str]:
        """Get all nodes reachable from the given node via BFS."""
        reachable: set[str] = set()
        queue: deque[str] = deque([node])

        while queue:
            current = queue.popleft()
            for neighbor in self._adj.get(current, []):
                if neighbor not in reachable:
                    reachable.add(neighbor)
                    queue.append(neighbor)

        return reachable

    def find_orphans(self, roots: list[str]) -> list[str]:
        """Find nodes not reachable from any root.

        Args:
            roots: Root package names.

        Returns:
            List of unreachable node names.
        """
        reachable: set[str] = set()
        for root in roots:
            reachable |= self.reachable_from(root)
            reachable.add(root)

        return [node for node in self._nodes if node not in reachable]

    def find_version_conflicts(self) -> list[dict[str, object]]:
        """Find packages with multiple versions installed.

        Returns:
            List of conflict descriptions.
        """
        # Group by package name (ignoring ecosystem prefix)
        name_versions: dict[str, set[str]] = defaultdict(set)
        for name, dep in self._nodes.items():
            # Strip ecosystem prefix if present
            clean_name = name.split(":", 1)[-1] if ":" in name else name
            name_versions[clean_name].add(dep.version)

        conflicts = []
        for name, versions in name_versions.items():
            if len(versions) > 1:
                conflicts.append(
                    {
                        "package": name,
                        "versions": sorted(versions),
                        "count": len(versions),
                    }
                )

        return conflicts

    def toposort(self) -> list[str]:
        """Topological sort of the graph (Kahn's algorithm).

        Returns:
            List of nodes in dependency order.

        Raises:
            ValueError: If the graph has cycles.
        """
        in_degree: dict[str, int] = defaultdict(int)
        for node in self._nodes:
            in_degree[node] = 0

        for _source, targets in self._adj.items():
            for target in targets:
                in_degree[target] += 1

        queue: deque[str] = deque()
        for node, degree in in_degree.items():
            if degree == 0:
                queue.append(node)

        result: list[str] = []
        while queue:
            node = queue.popleft()
            result.append(node)

            for neighbor in self._adj.get(node, []):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(result) != len(self._nodes):
            raise ValueError("Graph contains cycles — topological sort impossible")

        return result

    def impact_score(self, node: str) -> int:
        """Calculate the impact score for a node (0-100).

        Higher score = more packages depend on this node (higher blast radius).

        Algorithm:
        - Count direct dependents (predecessors)
        - Count transitive dependents
        - Weight by depth from the node
        """
        predecessors = self.predecessors(node)
        direct_count = len(predecessors)

        # BFS from node in reverse direction
        transitive_count = 0
        visited: set[str] = set()
        queue: deque[str] = deque(predecessors)

        while queue:
            current = queue.popleft()
            if current in visited:
                continue
            visited.add(current)
            transitive_count += 1

            for pred in self.predecessors(current):
                if pred not in visited:
                    queue.append(pred)

        # Score: 40% direct, 60% transitive
        total = direct_count * 2 + transitive_count
        score = min(100, int(total * 5))

        return score

    def __repr__(self) -> str:
        return f"DependencyGraph(nodes={self.size}, edges={len(self._edges)})"
