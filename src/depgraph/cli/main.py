"""CLI interface for DepGraph."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from depgraph import __version__
from depgraph.analysis.analyzer import analyze, analyze_and_format
from depgraph.analysis.graph import DependencyGraph
from depgraph.analysis.visualizer import visualize_stats, visualize_tree
from depgraph.models import Ecosystem
from depgraph.parsers.registry import detect_ecosystem, get_parser_for_ecosystem


def _get_ecosystem(args: argparse.Namespace) -> Ecosystem | None:
    """Get ecosystem from args."""
    if hasattr(args, "ecosystem") and args.ecosystem:
        return Ecosystem(args.ecosystem)
    return None


def _get_root(args: argparse.Namespace) -> str | None:
    """Get root package from args."""
    return getattr(args, "root", None)


def _get_source_dirs(args: argparse.Namespace, directory: Path) -> list[Path] | None:
    """Get source directories from args."""
    if getattr(args, "no_unused", False):
        return None

    if hasattr(args, "source_dirs") and args.source_dirs:
        return [directory / d for d in args.source_dirs]

    # Auto-detect source directories
    candidates = ["src", "lib", "app", ".", "pkg"]
    found = []
    for c in candidates:
        p = directory / c
        if p.exists():
            found.append(p)
    return found if found else [directory]


def _build_graph(directory: Path, ecosystem: Ecosystem | None, root: str | None) -> DependencyGraph:
    """Build a dependency graph from a directory."""
    if ecosystem:
        parser = get_parser_for_ecosystem(ecosystem)
    else:
        result = detect_ecosystem(directory)
        if result:
            parser, _ = result
        else:
            return DependencyGraph()

    if not parser:
        return DependencyGraph()

    detected = detect_ecosystem(directory)
    if not detected:
        return DependencyGraph()

    _, dep_file = detected
    deps, edges = parser.parse(dep_file, root)

    graph = DependencyGraph()
    for dep in deps:
        graph.add_node(dep)
    for edge in edges:
        graph.add_edge(edge)

    return graph


def _cmd_analyze(args: argparse.Namespace) -> int:
    """Handle analyze command."""
    directory = Path(args.directory).resolve()
    ecosystem = _get_ecosystem(args)
    root = _get_root(args)
    source_dirs = _get_source_dirs(args, directory)
    max_depth = getattr(args, "max_depth", None)

    output = analyze_and_format(
        directory=directory,
        ecosystem=ecosystem,
        root_package=root,
        source_dirs=source_dirs,
        output_format=args.output,
        max_depth=max_depth,
    )
    print(output)
    return 0


def _cmd_tree(args: argparse.Namespace) -> int:
    """Handle tree command."""
    directory = Path(args.directory).resolve()
    ecosystem = _get_ecosystem(args)
    root = _get_root(args)
    max_depth = getattr(args, "max_depth", None)

    result = analyze(directory=directory, ecosystem=ecosystem, root_package=root)

    if not result.root_package:
        print("Error: Could not determine root package. Use --root.", file=sys.stderr)
        return 1

    graph = _build_graph(directory, ecosystem, root)
    output = visualize_tree(graph, result.root_package, max_depth)
    print(output)
    return 0


def _cmd_stats(args: argparse.Namespace) -> int:
    """Handle stats command."""
    directory = Path(args.directory).resolve()
    ecosystem = _get_ecosystem(args)
    root = _get_root(args)

    graph = _build_graph(directory, ecosystem, root)
    output = visualize_stats(graph, root or directory.name)
    print(output)
    return 0


def _cmd_cycles(args: argparse.Namespace) -> int:
    """Handle cycles command."""
    directory = Path(args.directory).resolve()
    ecosystem = _get_ecosystem(args)
    root = _get_root(args)

    result = analyze(directory=directory, ecosystem=ecosystem, root_package=root)

    if result.cycles:
        print(f"Found {len(result.cycles)} circular dependency(ies):\n")
        for i, cycle in enumerate(result.cycles, 1):
            print(f"  {i}. {cycle.display} (length: {cycle.length})")
        return 1
    else:
        print("No circular dependencies detected ✓")
        return 0


def _cmd_health(args: argparse.Namespace) -> int:
    """Handle health command."""
    directory = Path(args.directory).resolve()
    ecosystem = _get_ecosystem(args)
    root = _get_root(args)

    result = analyze(directory=directory, ecosystem=ecosystem, root_package=root)

    print(f"Health Score: {result.health.overall}/100 ({result.health.grade})")
    if result.health.issues:
        print(f"\nIssues ({len(result.health.issues)}):")
        for issue in result.health.issues:
            print(f"  [{issue.severity.value.upper()}] {issue.message}")
    return 0


def _cmd_detect(args: argparse.Namespace) -> int:
    """Handle detect command."""
    directory = Path(args.directory).resolve()
    result = detect_ecosystem(directory)

    if result:
        parser, dep_file = result
        print(f"Detected: {parser.ecosystem.value}")
        print(f"File: {dep_file}")
        return 0
    else:
        print("No recognized dependency file found.")
        return 1


def _cmd_ecosystems() -> int:
    """Handle ecosystems command."""
    print("Supported ecosystems:")
    for eco in Ecosystem:
        parser = get_parser_for_ecosystem(eco)
        if parser:
            print(f"  • {eco.value}")
    return 0


def main(argv: list[str] | None = None) -> int:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="depgraph",
        description="Multi-ecosystem dependency graph analyzer with cycle detection and health scoring.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # --- analyze command ---
    analyze_p = subparsers.add_parser("analyze", help="Analyze dependencies in a directory")
    analyze_p.add_argument("directory", nargs="?", default=".", help="Directory to analyze (default: current)")
    analyze_p.add_argument("-e", "--ecosystem", choices=[e.value for e in Ecosystem], help="Force ecosystem")
    analyze_p.add_argument("-r", "--root", help="Root package name")
    analyze_p.add_argument("-o", "--output", choices=["text", "json", "markdown"], default="text", help="Output format")
    analyze_p.add_argument("-s", "--source-dirs", nargs="*", help="Source directories for unused detection")
    analyze_p.add_argument("--max-depth", type=int, help="Max tree depth for visualization")
    analyze_p.add_argument("--no-unused", action="store_true", help="Skip unused dependency detection")

    # --- tree command ---
    tree_p = subparsers.add_parser("tree", help="Show dependency tree")
    tree_p.add_argument("directory", nargs="?", default=".", help="Directory to analyze")
    tree_p.add_argument("-e", "--ecosystem", choices=[e.value for e in Ecosystem], help="Force ecosystem")
    tree_p.add_argument("-r", "--root", help="Root package name")
    tree_p.add_argument("--max-depth", type=int, help="Maximum depth to display")

    # --- stats command ---
    stats_p = subparsers.add_parser("stats", help="Show dependency statistics")
    stats_p.add_argument("directory", nargs="?", default=".", help="Directory to analyze")
    stats_p.add_argument("-e", "--ecosystem", choices=[e.value for e in Ecosystem], help="Force ecosystem")
    stats_p.add_argument("-r", "--root", help="Root package name")

    # --- cycles command ---
    cycles_p = subparsers.add_parser("cycles", help="Detect circular dependencies")
    cycles_p.add_argument("directory", nargs="?", default=".", help="Directory to analyze")
    cycles_p.add_argument("-e", "--ecosystem", choices=[e.value for e in Ecosystem], help="Force ecosystem")
    cycles_p.add_argument("-r", "--root", help="Root package name")

    # --- health command ---
    health_p = subparsers.add_parser("health", help="Show dependency health score")
    health_p.add_argument("directory", nargs="?", default=".", help="Directory to analyze")
    health_p.add_argument("-e", "--ecosystem", choices=[e.value for e in Ecosystem], help="Force ecosystem")
    health_p.add_argument("-r", "--root", help="Root package name")

    # --- detect command ---
    detect_p = subparsers.add_parser("detect", help="Auto-detect dependency ecosystem")
    detect_p.add_argument("directory", nargs="?", default=".", help="Directory to scan")

    # --- list-ecosystems command ---
    subparsers.add_parser("ecosystems", help="List supported ecosystems")

    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 1

    try:
        if args.command == "analyze":
            return _cmd_analyze(args)
        elif args.command == "tree":
            return _cmd_tree(args)
        elif args.command == "stats":
            return _cmd_stats(args)
        elif args.command == "cycles":
            return _cmd_cycles(args)
        elif args.command == "health":
            return _cmd_health(args)
        elif args.command == "detect":
            return _cmd_detect(args)
        elif args.command == "ecosystems":
            return _cmd_ecosystems()
        else:
            parser.print_help()
            return 1
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
