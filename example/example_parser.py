#!/usr/bin/env python

"""
Example parser configuration, which is used to generate the example site.
"""

import pathlib
import re
import shutil
import subprocess
from typing import Dict, List, Optional

import frontmatter
import jinja2
import typer
from livereload import Server
from typing_extensions import Annotated

from repo_parser import Processor, Resource, get_resources, scan


def _process_markdown(file_contents: str):
    metadata, _ = frontmatter.parse(file_contents)

    filetype = metadata.get("type", "file")
    metadata.pop("type", None)  # remove "type" from the metadata

    return filetype, metadata, file_contents


def _augment_metadata(resource: Resource, extra_metadata: Dict):
    """
    add language metadata to service/library files based on parent resources
    """
    if resource.type == "language":
        extra_metadata["language"] = resource.name
    else:
        resource.metadata.update(extra_metadata)

    for child in resource.children:
        _augment_metadata(child, extra_metadata)


def _rewrite_readmes(resource: Resource) -> None:
    """
    rewrite README.md files to index.md (for Sphinx)

    FIXME: maintain original paths for github links, etc
    """
    if resource.path == pathlib.PurePath("README.md"):
        resource.path = pathlib.PurePath("index.md")
    for child in resource.children:
        _rewrite_readmes(child)


def _collect_resources(resource: Resource, type: str) -> List[Resource]:
    resources: List[Resource] = []

    # append the resource itself (if it matches the type) as well as any children
    # that also match
    if resource.type == type:
        resources.append(resource)
    for child in resource.children:
        resources.extend(_collect_resources(child, type))

    return resources


def _write_files(resource: Resource, output_dir: pathlib.Path) -> None:
    for child in resource.children:
        if child.type == "file":
            file_path = output_dir / child.path
            # FIXME: this is highly inefficient, we attempt to make a directory
            # for every file, even if it's not needed (this is required because
            # file resources may live under a deeply nested subpath)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(child.content)


def _write_docs(
    repo: Resource, docs_template_dir: pathlib.Path, output_dir: pathlib.Path
) -> None:
    services = _collect_resources(repo, "service")
    libraries = _collect_resources(repo, "library")
    languages = _collect_resources(repo, "language")

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
            _write_files(resource, resource_path)


def _scan_and_write_docs(
    dirname: pathlib.Path, docs_dir: pathlib.Path, output_dir: pathlib.Path
):
    print(f"Scanning {dirname} and writing docs to {output_dir}")

    processors = [
        Processor(re.compile("\.md$"), _process_markdown, True),
    ]

    dir = scan(dirname, processors)
    repo = get_resources(dir, processors)

    _augment_metadata(repo, {})
    _rewrite_readmes(repo)

    _write_docs(repo, docs_dir, output_dir)


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
        Optional[bool],
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
