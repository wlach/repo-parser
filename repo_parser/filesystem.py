import pathlib
from dataclasses import dataclass
from pathlib import PurePath
from typing import List, Optional

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


def scan(path: pathlib.Path, processors: List[Processor]) -> Dir:
    """
    Scans a directory for files and subdirectories, returning a data
    structure representing the directory tree. Takes in a list of processors
    to figure out which files should be included in the returned tree.

    This step does not do any post-processing of the files, though their
    content is read in if one of their processors requires it.
    """
    dir = Dir(path=pathlib.PurePath(path), files=[], dirs=[])

    for entry in path.iterdir():
        if entry.is_file():
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
            dir.dirs.append(scan(path / entry.name, processors))

    return dir
