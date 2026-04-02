"""
Output serialization for repo-parser.

This module provides functions to serialize the Resource tree into various formats.
"""

import json
import re
from pathlib import Path
from typing import Any

import duckdb

from .resource import Resource

_SQL_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def to_duckdb(
    con: duckdb.DuckDBPyConnection,
    resource: Resource,
    *,
    table_name: str = "resources",
    replace: bool = True,
) -> None:
    """
    Write a Resource tree to a DuckDB table.

    Creates a table containing the flattened resource tree.

    Args:
        con: DuckDB connection to write into
        resource: Root Resource to serialize
        table_name: Name of the table to create
        replace: Whether to drop an existing table with the same name

    The caller owns the DuckDB connection and decides whether it is in-memory
    or file-backed.
    """
    if not _SQL_IDENTIFIER_PATTERN.fullmatch(table_name):
        msg = f"Invalid DuckDB table name: {table_name!r}"
        raise ValueError(msg)

    if replace:
        con.sql(f"DROP TABLE IF EXISTS {table_name}")

    con.sql(f"""
            CREATE TABLE {table_name} (
                path VARCHAR PRIMARY KEY,
                parent_path VARCHAR,
                name VARCHAR NOT NULL,
                type VARCHAR NOT NULL,
                content TEXT,
                properties JSON,
                last_modified TIMESTAMP NOT NULL,
                FOREIGN KEY (parent_path) REFERENCES {table_name}(path)
            )
        """)

    # Flatten the resource tree and insert
    resource_rows = _flatten_resource_tree(resource, Path(resource.src_path))

    # Insert resources
    con.executemany(
        f"""
            INSERT INTO {table_name} 
            (path, parent_path, name, type, content, properties, last_modified)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
        resource_rows,
    )


def _flatten_resource_tree(
    resource: Resource,
    root_path: Path,
    parent_path: str | None = None,
) -> list[tuple[Any, ...]]:
    """
    Flatten a Resource tree into rows for database insertion.

    Args:
        resource: Resource to flatten
        root_path: Source path of the root resource
        parent_path: Path of parent resource (None for root)

    Returns:
        List of tuples for the resources table
    """
    resource_rows = []
    resource_path = _resource_path(resource, root_path)

    # Add this resource
    resource_rows.append(
        (
            resource_path,
            parent_path,
            resource.name,
            resource.type,
            resource.content,
            json.dumps(resource.metadata, sort_keys=True, default=str),
            resource.last_modified,
        )
    )

    # Recursively process children
    for child in resource.children:
        resource_rows.extend(
            _flatten_resource_tree(child, root_path, parent_path=resource_path)
        )

    return resource_rows


def _resource_path(resource: Resource, root_path: Path) -> str:
    relative_path = Path(resource.src_path).relative_to(root_path)
    if str(relative_path) == ".":
        return "."

    return relative_path.as_posix()
