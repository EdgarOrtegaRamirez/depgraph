"""Unused dependency detection via import analysis."""

from __future__ import annotations

import ast
import re
from pathlib import Path

from depgraph.models import Dependency, Ecosystem

# Mapping of PyPI package names to their import names
# (many packages have different install vs import names)
PYPI_TO_IMPORT: dict[str, list[str]] = {
    "pillow": ["PIL"],
    "beautifulsoup4": ["bs4"],
    "scikit-learn": ["sklearn"],
    "pyyaml": ["yaml"],
    "python-dateutil": ["dateutil"],
    "opencv-python": ["cv2"],
    "pymupdf": ["fitz"],
    "attrs": ["attr"],
    "python-dotenv": ["dotenv"],
    "google-auth": ["google", "google.auth"],
    "pyjwt": ["jwt"],
    "python-multipart": ["multipart"],
    "aiohttp": ["aiohttp"],
    "click": ["click"],
    "rich": ["rich"],
    "typer": ["typer"],
    "fastapi": ["fastapi"],
    "flask": ["flask"],
    "django": ["django"],
    "sqlalchemy": ["sqlalchemy"],
    "celery": ["celery"],
    "redis": ["redis"],
    "httpx": ["httpx"],
    "requests": ["requests"],
    "urllib3": ["urllib3"],
    "certifi": ["certifi"],
    "charset-normalizer": ["charset_normalizer"],
    "idna": ["idna"],
    "filelock": ["filelock"],
    "packaging": ["packaging"],
    "pluggy": ["pluggy"],
    "pygments": ["pygments"],
    "tomlkit": ["tomlkit"],
    "pydantic": ["pydantic"],
    "starlette": ["starlette"],
    "anyio": ["anyio"],
    "sniffio": ["sniffio"],
}


def _package_to_import_names(dep: Dependency) -> list[str]:
    """Map a package name to likely import names."""
    name = dep.name.lower()

    # Check known mappings
    if name in PYPI_TO_IMPORT:
        return PYPI_TO_IMPORT[name]

    # Default: replace hyphens with underscores
    import_name = name.replace("-", "_")
    return [import_name]


def _extract_imports_from_file(file_path: Path) -> set[str]:
    """Extract all import names from a Python file using AST."""
    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(content, filename=str(file_path))
    except (SyntaxError, UnicodeDecodeError):
        return set()

    imports: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module.split(".")[0])

    return imports


def _extract_imports_from_js(file_path: Path) -> set[str]:
    """Extract import names from JavaScript/TypeScript files via regex."""
    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return set()

    imports: set[str] = set()

    # ES module imports
    for match in re.finditer(r"""(?:import|from)\s+['"]([^'"]+)['"]""", content):
        imp = match.group(1)
        if imp.startswith("."):
            continue  # Skip relative imports
        # Extract package name (scope or simple)
        if imp.startswith("@"):
            parts = imp.split("/")
            imports.add(f"{parts[0]}/{parts[1]}" if len(parts) > 1 else parts[0])
        else:
            imports.add(imp.split("/")[0])

    # require() calls
    for match in re.finditer(r"""require\(['"]([^'"]+)['"]\)""", content):
        imp = match.group(1)
        if imp.startswith("."):
            continue
        if imp.startswith("@"):
            parts = imp.split("/")
            imports.add(f"{parts[0]}/{parts[1]}" if len(parts) > 1 else parts[0])
        else:
            imports.add(imp.split("/")[0])

    return imports


def _extract_imports_from_go(file_path: Path) -> set[str]:
    """Extract import paths from Go files."""
    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return set()

    imports: set[str] = set()

    # Go imports: "package/path"
    for match in re.finditer(r'"([a-zA-Z0-9._/-]+)"', content):
        imp = match.group(1)
        if "." in imp.split("/")[0]:
            imports.add(imp)

    return imports


def find_unused(
    dependencies: list[Dependency],
    source_dirs: list[Path],
    ecosystem: Ecosystem,
) -> list[str]:
    """Find dependencies that are not imported in source code.

    Args:
        dependencies: List of declared dependencies.
        source_dirs: Directories to scan for source files.
        ecosystem: The target ecosystem.

    Returns:
        List of dependency names that appear unused.
    """
    # Collect all imports from source files
    all_imports: set[str] = set()

    for source_dir in source_dirs:
        if not source_dir.exists():
            continue

        for file_path in source_dir.rglob("*"):
            if not file_path.is_file():
                continue

            # Skip common non-source directories
            parts = file_path.parts
            if any(p in parts for p in (".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build")):
                continue

            if ecosystem == Ecosystem.PIP and file_path.suffix == ".py":
                all_imports |= _extract_imports_from_file(file_path)
            elif ecosystem in (Ecosystem.NPM, Ecosystem.YARN, Ecosystem.PNPM) and file_path.suffix in (
                ".js", ".ts", ".jsx", ".tsx", ".mjs", ".cjs"
            ):
                all_imports |= _extract_imports_from_js(file_path)
            elif ecosystem == Ecosystem.GO and file_path.suffix == ".go":
                all_imports |= _extract_imports_from_go(file_path)

    # Check each dependency against imports
    unused: list[str] = []
    for dep in dependencies:
        import_names = _package_to_import_names(dep)
        found = any(imp in all_imports for imp in import_names)

        # Also check if the package name itself is imported (for npm packages)
        if not found:
            found = dep.name in all_imports or dep.name.replace("-", "_") in all_imports

        if not found:
            unused.append(dep.name)

    return unused


def get_import_coverage(
    dependencies: list[Dependency], source_dirs: list[Path], ecosystem: Ecosystem
) -> dict[str, float]:
    """Calculate import coverage percentage.

    Returns:
        Dictionary with coverage stats.
    """
    unused = find_unused(dependencies, source_dirs, ecosystem)
    total = len(dependencies)
    used = total - len(unused)

    return {
        "total": total,
        "used": used,
        "unused": len(unused),
        "coverage": (used / total * 100) if total > 0 else 100.0,
    }
