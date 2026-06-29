"""Parser for Python pip requirements files."""

from __future__ import annotations

import re
from pathlib import Path

from depgraph.models import Dependency, Ecosystem, Edge
from depgraph.parsers.base import BaseParser


class RequirementsParser(BaseParser):
    """Parser for requirements.txt files."""

    ecosystem = Ecosystem.PIP

    # Pattern: package[extras]>=version,<version
    REQ_PATTERN = re.compile(
        r"^(?P<name>[A-Za-z0-9][A-Za-z0-9._-]*)"
        r"(?:\[(?P<extras>[^\]]+)\])?"
        r"(?:\s*(?P<op>[=!<>~]+)\s*(?P<version>[^\s,;]+))?"
        r"(?:\s*[;].*)?"
        r"(?:\s*#.*)?$"
    )

    # Directives to skip
    SKIP_PREFIXES = ("#", "-", "http://", "https://", "git+", "file://", ".")

    def parse(self, file_path: Path, root_package: str | None = None) -> tuple[list[Dependency], list[Edge]]:
        deps: list[Dependency] = []
        edges: list[Edge] = []

        if not file_path.exists():
            return deps, edges

        content = file_path.read_text(encoding="utf-8")
        for line in content.splitlines():
            line = line.strip()
            if not line or any(line.startswith(p) for p in self.SKIP_PREFIXES):
                continue

            match = self.REQ_PATTERN.match(line)
            if not match:
                continue

            name = self._clean_package_name(match.group("name"))
            version = self._clean_version(match.group("version") or "")
            extras = [e.strip() for e in (match.group("extras") or "").split(",") if e.strip()]

            dep = Dependency(
                name=name,
                version=version or "*",
                ecosystem=Ecosystem.PIP,
                is_direct=True,
                extras=extras,
            )
            deps.append(dep)

            if root_package:
                edges.append(Edge(source=root_package, target=name, version_constraint=version or "*"))

        return deps, edges

    def detect(self, directory: Path) -> bool:
        """Detect requirements*.txt files."""
        for f in directory.iterdir():
            if f.is_file() and f.name.startswith("requirements") and f.suffix == ".txt":
                return True
        return False


class PyProjectParser(BaseParser):
    """Parser for pyproject.toml files (PEP 621 dependencies)."""

    ecosystem = Ecosystem.PIP

    # Fields to skip (metadata, not dependencies)
    META_FIELDS = frozenset({
        "name", "version", "description", "readme", "license", "requires-python",
        "authors", "maintainers", "keywords", "classifiers", "urls",
        "optional-dependencies", "project", "build-system", "tool", "scripts",
        "entry-points", "gui-scripts", "console-scripts", "dynamic",
    })

    def parse(self, file_path: Path, root_package: str | None = None) -> tuple[list[Dependency], list[Edge]]:
        deps: list[Dependency] = []
        edges: list[Edge] = []

        if not file_path.exists():
            return deps, edges

        content = file_path.read_text(encoding="utf-8")
        in_deps_array = False
        bracket_depth = 0

        for line in content.splitlines():
            stripped = line.strip()

            # Detect start of dependencies array (handles multi-line and single-line)
            if not in_deps_array and re.match(r'^dependencies\s*=\s*\[', stripped):
                in_deps_array = True
                bracket_depth = stripped.count("[") - stripped.count("]")

                # Single-line array: dependencies = ["a", "b"]
                if bracket_depth <= 0:
                    in_deps_array = False
                    self._parse_inline_deps(stripped, deps, edges, root_package)
                continue

            # Inside a multi-line dependencies array
            if in_deps_array:
                bracket_depth += stripped.count("[") - stripped.count("]")

                # Try to extract dependency from this line
                dep_str = self._extract_dep_string(stripped)
                if dep_str:
                    # Strip version constraint from extracted name
                    for op in (">=", "<=", "==", "!=", "~=", "~"):
                        dep_str = dep_str.split(op)[0]
                    name = self._clean_package_name(dep_str)
                    if name and name not in self.META_FIELDS:
                        dep = Dependency(
                            name=name,
                            version="*",
                            ecosystem=Ecosystem.PIP,
                            is_direct=True,
                        )
                        deps.append(dep)
                        if root_package:
                            edges.append(Edge(source=root_package, target=name, version_constraint="*"))

                # Check if array is closed
                if bracket_depth <= 0:
                    in_deps_array = False
                    bracket_depth = 0

        return deps, edges

    def _extract_dep_string(self, line: str) -> str | None:
        """Extract a dependency string from a line (handles quoted strings)."""
        # Remove trailing comma
        line = line.rstrip(",").strip()
        # Remove quotes
        if (line.startswith('"') and line.endswith('"')) or (line.startswith("'") and line.endswith("'")):
            line = line[1:-1]
        # Remove comments
        if "#" in line:
            line = line[:line.index("#")].strip()
        # Must look like a package name
        if re.match(r"^[A-Za-z0-9]", line):
            # Strip version constraint
            for op in (">=", "<=", "==", "!=", "~=", "~"):
                line = line.split(op)[0]
            name = self._clean_package_name(line)
            if name and name not in self.META_FIELDS:
                return name
        return None

    def _parse_inline_deps(
        self, line: str, deps: list[Dependency], edges: list[Edge], root_package: str | None
    ) -> None:
        """Parse a single-line dependencies array."""
        match = re.search(r'dependencies\s*=\s*\[(.+)\]', line)
        if not match:
            return

        content = match.group(1)
        for dep_match in re.finditer(r"""["']([A-Za-z0-9][A-Za-z0-9._-]*)""", content):
            name = self._clean_package_name(dep_match.group(1))
            if name and name not in self.META_FIELDS:
                dep = Dependency(
                    name=name,
                    version="*",
                    ecosystem=Ecosystem.PIP,
                    is_direct=True,
                )
                deps.append(dep)
                if root_package:
                    edges.append(Edge(source=root_package, target=name, version_constraint="*"))

    def detect(self, directory: Path) -> bool:
        """Detect pyproject.toml files."""
        return (directory / "pyproject.toml").exists()


