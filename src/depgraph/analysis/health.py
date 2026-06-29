"""Health scoring for dependency graphs."""

from __future__ import annotations

from dataclasses import dataclass, field

from depgraph.analysis.graph import DependencyGraph
from depgraph.models import HealthScore, Issue, Severity


@dataclass
class HealthScorer:
    """Scores dependency graph health (0-100).

    Factors:
    - Cycle presence (0-25 points deducted)
    - Dependency depth (0-20 points deducted)
    - Dependency count (0-15 points deducted)
    - Version conflicts (0-20 points deducted)
    - Orphaned packages (0-10 points deducted)
    - Broad dependency tree (0-10 points deducted)
    """

    graph: DependencyGraph
    root: str | None = None
    issues: list[Issue] = field(default_factory=list)

    # Tunable thresholds
    max_ideal_depth: int = 5
    max_ideal_direct: int = 20
    max_ideal_total: int = 100

    def score(self) -> HealthScore:
        """Calculate the overall health score."""
        base_score = 100.0
        breakdown: dict[str, float] = {}

        # 1. Cycle detection (most critical)
        cycles = self.graph.detect_cycles()
        cycle_deduction = min(25, len(cycles) * 10)
        if cycles:
            breakdown["cycles"] = -cycle_deduction
            base_score -= cycle_deduction
            for cycle in cycles:
                self.issues.append(
                    Issue(
                        severity=Severity.CRITICAL if cycle.length <= 2 else Severity.HIGH,
                        category="cycle",
                        message=f"Circular dependency detected: {cycle.display}",
                        details={"cycle_length": cycle.length, "path": cycle.path},
                    )
                )
        else:
            breakdown["cycles"] = 0

        # 2. Dependency depth
        if self.root and self.root in self.graph.nodes:
            depth = self.graph.max_depth(self.root)
            depth_deduction = max(0, (depth - self.max_ideal_depth) * 4)
            depth_deduction = min(20, depth_deduction)
            breakdown["depth"] = -depth_deduction
            base_score -= depth_deduction

            if depth > self.max_ideal_depth + 5:
                self.issues.append(
                    Issue(
                        severity=Severity.MEDIUM,
                        category="depth",
                        message=f"Deep dependency chain ({depth} levels) — may indicate unnecessary complexity",
                        details={"depth": depth},
                    )
                )

        # 3. Total dependency count
        total = self.graph.size
        count_deduction = max(0, (total - self.max_ideal_total) * 0.1)
        count_deduction = min(15, count_deduction)
        breakdown["count"] = -count_deduction
        base_score -= count_deduction

        if total > self.max_ideal_total * 2:
            self.issues.append(
                Issue(
                    severity=Severity.LOW,
                    category="count",
                    message=f"Large dependency tree ({total} packages) — review for bloat",
                    details={"total": total},
                )
            )

        # 4. Version conflicts
        conflicts = self.graph.find_version_conflicts()
        conflict_deduction = min(20, len(conflicts) * 5)
        breakdown["conflicts"] = -conflict_deduction
        base_score -= conflict_deduction

        for conflict in conflicts:
            pkg_name = conflict["package"]
            ver_count = conflict["count"]
            ver_list = ", ".join(conflict["versions"])
            self.issues.append(
                Issue(
                    severity=Severity.MEDIUM if ver_count <= 2 else Severity.HIGH,
                    category="version_conflict",
                    message=f"Version conflict: {pkg_name} has {ver_count} versions: {ver_list}",
                    dependency=pkg_name,
                    details=conflict,
                )
            )

        # 5. Orphaned packages (not reachable from root)
        if self.root:
            orphans = self.graph.find_orphans([self.root])
            orphan_deduction = min(10, len(orphans) * 2)
            breakdown["orphans"] = -orphan_deduction
            base_score -= orphan_deduction

            if orphans:
                self.issues.append(
                    Issue(
                        severity=Severity.LOW,
                        category="orphans",
                        message=f"{len(orphans)} orphaned packages not reachable from root",
                        details={"orphans": orphans[:10]},  # Limit display
                    )
                )

        # 6. Breadth at max depth
        if self.root and self.root in self.graph.nodes:
            breadth = self.graph.max_breadth(self.root)
            breadth_deduction = max(0, (breadth - 20) * 0.5)
            breadth_deduction = min(10, breadth_deduction)
            breakdown["breadth"] = -breadth_deduction
            base_score -= breadth_deduction

        final_score = max(0, base_score)

        return HealthScore.from_score(final_score, self.issues)
