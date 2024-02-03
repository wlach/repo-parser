import pathlib
from dataclasses import dataclass
from pathlib import PurePath
from typing import List, Optional

import git

from .processor import Processor


@dataclass
class File:
    name: str
    src_path: PurePath
    content: Optional[str]


@dataclass
class Dir:
    path: pathlib.Path
    files: List[File]
    dirs: List["Dir"]


def _scan(path: pathlib.Path, processors: List[Processor], repo: git.Repo) -> Dir:
    dir = Dir(path=pathlib.PurePath(path), files=[], dirs=[])

    entries = [entry for entry in path.iterdir()]
    if not entries:
        return dir
    # FIXME: At some point we should only ignore .git in the root directory
    ignored = set(repo.ignored(*[entry.name for entry in entries]) + [".git"])

    for entry in entries:
        if entry.name in ignored:
            continue
        elif entry.is_file():
            for processor in processors:
                if processor.pattern.search(str(entry)):
                    content = entry.read_text() if processor.read_content else None
                    dir.files.append(
                        File(
                            name=entry.name,
                            src_path=(path / entry.name),
                            content=content,
                        )
                    )
        elif entry.is_dir():
            dir.dirs.append(_scan(path / entry.name, processors, repo))

    return dir



def scan(path: pathlib.Path, processors: List[Processor]) -> Dir:
    """
    Scans a GitHub repository for files and subdirectories, returning a data
    structure representing the directory tree.
    
    Takes in a list of processors to figure out which files should be included
    in the returned tree.

    Under the hood, this uses the `git` library to scan the repository, skipping
    files in .gitignore.

    This step does not do any post-processing of the files, though their
    content is read in if one of their processors requires it.
    """
    repo = git.Repo(path)
    return _scan(path, processors, repo)
