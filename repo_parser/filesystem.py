import pathlib
import re
from dataclasses import dataclass
from pathlib import Path, PurePath

import git

from .processor import Processor


@dataclass
class File:
    name: str
    src_path: PurePath
    content: str | None


@dataclass
class Dir:
    path: pathlib.Path
    files: list[File]
    dirs: list["Dir"]


def _scan(
    path: pathlib.Path,
    processors: list[Processor],
    ignore_patterns: list[re.Pattern],
    repo: git.Repo,
) -> Dir:
    repo_root = Path(repo.working_dir).absolute()
    rel_path = path.absolute().relative_to(repo_root)

    # return indexed files, filtered by subtree. resulting filepaths will all
    # be relative to the repository root.
    dirs = {repo_root: Dir(path=repo_root, files=[], dirs=[])}
    result = repo.git.ls_files("--exclude-standard", rel_path)

    for p in result.splitlines():
        abs_path = (repo_root / p).absolute()
        parent = abs_path.parent
        # All matching done against the relative path from the repo root
        if any(pattern.search(p) for pattern in ignore_patterns):
            continue

        d = dirs.get(parent, Dir(path=parent, files=[], dirs=[]))
        content = ""
        matched = False
        for processor in processors:
            if processor.pattern.search(p):
                matched = True
                if processor.read_content and not content:
                    content = abs_path.read_text()
        # Only append 1 File object even if multiple processors matched
        if matched:
            d.files.append(
                File(name=abs_path.name, src_path=PurePath(abs_path), content=content)
            )

        dirs[parent] = d

    # Reverse depth first merge and fill in missing directories.  dirs is
    # current a bunch of dangling Dir references, each have no dir entries
    # itself. So this loop joins them all together into the tree. In addtion it
    # fills in any missing Dir entries of parents that did not have a direct
    # child file match any processors
    visited: set[Path] = set()
    dir_paths = list(dirs.keys())
    while dir_paths:
        d = dir_paths.pop()
        if d in visited:
            continue
        visited.add(d)

        if d.absolute() == repo_root:
            continue

        parent = dirs.get(d.parent, Dir(path=d.parent, files=[], dirs=[]))
        parent.dirs.append(dirs[d])
        dirs[d.parent] = parent
        dir_paths.append(parent.path)

    return dirs[repo_root]


def scan(
    path: pathlib.Path,
    processors: list[Processor],
    ignore_patterns: list[re.Pattern] | None = None,
    subdirs: list[pathlib.Path] | None = None,
) -> tuple[Dir, git.Repo]:
    """
    Scans a GitHub repository for files and subdirectories, returning a data
    structure representing the directory tree.

    Takes in a list of processors to figure out which files should be included
    in the returned tree.

    Under the hood, this uses the `git` library to scan the repository, skipping
    files in .gitignore.

    This step does not do any post-processing of the files, though their
    content is read in if one of their processors requires it.

    Returns a tuple of (Dir, git.Repo) for further processing.
    """
    # Ensure the working_dir is the toplevel root of the tree
    repo = git.Repo(path, search_parent_directories=True)
    repo = git.Repo(repo.git.rev_parse("--show-toplevel"))

    path = path.resolve()
    # if subdirs, just scan each one and return the results
    if subdirs:
        repo_root = Path(repo.working_dir).absolute()
        dir = Dir(path=repo_root, files=[], dirs=[])
        for subdir in subdirs:
            tree = _scan(
                path / subdir,
                processors,
                ignore_patterns or [],
                repo,
            )
            dir.files += tree.files
            dir.dirs += tree.dirs
        return dir, repo

    return _scan(
        path,
        processors,
        ignore_patterns or [],
        repo,
    ), repo
