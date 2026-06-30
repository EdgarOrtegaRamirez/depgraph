# DepGraph

Multi-ecosystem dependency graph analyzer with cycle detection, health scoring, and unused dependency detection.

## Features

- **Multi-Ecosystem Support**: Analyze Python (pip), JavaScript (npm/yarn), Go, and Rust (Cargo) dependencies
- **Cycle Detection**: Detect circular dependencies using DFS algorithm
- **Health Scoring**: Calculate a 0-100 health score based on depth, conflicts, cycles, and more
- **Unused Detection**: Scan source files to find unused dependencies via AST/import analysis
- **ASCII Visualization**: Generate tree and flat dependency visualizations
- **Multiple Output Formats**: Text, JSON, and Markdown reports

## Quick Start

```bash
# Install
pip install depgraph

# Analyze current directory
depgraph analyze

# Show dependency tree
depgraph tree

# Detect cycles
depgraph cycles

# Health check
depgraph health

# JSON output
depgraph analyze -o json
```

## Supported Ecosystems

| Ecosystem | Detection File |
|-----------|----------------|
| Python (pip) | `requirements*.txt`, `pyproject.toml` |
| JavaScript (npm) | `package-lock.json` |
| Go | `go.sum` |
| Rust (Cargo) | `Cargo.lock` |

## CLI Commands

- `analyze` — Full dependency analysis with health score, cycles, and unused detection
- `tree` — ASCII tree visualization of dependencies
- `stats` — Dependency statistics (depth, breadth, counts)
- `cycles` — Detect circular dependencies
- `health` — Dependency health score and issues
- `detect` — Auto-detect the dependency ecosystem
- `ecosystems` — List supported ecosystems

## Examples

### Analyze a Python project

```bash
depgraph analyze /path/to/python/project
```

### Analyze with explicit ecosystem

```bash
depgraph analyze -e go /path/to/go/project
```

### JSON report for CI/CD

```bash
depgraph analyze -o json > depgraph-report.json
```

### Check for cycles only

```bash
depgraph cycles /path/to/project
```

## Architecture

```
src/depgraph/
├── models.py              # Data models (Dependency, Edge, Cycle, HealthScore, etc.)
├── parsers/
│   ├── base.py            # Abstract base parser
│   ├── parsers.py         # Ecosystem parsers (pip, npm, go, cargo)
│   └── registry.py        # Auto-detection and parser registry
└── analysis/
    ├── graph.py           # DependencyGraph with DFS/BFS/cycle detection
    ├── health.py          # Health scoring engine
    ├── unused.py          # Unused dependency detection via AST analysis
    ├── visualizer.py      # ASCII tree and stats visualization
    └── analyzer.py        # Main analyzer orchestrator
```

### Key Algorithms

- **Cycle Detection**: Modified DFS with recursion stack tracking
- **BFS Traversal**: Level-order traversal for depth/breadth metrics
- **Topological Sort**: Kahn's algorithm for dependency ordering
- **Impact Scoring**: Reverse BFS to calculate blast radius
- **Import Analysis**: AST parsing via tree-sitter (Python ast, JS/TS tree-sitter-javascript/typescript, Go tree-sitter-go) with regex fallback

## Testing

```bash
# Run all tests
pytest

# With coverage
pytest --cov=depgraph

# Run specific test file
pytest tests/test_graph.py
```

## Development

```bash
# Install dev dependencies
uv pip install -e ".[dev]"

# Lint
ruff check src/ tests/

# Format
ruff format src/ tests/
```

## License

MIT
