"""
Tests for output serialization.
"""

import json
import re
from datetime import datetime
from pathlib import Path, PurePath

import duckdb
import pytest

from repo_parser import Processor, get_resources, scan
from repo_parser.filesystem import File
from repo_parser.outputs import to_duckdb
from repo_parser.resource import Resource


def _resource(
    name: str,
    src_path: Path,
    *,
    type: str = "file",
    metadata: dict | None = None,
    content: str | None = None,
    children: list[Resource] | None = None,
) -> Resource:
    return Resource(
        name=name,
        src_path=src_path,
        path=PurePath(),
        type=type,
        metadata=metadata or {},
        content=content,
        children=children or [],
        last_modified=datetime(2024, 1, 1, 12, 0, 0),
    )


def test_to_duckdb_basic(tmp_path):
    """Test basic DuckDB serialization with path identity."""
    repo_path = tmp_path / "test-repo"
    db_path = tmp_path / "repo.duckdb"

    root = _resource(
        "test-repo",
        repo_path,
        type="repo",
        metadata={"repo_key": "repo_value"},
    )
    root.children = [
        _resource(
            "README.md",
            repo_path / "README.md",
            metadata={"file_key": "file_value"},
            content="# Test Repo",
        )
    ]

    with duckdb.connect(db_path) as con:
        to_duckdb(con, root)
        resources = con.execute(
            """
            SELECT path, parent_path, name, type, content, properties
            FROM resources
            ORDER BY path
            """
        ).fetchall()
        assert resources == [
            (".", None, "test-repo", "repo", None, '{"repo_key": "repo_value"}'),
            (
                "README.md",
                ".",
                "README.md",
                "file",
                "# Test Repo",
                '{"file_key": "file_value"}',
            ),
        ]


def test_to_duckdb_nested_tree_preserves_parent_paths(tmp_path):
    """Test DuckDB serialization with a deeper nested tree."""
    repo_path = tmp_path / "repo"
    db_path = tmp_path / "repo.duckdb"

    readme = _resource(
        "README.md",
        repo_path / "services/auth-service/README.md",
        content="# Auth Service",
    )
    service = _resource(
        "auth-service",
        repo_path / "services/auth-service",
        type="service",
        metadata={"owner": "team-auth"},
        children=[readme],
    )
    root = _resource("repo", repo_path, type="repo", children=[service])

    with duckdb.connect(db_path) as con:
        to_duckdb(con, root)
        resources = con.execute(
            "SELECT path, parent_path, name FROM resources ORDER BY path"
        ).fetchall()
        assert resources == [
            (".", None, "repo"),
            ("services/auth-service", ".", "auth-service"),
            (
                "services/auth-service/README.md",
                "services/auth-service",
                "README.md",
            ),
        ]


def test_to_duckdb_properties_preserve_json_types(tmp_path):
    """Test that metadata is stored as one JSON properties blob."""
    repo_path = tmp_path / "repo"
    db_path = tmp_path / "repo.duckdb"
    root = _resource(
        "repo",
        repo_path,
        type="repo",
        metadata={
            "simple": "value",
            "list": ["a", "b", "c"],
            "dict": {"nested": "structure"},
            "number": 42,
            "enabled": True,
        },
    )

    with duckdb.connect(db_path) as con:
        to_duckdb(con, root)
        row = con.execute("SELECT properties FROM resources").fetchone()

    assert row is not None
    properties = row[0]
    assert json.loads(properties) == {
        "simple": "value",
        "list": ["a", "b", "c"],
        "dict": {"nested": "structure"},
        "number": 42,
        "enabled": True,
    }


def test_to_duckdb_replace_existing_table(tmp_path):
    """Test that replace controls whether an existing table is overwritten."""
    db_path = tmp_path / "repo.duckdb"
    root = _resource("repo", tmp_path / "repo", type="repo")

    with duckdb.connect(db_path) as con:
        to_duckdb(con, root)
        replacement = _resource("replacement", tmp_path / "replacement", type="repo")
        to_duckdb(con, replacement)

        resources = con.execute("SELECT path, name FROM resources").fetchall()
        columns = [
            row[1] for row in con.execute("PRAGMA table_info('resources')").fetchall()
        ]

    assert resources == [(".", "replacement")]
    assert columns == [
        "path",
        "parent_path",
        "name",
        "type",
        "content",
        "properties",
        "last_modified",
    ]


def test_to_duckdb_replace_false_fails_when_table_exists(tmp_path):
    db_path = tmp_path / "repo.duckdb"
    root = _resource("repo", tmp_path / "repo", type="repo")

    with duckdb.connect(db_path) as con:
        to_duckdb(con, root)
        with pytest.raises(duckdb.CatalogException):
            to_duckdb(con, root, replace=False)


def test_to_duckdb_custom_table_name(tmp_path):
    db_path = tmp_path / "repo.duckdb"
    root = _resource("repo", tmp_path / "repo", type="repo")

    with duckdb.connect(db_path) as con:
        to_duckdb(con, root, table_name="bronze_resources")
        resources = con.execute("SELECT path, name FROM bronze_resources").fetchall()

    assert resources == [(".", "repo")]


def test_to_duckdb_rejects_invalid_table_name(tmp_path):
    db_path = tmp_path / "repo.duckdb"
    root = _resource("repo", tmp_path / "repo", type="repo")

    with duckdb.connect(db_path) as con:
        with pytest.raises(ValueError, match="Invalid DuckDB table name"):
            to_duckdb(con, root, table_name="resources; DROP TABLE resources")


def test_to_duckdb_with_example_repo(tmp_path):
    """Test serialization from a real scan of the example repo."""

    def process_markdown(file: File):
        return "file", {"title": file.name}, file

    processors = [Processor(re.compile(r"\.md$"), process_markdown, True)]
    dir, repo = scan(Path("example/repo"), processors)
    root = get_resources(repo, dir, processors, disable_last_modified=True)
    db_path = tmp_path / "example.duckdb"

    with duckdb.connect(db_path) as con:
        to_duckdb(con, root)
        readme = con.execute(
            """
            SELECT path, parent_path, properties
            FROM resources
            WHERE path = 'README.md'
            """
        ).fetchone()

    assert readme is not None
    assert readme[0] == "README.md"
    assert readme[1] == "."
    assert json.loads(readme[2]) == {"title": "README.md"}