class GoSumParser(BaseParser):
    """Parser for Go go.sum files."""

    ecosystem = Ecosystem.GO

    # go.sum format: module version h1:hash
    LINE_PATTERN = re.compile(r"^(\S+)\s+(v[\d.]+\S*)\s+(\S+)$")

    def parse(self, file_path: Path, root_package: str | None = None) -> tuple[list[Dependency], list[Edge]]:
        deps: list[Dependency] = []
        edges: list[Edge] = []
        seen: set[str] = set()

        if not file_path.exists():
            return deps, edges

        content = file_path.read_text(encoding="utf-8")
        for line in content.splitlines():
            match = self.LINE_PATTERN.match(line.strip())
            if not match:
                continue

            name = match.group(1)
            version = match.group(2)

            # Skip module itself
            if name == root_package:
                continue

            if name not in seen:
                seen.add(name)
                dep = Dependency(
                    name=name,
                    version=version,
                    ecosystem=Ecosystem.GO,
                    is_direct=True,
                )
                deps.append(dep)

                if root_package:
                    edges.append(Edge(source=root_package, target=name, version_constraint=version))

        return deps, edges

    def detect(self, directory: Path) -> bool:
        """Detect go.sum files."""
        return (directory / "go.sum").exists()


class CargoLockParser(BaseParser):
    """Parser for Rust Cargo.lock files."""

    ecosystem = Ecosystem.CARGO

    def parse(self, file_path: Path, root_package: str | None = None) -> tuple[list[Dependency], list[Edge]]:
        deps: list[Dependency] = []
        edges: list[Edge] = []

        if not file_path.exists():
            return deps, edges

        content = file_path.read_text(encoding="utf-8")
        current_name = ""
        current_version = ""

        for line in content.splitlines():
            stripped = line.strip()

            if stripped.startswith("name = "):
                current_name = stripped.split("=", 1)[1].strip().strip('"')
            elif stripped.startswith("version = "):
                current_version = stripped.split("=", 1)[1].strip().strip('"')

            # End of package block
            if stripped == "" and current_name and current_version:
                if current_name != root_package:
                    dep = Dependency(
                        name=current_name,
                        version=current_version,
                        ecosystem=Ecosystem.CARGO,
                        is_direct=True,
                    )
                    deps.append(dep)

                    if root_package:
                        edges.append(Edge(source=root_package, target=current_name, version_constraint=current_version))

                current_name = ""
                current_version = ""

        # Handle last entry (no trailing newline)
        if current_name and current_version and current_name != root_package:
            dep = Dependency(
                name=current_name,
                version=current_version,
                ecosystem=Ecosystem.CARGO,
                is_direct=True,
            )
            deps.append(dep)

            if root_package:
                edges.append(Edge(source=root_package, target=current_name, version_constraint=current_version))

        return deps, edges

    def detect(self, directory: Path) -> bool:
        """Detect Cargo.lock files."""
        return (directory / "Cargo.lock").exists()
