from dataclasses import dataclass
from datetime import datetime
from pathlib import PurePath

import git

from .filesystem import Dir
from .processor import Processor


@dataclass
class Resource:
    name: str
    src_path: PurePath
    path: PurePath
    type: str
    metadata: dict
    content: str | None
    children: list["Resource"]
    last_modified: datetime


def _get_last_modified(repo: git.Repo, file_path: PurePath) -> datetime:
    """Get the last modification date from git as a datetime object"""
    commits = list(repo.iter_commits(paths=str(file_path), max_count=1))
    if commits:
        return datetime.fromtimestamp(commits[0].committed_date)

    return datetime.now()


def _get_resources(
    dir: Dir, parent_path: PurePath, processors: list[Processor], repo: git.Repo
) -> list[Resource]:
    child_resources: list[Resource] = []
    dir_resource: Resource | None = None

    # do a first pass to see if we can find a "dir_resource"
    for file in dir.files:
        for processor in processors:
            if processor.pattern.search(file.name):
                filetype, metadata, _ = processor.process(file.content or "")
                if filetype != "file":
                    if dir_resource is None:
                        dir_resource = Resource(
                            name=dir.path.name,
                            src_path=dir.path,
                            path=PurePath(),
                            type=filetype,
                            metadata=metadata,
                            content=None,
                            children=[],
                            last_modified=datetime.now(),  # Placeholder, will be computed from children
                        )
                        # parent path is now the dir_resource
                        parent_path = dir_resource.path
                    else:
                        # a previous processor picked this up, augment the metadata
                        # FIXME: I think we want to be able to override the name as well
                        dir_resource.metadata.update(metadata)

    # do a second pass to find all the child resources, placing
    # their paths relative to the parent
    for file in dir.files:
        for processor in processors:
            if processor.pattern.search(file.name):
                _, metadata, _ = processor.process(file.content or "")
                child_resources.append(
                    Resource(
                        name=file.name,
                        path=parent_path / file.name,
                        src_path=file.src_path,
                        type="file",
                        metadata=metadata,
                        content=file.content,
                        children=[],
                        last_modified=_get_last_modified(repo, file.src_path),
                    )
                )
                # Will only match once!
                break

    for subdir in dir.dirs:
        child_resources.extend(
            _get_resources(subdir, parent_path / subdir.path.name, processors, repo)
        )

    # if this directory did not define a new resource, append any newly
    # found resources to the parent
    if dir_resource is None:
        return child_resources

    # otherwise, add the child resources to the dir_resource, and return that
    dir_resource.children = child_resources

    # Update dir_resource last_modified to be the most recent from all children
    # (which includes all files in this directory, even the one that defined it)
    if child_resources:
        dir_resource.last_modified = max(
            child.last_modified for child in child_resources
        )
    # If no children, keep the placeholder datetime.now()

    return [dir_resource]


def get_resources(dir: Dir, processors: list[Processor], repo: git.Repo) -> Resource:
    """
    Gets a list of resources from a scanned filesystem.

    Will process each file in the filesystem with the provided processors,
    note that order matters: the first processor that matches a given file
    will be used and no further processors will be applied after that.
    """

    children = _get_resources(dir, PurePath(), processors, repo)

    return Resource(
        name=dir.path.name,
        path=PurePath(),
        src_path=dir.path,
        type="repo",
        metadata={},
        children=children,
        content=None,
        last_modified=max(child.last_modified for child in children)
        if children
        else datetime.now(),
    )
