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


def _scan(
    path: pathlib.Path,
    processors: List[Processor],
    repo: git.Repo,
    depth: int,
    max_depth: Optional[int],
) -> Dir:
    dir = Dir(path=pathlib.PurePath(path), files=[], dirs=[])
    entries = [entry for entry in path.iterdir()]
    if not entries:
        return dir
    ignored = set(repo.ignored(*[entry.resolve() for entry in entries]))

    for entry in entries:
        # FIXME: At some point we should only ignore .git in the root directory
        if entry.name == ".git" or str(entry.resolve()) in ignored:
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
        elif entry.is_dir() and (max_depth is None or depth < max_depth):
            dir.dirs.append(
                _scan(path / entry.name, processors, repo, depth + 1, max_depth)
            )

    return dir


def scan(
    path: pathlib.Path,
    processors: List[Processor],
    subdirs: Optional[List[pathlib.Path]] = None,
    max_depth: Optional[int] = None,
) -> Dir:
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

    # if subdirs, just scan each one and return the results
    if subdirs:
        dir = Dir(path=pathlib.PurePath(path), files=[], dirs=[])
        for subdir in subdirs:
            dir.dirs.append(_scan(path / subdir, processors, repo, 0, max_depth))
        return dir

    # otherwise read everything up to max_depth
    return _scan(path, processors, repo, 0, max_depth)
