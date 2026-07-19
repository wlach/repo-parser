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
    scan_root = path.absolute()
    rel_path = path.absolute().relative_to(repo_root)

    # return indexed files, filtered by subtree. resulting filepaths will all
    # be relative to the repository root.
    dirs = {scan_root: Dir(path=scan_root, files=[], dirs=[])}
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

    # Reverse depth first merge and fill in missing directories. dirs is
    # currently a bunch of dangling Dir references, each with no dir entries
    # itself. This loop joins them together into the tree. In addition, it
    # fills in any missing Dir entries of parents that did not have a direct
    # child file match any processors.
    visited: set[Path] = set()
    dir_paths = list(dirs.keys())
    while dir_paths:
        d = dir_paths.pop()
        if d in visited:
            continue
        visited.add(d)

        if d.absolute() == scan_root:
            continue

        parent = dirs.get(d.parent, Dir(path=d.parent, files=[], dirs=[]))
        parent.dirs.append(dirs[d])
        dirs[d.parent] = parent
        dir_paths.append(parent.path)

    return dirs[scan_root]


def _merge_subdir_tree(root: Dir, tree: Dir) -> None:
    relative_parts = tree.path.relative_to(root.path).parts
    if not relative_parts:
        root.files.extend(tree.files)
        root.dirs.extend(tree.dirs)
        return

    current = root
    for part in relative_parts[:-1]:
        child_path = current.path / part
        child = next((d for d in current.dirs if d.path == child_path), None)
        if child is None:
            child = Dir(path=child_path, files=[], dirs=[])
            current.dirs.append(child)
        current = child

    existing = next((d for d in current.dirs if d.path == tree.path), None)
    if existing is None:
        current.dirs.append(tree)
        return

    existing.files.extend(tree.files)
    existing.dirs.extend(tree.dirs)


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
        dir = Dir(path=path, files=[], dirs=[])
        for subdir in subdirs:
            tree = _scan(
                path / subdir,
                processors,
                ignore_patterns or [],
                repo,
            )
            _merge_subdir_tree(dir, tree)
        return dir, repo

    return _scan(
        path,
        processors,
        ignore_patterns or [],
        repo,
    ), repo
