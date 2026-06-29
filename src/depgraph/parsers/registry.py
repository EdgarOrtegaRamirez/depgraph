"""Parser registry for auto-detection."""

from __future__ import annotations

from pathlib import Path

from depgraph.models import Ecosystem
from depgraph.parsers.base import BaseParser
from depgraph.parsers.parsers import (
    CargoLockParser,
    GoSumParser,
    PyProjectParser,
    RequirementsParser,
)

# All available parsers
PARSERS: list[BaseParser] = [
    RequirementsParser(),
    PyProjectParser(),
    GoSumParser(),
    CargoLockParser(),
]


def detect_ecosystem(directory: Path) -> tuple[BaseParser, Path] | None:
    """Auto-detect the dependency ecosystem in a directory.

    Args:
        directory: Directory to scan for dependency files.

    Returns:
        Tuple of (parser, file_path) or None if not detected.
    """
    for parser in PARSERS:
        if parser.detect(directory):
            # Find the actual file
            file_path = _find_dep_file(directory, parser.ecosystem)
            if file_path:
                return parser, file_path
    return None


def get_parser_for_ecosystem(ecosystem: Ecosystem) -> BaseParser | None:
    """Get parser for a specific ecosystem.

    Args:
        ecosystem: Target ecosystem.

    Returns:
        Parser instance or None.
    """
    for parser in PARSERS:
        if parser.ecosystem == ecosystem:
            return parser
    return None


def _find_dep_file(directory: Path, ecosystem: Ecosystem) -> Path | None:
    """Find the dependency file for a given ecosystem."""
    candidates = {
        Ecosystem.PIP: [
            "requirements.txt",
            "requirements-base.txt",
            "requirements-dev.txt",
            "requirements-lock.txt",
            "pyproject.toml",
        ],
        Ecosystem.GO: ["go.sum"],
        Ecosystem.CARGO: ["Cargo.lock"],
    }

    for candidate in candidates.get(ecosystem, []):
        path = directory / candidate
        if path.exists():
            return path

    # For pip, check any requirements*.txt
    if ecosystem == Ecosystem.PIP:
        for f in directory.iterdir():
            if f.is_file() and f.name.startswith("requirements") and f.suffix == ".txt":
                return f

    return None
