# Get last modified in bulk

Owner: Will Lachance <wlach@protonmail.com>

## Overview

### Problem Statement

Improve speed of repo-parser when working on larger repositories

### Context (as needed)

Currently, `repo-parser` calls `repo.iter_commits()` once per file via `_get_last_modified()` in `resource.py` to get last commit dates. For repositories with hundreds or thousands of files, this results in hundreds/thousands of separate git operations, each with overhead from spawning git processes and parsing output.

This scales linearly with the number of files and becomes prohibitively slow on larger repositories. The overhead of spawning git processes and parsing output accumulates across all these individual calls.

### Goals

- Improve speed of repo parser on larger repositories

### Non-Goals

N/A

### Proposed Solution

Collect all file paths during resource creation, then make a single batched `git log` call to retrieve all last-modified dates at once. Parse the output to build a file path → timestamp mapping, which is used as a cache when creating Resource objects.

This reduces hundreds/thousands of individual `repo.iter_commits()` calls to just 1 batched call (or a small number if chunking is needed for very large file sets).

## Alternatives considered (as needed)

- Switch to pygit which uses libgit. Rejected initially because
  it's likely to have similar bottlenecks. May be considered in future.

## Future plans (as needed)

Switch to pygit, maybe?

## Other reading (as needed)

N/A

## Implementation (ephemeral)

### Implementation Plan

#### Phase 1: Create batched git query function for commit dates

1. **Add `_get_last_modified_batch()` function in `resource.py`**

   - Accepts `repo: git.Repo`, `file_paths: list[PurePath]`, and optional `scan_root: Path | None`
   - Returns `dict[PurePath, datetime]` mapping file paths to their last commit dates
   - Converts all `file_paths` to relative paths using `pathlib.Path.relative_to(repo.working_dir)` (git log needs paths relative to repo root)
   - Uses `scan_root` parameter to resolve relative paths (if provided, relative paths are resolved against this root; otherwise against current working directory or repo root)
   - Uses `repo.git.log()` with format `--format="%ct" --name-only -- <paths>` to get commit timestamps and affected files
   - Processes in chunks using `LAST_MODIFIED_CHUNK_SIZE` constant (200 files per chunk) to avoid command-line length limits
   - Handles files with no git history (returns `datetime.now()` in the cache)
   - Note: May raise `git.GitCommandError` if git log fails (exceptions propagate naturally)

