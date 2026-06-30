"""Unused dependency detection via import analysis."""

from __future__ import annotations

import ast
import logging
from pathlib import Path

from depgraph.models import Dependency, Ecosystem

logger = logging.getLogger(__name__)

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
    """Extract import names from JavaScript/TypeScript files using tree-sitter AST."""
    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
        content_bytes = content.encode("utf-8")
    except OSError:
        return set()

    imports: set[str] = set()

    try:
        import tree_sitter_javascript as tsjs
        import tree_sitter_typescript as tsts
        from tree_sitter import Language, Parser

        # Choose parser based on file extension
        if file_path.suffix in (".ts", ".tsx"):
            lang = Language(tsts.language_typescript())
        else:
            lang = Language(tsjs.language())

        parser = Parser(lang)
        tree = parser.parse(content_bytes)

        # Walk AST to find import declarations and require calls
        _walk_js_imports(tree.root_node, imports)

    except ImportError:
        logger.debug("tree-sitter not available for JS, falling back to regex")
        _extract_imports_from_js_fallback(content, imports)

    return imports


def _walk_js_imports(node, imports: set[str]) -> None:
    """Recursively walk JS AST to extract import specifiers."""
    node_type = node.type

    # import declarations: import X from 'Y' or import { X } from 'Y'
    if node_type == "import_statement":
        source = _find_js_child(node, "string")
        if source:
            pkg = _normalize_js_import(source)
            if pkg:
                imports.add(pkg)

    # require() calls: const X = require('Y')
    elif node_type == "call_expression":
        func = _find_js_child(node, "identifier")
        if func and func.text == b"require":
            arg = _find_js_child(node, "string")
            if arg:
                pkg = _normalize_js_import(arg)
                if pkg:
                    imports.add(pkg)

    # Dynamic import(): import('Y')
    elif node_type == "import":
        # Check if this is inside a call_expression parent
        pass

    # export ... from 'Y'
    elif node_type in ("export_statement", "export_default_declaration"):
        source = _find_js_child(node, "string")
        if source:
            pkg = _normalize_js_import(source)
            if pkg:
                imports.add(pkg)

    # Recurse into children
    for child in node.children:
        _walk_js_imports(child, imports)


def _find_js_child(node, child_type: str):
    """Find first descendant of a given type in a JS AST node (recursive)."""
    for child in node.children:
        if child.type == child_type:
            return child
        # Recurse into children to find nested nodes
        found = _find_js_child(child, child_type)
        if found:
            return found
    return None


def _normalize_js_import(source_node) -> str | None:
    """Extract and normalize a JS import source from a string AST node."""
    # Get the raw text and strip quotes
    raw = source_node.text.decode("utf-8") if source_node.text else ""
    imp = raw.strip("'\"`")

    if not imp or imp.startswith("."):
        return None  # Skip empty and relative imports

    # Handle scoped packages: @scope/package
    if imp.startswith("@"):
        parts = imp.split("/")
        return f"{parts[0]}/{parts[1]}" if len(parts) > 1 else parts[0]

    # Handle subpath imports: package/subpath
    return imp.split("/")[0]


def _extract_imports_from_js_fallback(content: str, imports: set[str]) -> None:
    """Regex fallback for JS imports when tree-sitter is unavailable."""
    import re

    # ES module imports
    for match in re.finditer(r"""(?:import|from)\s+['"]([^'"]+)['"]""", content):
        pkg = _normalize_js_import_str(match.group(1))
        if pkg:
            imports.add(pkg)

    # require() calls
    for match in re.finditer(r"""require\(['"]([^'"]+)['"]\)""", content):
        pkg = _normalize_js_import_str(match.group(1))
        if pkg:
            imports.add(pkg)


def _normalize_js_import_str(imp: str) -> str | None:
    """Normalize a raw JS import string."""
    if not imp or imp.startswith("."):
        return None
    if imp.startswith("@"):
        parts = imp.split("/")
        return f"{parts[0]}/{parts[1]}" if len(parts) > 1 else parts[0]
    return imp.split("/")[0]


def _extract_imports_from_go(file_path: Path) -> set[str]:
    """Extract import paths from Go files using tree-sitter AST."""
    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
        content_bytes = content.encode("utf-8")
    except OSError:
        return set()

    imports: set[str] = set()

    try:
        import tree_sitter_go as tsgo
        from tree_sitter import Language, Parser

        lang = Language(tsgo.language())
        parser = Parser(lang)
        tree = parser.parse(content_bytes)

        # Walk AST to find import declarations
        _walk_go_imports(tree.root_node, imports)

    except ImportError:
        logger.debug("tree-sitter not available for Go, falling back to regex")
        _extract_imports_from_go_fallback(content, imports)

    return imports


def _walk_go_imports(node, imports: set[str]) -> None:
    """Recursively walk Go AST to extract import paths."""
    # Go import_declaration contains import_spec_list with import_spec children
    if node.type == "import_declaration":
        for child in node.children:
            if child.type == "import_spec_list":
                for spec in child.children:
                    if spec.type == "import_spec":
                        path = _find_go_child(spec, "interpreted_string_literal")
                        if path:
                            imp = path.text.decode("utf-8").strip('"')
                            if imp:
                                imports.add(imp)
            elif node.type == "import_spec":
                path = _find_go_child(node, "interpreted_string_literal")
                if path:
                    imp = path.text.decode("utf-8").strip('"')
                    if imp:
                        imports.add(imp)

    # Recurse into children
    for child in node.children:
        _walk_go_imports(child, imports)


def _find_go_child(node, child_type: str):
    """Find first child of a given type in a Go AST node."""
    for child in node.children:
        if child.type == child_type:
            return child
    return None


def _extract_imports_from_go_fallback(content: str, imports: set[str]) -> None:
    """Regex fallback for Go imports when tree-sitter is unavailable."""
    import re

    # Match import blocks and single imports
    # Handle both: import "fmt" and import ( "fmt" "net/http" )
    for match in re.finditer(r'import\s*(?:\(([^)]+)\)|"([^"]+)")', content):
        block = match.group(1) or match.group(2)
        if block:
            # Extract all quoted strings from the block
            for pkg_match in re.finditer(r'"([^"]+)"', block):
                imp = pkg_match.group(1)
                if imp:
                    imports.add(imp)
            # Single import (no parentheses)
            if match.group(2):
                imports.add(match.group(2))


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
