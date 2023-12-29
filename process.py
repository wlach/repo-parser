#!/usr/bin/env python

import os
import pathlib
import re
import shutil
from dataclasses import dataclass
from typing import Dict, List, Tuple

import frontmatter
import jinja2
import typer

def _markdown_processor(filename: pathlib.Path):
    metadata, content = frontmatter.parse(filename.read_text())
    return metadata, content


@dataclass
class File:
    name: str
    metadata: Dict
    content: str


@dataclass
class Dir:
    name: str
    files: List[File]
    dirs: List['Dir']


PROCESSORS = [
    (re.compile("\.md$"), _markdown_processor),
]

def _scan(dirname: pathlib.Path) -> Dir:
    dir = Dir(name=dirname.name, files=[], dirs=[])

    # would love to use glob, but it doesn't support excluding stuff
    with os.scandir(dirname) as entries:
        for entry in entries:
            if entry.is_file():
                for pattern, processor in PROCESSORS:
                    if pattern.search(entry.name):
                        metadata, content = processor(dirname / entry.name)
                        dir.files.append(File(name=entry.name, metadata=metadata, content=content))
            elif entry.is_dir():
                dir.dirs.append(_scan(dirname / entry.name))

    return dir

def _augment_metadata(dir: Dir, extra_metadata: Dict):
    # add language metadata to service/library files based on which directory they are in
    # (this will have weird effects if there is more than one language in a directory,
    # but that shouldn't happen)
    for file in dir.files:
        if file.metadata.get('type') == 'language':
            extra_metadata['language'] = dir.name
        else:
            file.metadata.update(extra_metadata)

    for subdir in dir.dirs:
        _augment_metadata(subdir, extra_metadata)

def _serialize(dir: Dir) -> Dict:
    dict = {'files': [], 'dirs': []}
    for file in dir.files:
        dict['files'].append({'name': file.name, 'metadata': file.metadata, 'content': file.content})
    for subdir in dir.dirs:
        dict['dirs'].append(_serialize(subdir))
    return dict

def _collect_resources(dir: Dir, type: str) -> List[Tuple[File, Dir]]:
    # if directory contains a file of a given type, it is of that
    # type (resources cannot be nested)
    for file in dir.files:
        if file.metadata.get('type') == type:
            return [(file, dir)]

    of_type = []
    for subdir in dir.dirs:
        of_type.extend(_collect_resources(subdir, type))

    return of_type

def _write_files(input_tree: Dir, output_dir: pathlib.Path, skip_file: File) -> None:
    for file in input_tree.files:
        if file.name == skip_file.name:
            continue
        file_path = output_dir / file.name
        file_path.write_text(file.content)
    for subdir in input_tree.dirs:
        subdir_path = output_dir / subdir.name
        subdir_path.mkdir(parents=True, exist_ok=True)
        _write_files(subdir, subdir_path)

def _write_docs(input_tree: Dir, docs_template_dir: pathlib.Path, output_dir: pathlib.Path) -> None:
    services = _collect_resources(input_tree, 'service')
    libraries = _collect_resources(input_tree, 'library')

    # first, create the docs directory from our template
    for file in docs_template_dir.glob('**/*'):
        if file.is_file():
            file_path = output_dir / file.relative_to(docs_template_dir)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            if file.name.endswith('.in'):
                file_path = file_path.with_name(file_path.name[:-3])
                file_path.write_text(
                    jinja2.Template(
                        file.read_text()
                    ).render(**{'services': services, 'libraries': libraries})
                )
            else:
                shutil.copy2(file, file_path)

    # then, iterate through resources and write them out
    for (type, subdir, resources) in [('library', 'libraries', libraries), ('service', 'services', services)]:
        resources_path = output_dir / subdir
        resources_path.mkdir(parents=True, exist_ok=True)
        for resource_file, dir in resources:
            resource_path = resources_path / dir.name
            resource_path.mkdir(parents=True, exist_ok=True)
            # rewrite the resource file as index.md
            resource_file_path = resource_path / 'index.md'
            resource_file_path.write_text(resource_file.content)
            # copy over any other files
            _write_files(dir, resource_path, resource_file)

def main(dirname: pathlib.Path, docs_dir: pathlib.Path, output_dir: pathlib.Path):
    dir = _scan(dirname)
    _augment_metadata(dir, {})
    # copy docs dir to destination verbatim
    # shutil.copytree(docs_dir, output_dir, dirs_exist_ok=True)
    # write out the service and library docs
    _write_docs(dir, docs_dir, output_dir) 

if __name__ == "__main__":
    typer.run(main)
