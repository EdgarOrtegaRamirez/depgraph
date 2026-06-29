"""Data models for dependency graph analysis."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Ecosystem(str, Enum):
    """Supported package ecosystems."""

    PIP = "pip"
    NPM = "npm"
    YARN = "yarn"
    PNPM = "pnpm"
    GO = "go"
    CARGO = "cargo"


class Severity(str, Enum):
    """Issue severity levels."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


@dataclass
class Dependency:
    """A single dependency node in the graph."""

    name: str
    version: str
    ecosystem: Ecosystem
    is_direct: bool = True
    extras: list[str] = field(default_factory=list)
    source: str | None = None  # e.g. git URL

    @property
    def key(self) -> str:
        """Unique key for this dependency."""
        return f"{self.ecosystem.value}:{self.name}"


@dataclass
class Edge:
    """A dependency edge (from -> to)."""

    source: str  # dependency name
    target: str  # dependency name
    version_constraint: str = ""


@dataclass
class Cycle:
    """A detected circular dependency."""

    path: list[str]
    length: int

    @property
    def display(self) -> str:
        """Human-readable cycle path."""
        return " -> ".join(self.path)


@dataclass
class Issue:
    """A detected issue in the dependency graph."""

    severity: Severity
    category: str
    message: str
    dependency: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class HealthScore:
    """Dependency health assessment."""

    overall: float  # 0-100
    grade: str  # A+ to F
    breakdown: dict[str, float] = field(default_factory=dict)
    issues: list[Issue] = field(default_factory=list)

    @classmethod
    def from_score(cls, score: float, issues: list[Issue] | None = None) -> HealthScore:
        """Create health score from numeric value."""
        issues = issues or []
        if score >= 95:
            grade = "A+"
        elif score >= 90:
            grade = "A"
        elif score >= 85:
            grade = "B+"
        elif score >= 80:
            grade = "B"
        elif score >= 75:
            grade = "C+"
        elif score >= 70:
            grade = "C"
        elif score >= 60:
            grade = "D"
        else:
            grade = "F"

        return cls(overall=round(score, 1), grade=grade, issues=issues)


@dataclass
class GraphStats:
    """Statistics about the dependency graph."""

    total_packages: int = 0
    direct_dependencies: int = 0
    transitive_dependencies: int = 0
    max_depth: int = 0
    max_breadth: int = 0
    total_edges: int = 0
    ecosystem_counts: dict[str, int] = field(default_factory=dict)


@dataclass
class AnalysisResult:
    """Complete analysis result."""

    ecosystem: Ecosystem
    root_package: str | None = None
    stats: GraphStats = field(default_factory=GraphStats)
    health: HealthScore = field(default_factory=lambda: HealthScore.from_score(100))
    cycles: list[Cycle] = field(default_factory=list)
    issues: list[Issue] = field(default_factory=list)
    unused: list[str] = field(default_factory=list)
    version_conflicts: list[Issue] = field(default_factory=list)
