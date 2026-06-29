"""Base parser interface for dependency files."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from depgraph.models import Dependency, Ecosystem, Edge


class BaseParser(ABC):
    """Abstract base class for dependency file parsers."""

    ecosystem: Ecosystem

    @abstractmethod
    def parse(self, file_path: Path, root_package: str | None = None) -> tuple[list[Dependency], list[Edge]]:
        """Parse a dependency file and return dependencies and edges.

        Args:
            file_path: Path to the dependency file.
            root_package: Optional root package name.

        Returns:
            Tuple of (dependencies, edges).
        """

    @abstractmethod
    def detect(self, directory: Path) -> bool:
        """Detect if this parser can handle the given directory.

        Args:
            directory: Directory to check for dependency files.

        Returns:
            True if the directory contains a recognizable dependency file.
        """

    @staticmethod
    def _clean_version(version: str) -> str:
        """Clean and normalize a version string."""
        version = version.strip()
        # Remove common prefixes
        for prefix in ("v", "V", "==", ">=", "<=", "~=", "!=", "~"):
            if version.startswith(prefix):
                version = version[len(prefix) :]
        return version.strip()

    @staticmethod
    def _clean_package_name(name: str) -> str:
        """Clean and normalize a package name."""
        return name.strip().lower().replace("_", "-")
