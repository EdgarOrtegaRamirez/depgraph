"""Tests for dependency file parsers."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from depgraph.models import Ecosystem
from depgraph.parsers.parsers import (
    CargoLockParser,
    GoSumParser,
    PyProjectParser,
    RequirementsParser,
)


@pytest.fixture
def tmp_dir() -> Path:
    """Create a temporary directory."""
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


class TestRequirementsParser:
    """Test the requirements.txt parser."""

    def test_parse_simple(self, tmp_dir: Path) -> None:
        req_file = tmp_dir / "requirements.txt"
        req_file.write_text("requests\nflask\nsqlalchemy\n")

        parser = RequirementsParser()
        deps, edges = parser.parse(req_file, root_package="myapp")

        assert len(deps) == 3
        assert deps[0].name == "requests"
        assert deps[1].name == "flask"
        assert deps[2].name == "sqlalchemy"
        assert len(edges) == 3
        assert edges[0].source == "myapp"
        assert edges[0].target == "requests"

    def test_parse_with_versions(self, tmp_dir: Path) -> None:
        req_file = tmp_dir / "requirements.txt"
        req_file.write_text("requests>=2.28.0\nflask==2.3.0\n")

        parser = RequirementsParser()
        deps, _ = parser.parse(req_file)

        assert deps[0].version == "2.28.0"
        assert deps[1].version == "2.3.0"

    def test_parse_with_extras(self, tmp_dir: Path) -> None:
        req_file = tmp_dir / "requirements.txt"
        req_file.write_text('requests[security]\n')

        parser = RequirementsParser()
        deps, _ = parser.parse(req_file)

        assert deps[0].extras == ["security"]

    def test_parse_skips_comments(self, tmp_dir: Path) -> None:
        req_file = tmp_dir / "requirements.txt"
        req_file.write_text("# This is a comment\nrequests\n# Another comment\n")

        parser = RequirementsParser()
        deps, _ = parser.parse(req_file)

        assert len(deps) == 1
        assert deps[0].name == "requests"

    def test_parse_skips_options(self, tmp_dir: Path) -> None:
        req_file = tmp_dir / "requirements.txt"
        req_file.write_text("-r base.txt\nrequests\n")

        parser = RequirementsParser()
        deps, _ = parser.parse(req_file)

        assert len(deps) == 1

    def test_parse_skips_urls(self, tmp_dir: Path) -> None:
        req_file = tmp_dir / "requirements.txt"
        req_file.write_text("git+https://github.com/user/repo.git\nrequests\n")

        parser = RequirementsParser()
        deps, _ = parser.parse(req_file)

        assert len(deps) == 1

    def test_parse_empty_file(self, tmp_dir: Path) -> None:
        req_file = tmp_dir / "requirements.txt"
        req_file.write_text("")

        parser = RequirementsParser()
        deps, _ = parser.parse(req_file)

        assert len(deps) == 0

    def test_parse_missing_file(self, tmp_dir: Path) -> None:
        parser = RequirementsParser()
        deps, _ = parser.parse(tmp_dir / "requirements.txt")

        assert len(deps) == 0

    def test_detect(self, tmp_dir: Path) -> None:
        parser = RequirementsParser()
        assert parser.detect(tmp_dir) is False

        (tmp_dir / "requirements.txt").write_text("")
        assert parser.detect(tmp_dir) is True

    def test_detect_variant(self, tmp_dir: Path) -> None:
        parser = RequirementsParser()
        (tmp_dir / "requirements-dev.txt").write_text("")
        assert parser.detect(tmp_dir) is True

    def test_ecosystem(self) -> None:
        assert RequirementsParser().ecosystem == Ecosystem.PIP


class TestPyProjectParser:
    """Test the pyproject.toml parser."""

    def test_parse_dependencies(self, tmp_dir: Path) -> None:
        pyproject = tmp_dir / "pyproject.toml"
        pyproject.write_text("""
[project]
name = "myapp"
version = "1.0.0"
dependencies = [
    "requests>=2.28",
    "flask>=2.3",
]
""")

        parser = PyProjectParser()
        deps, edges = parser.parse(pyproject, root_package="myapp")

        assert len(deps) == 2
        assert deps[0].name == "requests"
        assert deps[1].name == "flask"
        assert len(edges) == 2

    def test_parse_single_line_deps(self, tmp_dir: Path) -> None:
        pyproject = tmp_dir / "pyproject.toml"
        pyproject.write_text('dependencies = ["requests", "flask"]\n')

        parser = PyProjectParser()
        deps, _ = parser.parse(pyproject)

        assert len(deps) == 2

    def test_skips_optional_deps(self, tmp_dir: Path) -> None:
        pyproject = tmp_dir / "pyproject.toml"
        pyproject.write_text("""
