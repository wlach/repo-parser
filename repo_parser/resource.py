from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PurePath

import git

from .filesystem import Dir
from .processor import Processor

# Chunk size for batch git log queries to avoid command-line length limits
LAST_MODIFIED_CHUNK_SIZE = 200


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


def _get_last_modified_batch(
    repo: git.Repo, file_paths: list[PurePath], scan_root: Path | None = None
) -> dict[PurePath, datetime]:
    """
    Get the last modification dates for multiple files in a single batched git call.

    Args:
        repo: The git repository
        file_paths: List of file paths to query (can be absolute or relative)
        scan_root: Optional root path for resolving relative file paths. If provided,
            relative paths will be resolved against this root. If None, relative paths
            are resolved against the current working directory or repo root.

    Returns:
        Dictionary mapping file paths to their last commit dates. Files with no
        git history will have datetime.now() as their value.

    Raises:
        ValueError: If a file path cannot be converted to a relative path
        git.GitCommandError: If git log command fails (may be raised by repo.git.log)
    """
    if not file_paths:
        return {}

    repo_root = Path(repo.working_dir)
    result: dict[PurePath, datetime] = {}

    # Convert all paths to relative paths and build a mapping
    # We need to map relative paths back to original PurePath objects
    rel_path_to_original: dict[str, PurePath] = {}
    rel_paths: list[str] = []

    for file_path in file_paths:
        # Convert to Path and resolve to absolute path
        path_obj = Path(file_path)
        if path_obj.is_absolute():
            abs_path = path_obj
        else:
            # Try resolving relative path against scan_root (if provided) or current working directory
            if scan_root is not None:
                abs_path = (scan_root / path_obj).resolve()
            else:
                abs_path = path_obj.resolve()

            # If the resolved path is not within the repo root, try resolving against repo root
            try:
                abs_path.relative_to(repo_root)
            except ValueError:
                # Path is not within repo when resolved against scan_root/cwd, try repo root
                abs_path = (repo_root / path_obj).resolve()

        # Note: In normal operation, all paths come from scanning the repository,
        # so they should always be within the repo root. This may raise ValueError
        # if a path is outside the repo, but that shouldn't happen in practice.
        rel_path = str(abs_path.relative_to(repo_root))

        # Normalize path separators (git uses forward slashes)
        rel_path = rel_path.replace("\\", "/")
        rel_path_to_original[rel_path] = file_path
        rel_paths.append(rel_path)

    # Process in chunks to avoid command-line length limits
    for i in range(0, len(rel_paths), LAST_MODIFIED_CHUNK_SIZE):
        chunk = rel_paths[i : i + LAST_MODIFIED_CHUNK_SIZE]
        chunk_set = set(chunk)  # For fast lookup

        # Use git log to get commit timestamps and affected files
        # Format: timestamp\n<blank>\nfile1\nfile2\n...\n<blank>\n
        # Note: This may raise git.GitCommandError if git log fails
        log_output = repo.git.log("--format=%ct", "--name-only", "--", *chunk)

        # Parse the output
        # Format is: timestamp\n<blank>\nfile1\nfile2\n...\n<blank>\n
        lines = log_output.split("\n")
        current_timestamp: int | None = None
        file_timestamps: dict[str, int] = {}

        for line in lines:
            line = line.strip()
            if not line:
                # Blank line separates commits
                continue

            # Check if this is a timestamp (all digits)
            if line.isdigit():
                current_timestamp = int(line)
            elif current_timestamp is not None:
                # This is a file path, normalize it
                file_path_normalized = line.replace("\\", "/")
                if file_path_normalized in chunk_set:
                    # Track the most recent (largest) timestamp for each file
                    if (
                        file_path_normalized not in file_timestamps
                        or file_timestamps[file_path_normalized] < current_timestamp
                    ):
                        file_timestamps[file_path_normalized] = current_timestamp

        # Convert timestamps to datetime and map back to original PurePath objects
        for rel_path in chunk:
            original_path = rel_path_to_original[rel_path]
            if rel_path in file_timestamps:
                result[original_path] = datetime.fromtimestamp(
                    file_timestamps[rel_path]
                )
            else:
                # File has no git history
                result[original_path] = datetime.now()

    return result


def _apply_last_modified_map(
    resource: Resource, last_modified_cache: dict[PurePath, datetime]
) -> None:
    """
    Recursively apply last_modified dates from cache to a Resource tree.

    Updates file resources with dates from the cache, then updates directory
    resources to be the max of their children.
    """
    # Apply to children first (depth-first)
    for child in resource.children:
        _apply_last_modified_map(child, last_modified_cache)

    # Apply to this resource if it's a file
    if resource.type == "file" and resource.src_path in last_modified_cache:
        resource.last_modified = last_modified_cache[resource.src_path]

    # Update directory resources to be max of children
    if resource.children:
        resource.last_modified = max(child.last_modified for child in resource.children)


def _get_resources(
    dir: Dir,
    parent_path: PurePath,
    processors: list[Processor],
    repo: git.Repo,
    file_paths: list[PurePath] | None = None,
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
                            last_modified=datetime.now(),
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
                # Collect file path for batch querying
                if file_paths is not None:
                    file_paths.append(file.src_path)

                child_resources.append(
                    Resource(
                        name=file.name,
                        path=parent_path / file.name,
                        src_path=file.src_path,
                        type="file",
                        metadata=metadata,
                        content=file.content,
                        children=[],
                        last_modified=datetime.now(),
                    )
                )
                # Will only match once!
                break

    for subdir in dir.dirs:
        child_resources.extend(
            _get_resources(
                subdir,
                parent_path / subdir.path.name,
                processors,
                repo,
                file_paths,
            )
        )

    # if this directory did not define a new resource, append any newly
    # found resources to the parent
    if dir_resource is None:
        return child_resources

    # otherwise, add the child resources to the dir_resource, and return that
    dir_resource.children = child_resources

    # Update dir_resource last_modified to be the most recent from all children
    if child_resources:
        dir_resource.last_modified = max(
            child.last_modified for child in child_resources
        )

    return [dir_resource]


def get_resources(repo: git.Repo, dir: Dir, processors: list[Processor]) -> Resource:
    """
    Gets a list of resources from a scanned filesystem.

    Will process each file in the filesystem with the provided processors,
    note that order matters: the first processor that matches a given file
    will be used and no further processors will be applied after that.
    """
    # Collect file paths as we create resources (single pass)
    file_paths: list[PurePath] = []
    children = _get_resources(dir, PurePath(), processors, repo, file_paths)

    # Batch query all commit dates at once
    scan_root = dir.path
    last_modified_map = _get_last_modified_batch(repo, file_paths, scan_root)

    root_resource = Resource(
        name=dir.path.name,
        path=PurePath(),
        src_path=dir.path,
        type="repo",
        metadata={},
        children=children,
        content=None,
        last_modified=datetime.now(),
    )

    # Apply last_modified dates
    _apply_last_modified_map(root_resource, last_modified_map)

    return root_resource
