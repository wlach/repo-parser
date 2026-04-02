#!/usr/bin/env python

"""
Example parser configuration, which is used to generate the example site.
"""

import json
import pathlib
import re
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime
from typing import Annotated

import duckdb
import frontmatter
import jinja2
import typer
from livereload import Server

from repo_parser import Processor, get_resources, scan
from repo_parser.filesystem import File
from repo_parser.outputs import to_duckdb


@dataclass
class RenderResource:
    name: str
    path: str
    src_path: str
    type: str
    metadata: dict
    content: str | None
    last_modified: datetime


def _process_markdown(file: File):
    metadata, _ = frontmatter.parse(file.content or "")

    filetype = metadata.get("type", "file")
    metadata.pop("type", None)  # remove "type" from the metadata

    return filetype, metadata, file


def _augment_metadata(con: duckdb.DuckDBPyConnection) -> None:
    """
    Create a derived resources table with inherited language metadata.
    """
    con.sql("""
        CREATE OR REPLACE TABLE resources_derived AS
        SELECT
            r.path,
            r.parent_path,
            r.name,
            r.type,
            r.content,
            CASE
                WHEN r.type != 'language' AND language.name IS NOT NULL
                THEN json_merge_patch(
                    r.properties,
                    json_object('language', language.name)
                )
                ELSE r.properties
            END AS properties,
            r.last_modified
        FROM resources_raw r
        LEFT JOIN LATERAL (
            SELECT ancestor.name
            FROM resources_raw ancestor
            WHERE ancestor.type = 'language'
              AND (
                  r.path = ancestor.path
                  OR starts_with(r.path, ancestor.path || '/')
              )
            ORDER BY length(ancestor.path) DESC
            LIMIT 1
        ) language ON true
    """)


def _get_resources(
    con: duckdb.DuckDBPyConnection, resource_type: str
) -> list[RenderResource]:
    rows = con.execute(
        """
        SELECT name, path, type, properties, content, last_modified
        FROM resources_derived
        WHERE type = ?
        ORDER BY name
        """,
        [resource_type],
    ).fetchall()

    return [
        RenderResource(
            name=name,
            path=path,
            src_path=path,
            type=resource_type,
            metadata=json.loads(properties),
            content=content,
            last_modified=last_modified,
        )
        for name, path, _type, properties, content, last_modified in rows
    ]


def _docs_file_path(resource_path: str, file_path: str) -> pathlib.PurePath:
    relative_path = pathlib.PurePath(file_path).relative_to(resource_path)
    if relative_path.name == "README.md":
        return relative_path.with_name("index.md")

    return relative_path


def _write_files(
    con: duckdb.DuckDBPyConnection, resource: RenderResource, output_dir: pathlib.Path
) -> None:
    rows = con.execute(
        """
        SELECT path, content, properties, last_modified
        FROM resources_derived
        WHERE parent_path = ?
          AND type = 'file'
        ORDER BY path
        """,
        [resource.path],
    ).fetchall()

    for file_path, content, properties, last_modified in rows:
        output_path = output_dir / _docs_file_path(resource.path, file_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        post = frontmatter.loads(content or "")
        post.metadata.update(json.loads(properties))
        post.metadata["last_updated"] = last_modified.strftime("%Y-%m-%d")

        output_path.write_text(frontmatter.dumps(post))


def _write_docs(
    con: duckdb.DuckDBPyConnection,
    docs_template_dir: pathlib.Path,
    output_dir: pathlib.Path,
) -> None:
    services = _get_resources(con, "service")
    libraries = _get_resources(con, "library")
    languages = _get_resources(con, "language")

    # first, create the docs directory from our template
    for file in docs_template_dir.glob("**/*"):
        if file.is_file():
            file_path = output_dir / file.relative_to(docs_template_dir)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            if file.name.endswith(".in"):
                file_path = file_path.with_name(file_path.name[:-3])
                file_path.write_text(
                    jinja2.Template(
                        file.read_text(), trim_blocks=True, lstrip_blocks=True
                    ).render(
                        **{
                            "services": services,
                            "libraries": libraries,
                            "languages": languages,
                        }
                    )
                )
            elif file.name != "README.md":
                # copy every other file except README.md, which should not
                # be included in the generated docs (at least at its direct
                # path)
                shutil.copy2(file, file_path)

    # then, iterate through resources and write them out
    for subdir, resources in [
        ("libraries", libraries),
        ("services", services),
        ("languages", languages),
    ]:
        resources_path = output_dir / subdir
        resources_path.mkdir(parents=True, exist_ok=True)
        for resource in resources:
            resource_path = resources_path / resource.name
            resource_path.mkdir(parents=True, exist_ok=True)
            # copy over any other files
            _write_files(con, resource, resource_path)


def _scan_and_write_docs(
    dirname: pathlib.Path, docs_dir: pathlib.Path, output_dir: pathlib.Path
):
    print(f"Scanning {dirname} and writing docs to {output_dir}")

    processors = [
        Processor(re.compile(r"\.md$"), _process_markdown, True),
    ]

    dir, repo = scan(dirname, processors)
    root_resource = get_resources(repo, dir, processors)

    output_dir.mkdir(parents=True, exist_ok=True)
    db_path = output_dir / "repo.duckdb"
    db_path.unlink(missing_ok=True)
    with duckdb.connect(db_path) as con:
        to_duckdb(con, root_resource, table_name="resources_raw")
        _augment_metadata(con)

        _write_docs(con, docs_dir, output_dir)


def _rebuild_sphinx(
    dirname: pathlib.Path, docs_dir: pathlib.Path, output_dir: pathlib.Path
):
    _scan_and_write_docs(dirname, docs_dir, output_dir)
    subprocess.run(
        ["sphinx-build", str(output_dir), str(output_dir / "_build" / "html")]
    )


def main(
    dirname: pathlib.Path,
    docs_dir: pathlib.Path,
    output_dir: pathlib.Path,
    watch: Annotated[
        bool | None,
        typer.Option(
            "--watch", help="Continuously watch for changes, build, and serve website"
        ),
    ] = False,
):
    if watch:
        _rebuild_sphinx(dirname, docs_dir, output_dir.resolve())
        server = Server()
        server.watch(
            dirname,
            lambda: _rebuild_sphinx(dirname, docs_dir, output_dir.resolve()),
            delay=1,
        )
        server.serve(root=str(output_dir / "_build" / "html"), port=8000)
    else:
        _scan_and_write_docs(dirname, docs_dir, output_dir)


if __name__ == "__main__":
    typer.run(main)
