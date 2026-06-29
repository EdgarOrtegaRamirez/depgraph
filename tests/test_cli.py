"""Tests for the CLI interface."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from depgraph.cli.main import main


@pytest.fixture
def tmp_dir() -> Path:
    """Create a temporary directory."""
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


@pytest.fixture
def pip_project(tmp_dir: Path) -> Path:
    """Create a minimal pip project."""
    (tmp_dir / "requirements.txt").write_text("requests\nflask\n")
    return tmp_dir


@pytest.fixture
def go_project(tmp_dir: Path) -> Path:
    """Create a minimal Go project."""
    (tmp_dir / "go.sum").write_text("""
github.com/pkg/errors v0.9.0 h1:abc=
golang.org/x/net v0.0.0-20210226172049-e18ecbb05110 h1:def=
""")
    return tmp_dir


@pytest.fixture
def cargo_project(tmp_dir: Path) -> Path:
    """Create a minimal Cargo project."""
    (tmp_dir / "Cargo.lock").write_text("""
[[package]]
name = "serde"
version = "1.0.152"

[[package]]
name = "tokio"
version = "1.25.0"
""")
    return tmp_dir


class TestCLI:
    """Test CLI commands."""

    def test_no_command(self) -> None:
        result = main([])
        assert result == 1

    def test_version(self) -> None:
        with pytest.raises(SystemExit) as exc_info:
            main(["--version"])
        assert exc_info.value.code == 0

    def test_analyze_pip(self, pip_project: Path) -> None:
        result = main(["analyze", str(pip_project), "-r", "myapp"])
        assert result == 0

    def test_analyze_json(self, pip_project: Path) -> None:
        result = main(["analyze", str(pip_project), "-r", "myapp", "-o", "json"])
        assert result == 0

    def test_analyze_markdown(self, pip_project: Path) -> None:
        result = main(["analyze", str(pip_project), "-r", "myapp", "-o", "markdown"])
        assert result == 0

    def test_tree(self, pip_project: Path) -> None:
        result = main(["tree", str(pip_project), "-r", "myapp"])
        assert result == 0

    def test_stats(self, pip_project: Path) -> None:
        result = main(["stats", str(pip_project), "-r", "myapp"])
        assert result == 0

    def test_cycles_no_cycles(self, pip_project: Path) -> None:
        result = main(["cycles", str(pip_project), "-r", "myapp"])
        assert result == 0  # No cycles found

    def test_health(self, pip_project: Path) -> None:
        result = main(["health", str(pip_project), "-r", "myapp"])
        assert result == 0

    def test_detect_pip(self, pip_project: Path) -> None:
        result = main(["detect", str(pip_project)])
        assert result == 0

    def test_detect_go(self, go_project: Path) -> None:
        result = main(["detect", str(go_project)])
        assert result == 0

    def test_detect_cargo(self, cargo_project: Path) -> None:
        result = main(["detect", str(cargo_project)])
        assert result == 0

    def test_detect_none(self, tmp_dir: Path) -> None:
        result = main(["detect", str(tmp_dir)])
        assert result == 1

    def test_ecosystems(self) -> None:
        result = main(["ecosystems"])
        assert result == 0

    def test_analyze_missing_dir(self) -> None:
        result = main(["analyze", "/nonexistent/path"])
        assert result == 1

    def test_analyze_with_ecosystem_flag(self, pip_project: Path) -> None:
        result = main(["analyze", str(pip_project), "-e", "pip", "-r", "myapp"])
        assert result == 0

    def test_analyze_with_source_dirs(self, pip_project: Path) -> None:
        src_dir = pip_project / "src"
        src_dir.mkdir()
        (src_dir / "app.py").write_text("import requests\n")

        result = main(["analyze", str(pip_project), "-r", "myapp", "-s", "src"])
        assert result == 0

    def test_analyze_no_unused(self, pip_project: Path) -> None:
        result = main(["analyze", str(pip_project), "-r", "myapp", "--no-unused"])
        assert result == 0