[project]
name = "myapp"
dependencies = ["requests"]

[project.optional-dependencies]
dev = ["pytest", "ruff"]
""")

        parser = PyProjectParser()
        deps, _ = parser.parse(pyproject)

        assert len(deps) == 1
        assert deps[0].name == "requests"

    def test_detect(self, tmp_dir: Path) -> None:
        parser = PyProjectParser()
        assert parser.detect(tmp_dir) is False

        (tmp_dir / "pyproject.toml").write_text("")
        assert parser.detect(tmp_dir) is True

    def test_ecosystem(self) -> None:
        assert PyProjectParser().ecosystem == Ecosystem.PIP


class TestGoSumParser:
    """Test the go.sum parser."""

    def test_parse(self, tmp_dir: Path) -> None:
        go_sum = tmp_dir / "go.sum"
        go_sum.write_text("""
github.com/pkg/errors v0.9.0 h1:FJRI9yEhNi0+1g7t6VqZ6V6v3M1X7oRl6XzD9z2Y0E=
github.com/pkg/errors v0.9.0/go.mod h1:wawkcdKP8qVi9I6uytk1VskpUg4J34drlZh8qkd9m8=
golang.org/x/net v0.0.0-20210226172049-e18ecbb05110 h1:Qwp8DW6GMo86IYJHc7lX2hZLMO2Jl4KqN8w5m4K8t7k=
""")

        parser = GoSumParser()
        deps, edges = parser.parse(go_sum, root_package="github.com/mymodule")

        assert len(deps) == 2
        assert deps[0].name == "github.com/pkg/errors"
        assert deps[0].version == "v0.9.0"
        assert len(edges) == 2

    def test_deduplicates(self, tmp_dir: Path) -> None:
        go_sum = tmp_dir / "go.sum"
        go_sum.write_text("""
github.com/pkg/errors v0.9.0 h1:abc=
github.com/pkg/errors v0.9.0/go.mod h1:def=
""")

        parser = GoSumParser()
        deps, _ = parser.parse(go_sum)

        assert len(deps) == 1  # Deduplicated

    def test_skips_self(self, tmp_dir: Path) -> None:
        go_sum = tmp_dir / "go.sum"
        go_sum.write_text("""
github.com/mymodule v1.0.0 h1:abc=
github.com/pkg/errors v0.9.0 h1:def=
""")

        parser = GoSumParser()
        deps, _ = parser.parse(go_sum, root_package="github.com/mymodule")

        assert len(deps) == 1
        assert deps[0].name == "github.com/pkg/errors"

    def test_detect(self, tmp_dir: Path) -> None:
        parser = GoSumParser()
        assert parser.detect(tmp_dir) is False

        (tmp_dir / "go.sum").write_text("")
        assert parser.detect(tmp_dir) is True

    def test_ecosystem(self) -> None:
        assert GoSumParser().ecosystem == Ecosystem.GO


class TestCargoLockParser:
    """Test the Cargo.lock parser."""

    def test_parse(self, tmp_dir: Path) -> None:
        cargo_lock = tmp_dir / "Cargo.lock"
        cargo_lock.write_text("""
[[package]]
name = "serde"
version = "1.0.152"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "bb36210b26c3c0c5c8d6088b24206875b67a6307"

[[package]]
name = "tokio"
version = "1.25.0"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "abc123"
""")

        parser = CargoLockParser()
        deps, edges = parser.parse(cargo_lock, root_package="myapp")

        assert len(deps) == 2
        assert deps[0].name == "serde"
        assert deps[0].version == "1.0.152"
        assert len(edges) == 2

    def test_skips_self(self, tmp_dir: Path) -> None:
        cargo_lock = tmp_dir / "Cargo.lock"
        cargo_lock.write_text("""
[[package]]
name = "myapp"
version = "0.1.0"

[[package]]
name = "serde"
version = "1.0.152"
""")

        parser = CargoLockParser()
        deps, _ = parser.parse(cargo_lock, root_package="myapp")

        assert len(deps) == 1
        assert deps[0].name == "serde"

    def test_detect(self, tmp_dir: Path) -> None:
        parser = CargoLockParser()
        assert parser.detect(tmp_dir) is False

        (tmp_dir / "Cargo.lock").write_text("")
        assert parser.detect(tmp_dir) is True

    def test_ecosystem(self) -> None:
        assert CargoLockParser().ecosystem == Ecosystem.CARGO