2. **Implementation approach for git log parsing:**
   - Use `git log --format="%ct" --name-only -- <paths>` (no `--all` flag to match current `iter_commits` behavior)
   - Parse output line by line: the format is `timestamp\n<blank>\nfile1\nfile2\n...\n<blank>\n`
   - Track the most recent commit timestamp for each file path
   - Normalize file paths from git output (they'll be relative to repo root) and match them back to the input `PurePath` objects
   - Convert timestamps to `datetime` objects using `datetime.fromtimestamp()`
   - Build result dict using normalized paths as keys (matching the normalized input paths)

#### Phase 2: Batch commit date queries

**Modify `get_resources()` to batch query commit dates:**

1. **Create resources and collect file paths (single walk):**

   - Call `_get_resources()` with an optional `file_paths` list parameter
   - As `_get_resources()` creates file resources, it collects their `src_path` values into the list
   - This combines resource creation and path collection in a single walk of the Dir tree
   - Resources are created with placeholder `datetime.now()` dates

2. **Batch query commit dates:**

   - Call `_get_last_modified_batch()` with all collected file paths and `scan_root=dir.path` to get commit dates in one operation
   - Pass `dir.path` as `scan_root` since `file.src_path` values are relative to the scan root
   - This returns a `dict[PurePath, datetime]` cache

3. **Apply cached dates:**
   - Add `_apply_last_modified_cache()` function that recursively applies cached dates to Resource tree
   - Updates file resources with dates from cache
   - Updates directory resources to be max of their children (after children are updated)
   - Call this function on the root resource after creation

#### Phase 3: Testing and validation

1. **Update existing tests:**

   - Ensure `test_get_resources()` still passes
   - Ensure `test_directory_last_modified_from_children()` still passes
   - Ensure `test_repo_last_modified_from_all_descendants()` still passes

2. **Add new tests:**

   - Test `_get_last_modified_batch()` with various file sets
   - Test with files that have no git history
   - Test with empty file list
   - Test chunking behavior for large file sets

3. **Performance validation:**
   - Run `example_parser.py` on a larger repository and measure time improvement
   - Compare before/after using `time` command or Python profiling

### Implementation Checklist

- [x] Implement `_get_last_modified_batch()` function with git log parsing
- [x] Add chunking logic for large file sets using `LAST_MODIFIED_CHUNK_SIZE` constant (200 files per chunk)
- [x] Modify `_get_resources()` to accept optional `file_paths` parameter for collecting paths
- [x] Modify `_get_resources()` to accept optional `file_paths` parameter and collect paths as it creates resources
- [x] Modify `get_resources()` to create resources and collect paths in one walk
- [x] Modify `get_resources()` to call `_get_last_modified_batch()` with all paths
- [x] Add `_apply_last_modified_cache()` function to apply cached dates to Resource tree
- [x] Modify `get_resources()` to apply cached dates after resource creation
- [x] Add tests for batch function
- [x] Update existing tests to ensure they still pass
- [ ] Test on larger repository to validate performance improvement
- [ ] Compare before/after performance metrics

### Code Structure Changes

**`repo_parser/resource.py`:**

- Add `LAST_MODIFIED_CHUNK_SIZE` constant (200) for chunking batch queries
- Add `_get_last_modified_batch(repo: git.Repo, file_paths: list[PurePath], scan_root: Path | None = None) -> dict[PurePath, datetime]`
  - Converts paths to relative using `repo.working_dir`
  - Uses `scan_root` parameter to resolve relative paths (if provided, relative paths resolved against this root; otherwise against current working directory or repo root)
  - Uses `git log --format="%ct" --name-only` to batch query
  - Processes in chunks using `LAST_MODIFIED_CHUNK_SIZE` constant
  - Returns dict mapping file paths to commit dates (or `datetime.now()` if no history)
  - Note: May raise `ValueError` if path is outside repo root (shouldn't happen in practice)
- Add `_apply_last_modified_cache(resource: Resource, last_modified_cache: dict[PurePath, datetime]) -> None`
  - Recursively applies cached dates to Resource tree
  - Updates file resources with dates from cache
  - Updates directory resources to be max of their children
- Modify `_get_resources()` to accept optional `file_paths: list[PurePath] | None = None` parameter
  - When provided, collects `file.src_path` values as it creates file resources
  - This allows collecting paths during resource creation (single walk of Dir tree)
  - Resources created with placeholder `datetime.now()` dates
- Modify `get_resources()` to:
  - Create resources and collect paths in single walk (via `_get_resources()` with `file_paths` list)
  - Batch query commit dates using `_get_last_modified_batch()` with all collected paths and `scan_root=dir.path`
  - Apply cached dates using `_apply_last_modified_cache()`

### Edge Cases

- Files with no git history (not tracked, or new files): return `datetime.now()` as fallback
- Files that have been renamed (git log may show old paths): should not be a problem right now, but may need `--follow` flag in future
- Very large repositories (may need chunking): chunk using `LAST_MODIFIED_CHUNK_SIZE` constant (200 files per chunk) to avoid command-line length limits
- Empty repositories or repositories with no commits: return `datetime.now()` for all files
- Files outside the repository root: `ValueError` may be raised by `pathlib.Path.relative_to()` - shouldn't happen in practice since all paths come from repo scanning (comment documents this assumption)
- Path normalization: ensure paths from git log output match the normalized input paths (handle path separators, relative vs absolute)
- Git log errors: `git.GitCommandError` may be raised by `repo.git.log()` - exceptions propagate naturally (no custom exception handling needed)
