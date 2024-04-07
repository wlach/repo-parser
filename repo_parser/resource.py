from dataclasses import dataclass
from pathlib import PurePath
from typing import List, Optional

from .filesystem import Dir
from .processor import Processor


@dataclass
class Resource:
    name: str
    src_path: PurePath
    path: PurePath
    type: str
    metadata: dict
    content: Optional[str]
    children: List["Resource"]


def _get_resources(
    dir: Dir, parent_path: PurePath, processors: List[Processor]
) -> List[Resource]:
    child_resources: List[Resource] = []
    dir_resource: Optional[Resource] = None

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
                    )
                )
                # Will only match once!
                break

    for subdir in dir.dirs:
        child_resources.extend(
            _get_resources(subdir, parent_path / subdir.path.name, processors)
        )

    # if this directory did not define a new resource, append any newly
    # found resources to the parent
    if dir_resource is None:
        return child_resources

    # otherwise, add the child resources to the dir_resource, and return that
    dir_resource.children = child_resources
    return [dir_resource]


def get_resources(dir: Dir, processors: List[Processor]) -> Resource:
    return Resource(
        name=dir.path.name,
        path=PurePath(),
        src_path=dir.path,
        type="repo",
        metadata={},
        children=_get_resources(dir, PurePath(), processors),
        content=None,
    )
