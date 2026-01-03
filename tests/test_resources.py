import os
import re
import tempfile
from datetime import datetime
from pathlib import Path, PurePath

import git
import pytest

from repo_parser.processor import Processor
from repo_parser.resource import _get_last_modified_batch, get_resources


def test_get_resources(simple_filesystem, default_processors):
    processors = [
        *default_processors,
        Processor(
            re.compile(r"Makefile"), lambda content: ("file", {}, content), False
        ),
    ]
    dir, repo = simple_filesystem
    result = get_resources(repo, dir, processors)

    # Check structure without comparing exact datetime values
    assert result.name == "test"
    assert result.type == "repo"
    assert isinstance(result.last_modified, datetime)
    assert len(result.children) == 2

    # Find the README and service-example resources
    readme = next(r for r in result.children if r.name == "README.md")
    service = next(r for r in result.children if r.name == "service-example")

    assert readme.type == "file"
    assert isinstance(readme.last_modified, datetime)

    assert service.type == "service"
    assert isinstance(service.last_modified, datetime)
    assert len(service.children) == 3

    for child in service.children:
        assert isinstance(child.last_modified, datetime)


def test_directory_last_modified_from_children(simple_filesystem, default_processors):
    """Test that directory resources get last_modified from their children"""
    processors = [
        *default_processors,
        Processor(
            re.compile(r"Makefile"), lambda content: ("file", {}, content), False
        ),
    ]
    dir, repo = simple_filesystem
    result = get_resources(repo, dir, processors)

    # Find the service-example directory resource
    service = next(r for r in result.children if r.name == "service-example")

    # The service directory's last_modified should be the max of all its children
    # (including the README.md that defined it as a service)
    child_dates = [child.last_modified for child in service.children]
    assert service.last_modified == max(child_dates)


def test_repo_last_modified_from_all_descendants(simple_filesystem, default_processors):
    """Test that the repo resource gets last_modified from all descendants"""
    processors = [
        *default_processors,
        Processor(
            re.compile(r"Makefile"), lambda content: ("file", {}, content), False
        ),
    ]
    dir, repo = simple_filesystem
    result = get_resources(repo, dir, processors)

    # Collect all dates from all resources recursively
    def collect_dates(resource):
        dates = [resource.last_modified]
        for child in resource.children:
            dates.extend(collect_dates(child))
        return dates

    all_dates = []
    for child in result.children:
        all_dates.extend(collect_dates(child))

    # The repo's last_modified should be the max of all its descendants
    assert result.last_modified == max(all_dates)


def test_get_last_modified_batch_empty_list():
    """Test _get_last_modified_batch with empty file list"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        repo = git.Repo.init(tmpdir)
        # Create a file to make initial commit
        (tmpdir / "dummy.txt").write_text("dummy")
        repo.index.add(["dummy.txt"])
        repo.index.commit("initial commit")

        result = _get_last_modified_batch(repo, [])
        assert result == {}


def test_get_last_modified_batch_single_file():
    """Test _get_last_modified_batch with a single file"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        repo = git.Repo.init(tmpdir)

        # Create a file and commit it with a specific timestamp
        test_file = tmpdir / "test.md"
        test_file.write_text("test content")
        repo.index.add(["test.md"])

        # Set a specific commit date (2024-01-15 10:30:00 UTC)
        fixed_timestamp = 1705324200
        fixed_datetime = datetime.fromtimestamp(fixed_timestamp)

        # Set environment variables for git commit date
        old_author_date = os.environ.get("GIT_AUTHOR_DATE")
        old_committer_date = os.environ.get("GIT_COMMITTER_DATE")
        try:
            os.environ["GIT_AUTHOR_DATE"] = f"{fixed_timestamp} +0000"
            os.environ["GIT_COMMITTER_DATE"] = f"{fixed_timestamp} +0000"
            repo.index.commit("test commit")
        finally:
            # Restore original environment
            if old_author_date is not None:
                os.environ["GIT_AUTHOR_DATE"] = old_author_date
            elif "GIT_AUTHOR_DATE" in os.environ:
                del os.environ["GIT_AUTHOR_DATE"]
            if old_committer_date is not None:
                os.environ["GIT_COMMITTER_DATE"] = old_committer_date
            elif "GIT_COMMITTER_DATE" in os.environ:
                del os.environ["GIT_COMMITTER_DATE"]

        result = _get_last_modified_batch(repo, [PurePath("test.md")])

        assert len(result) == 1
        assert PurePath("test.md") in result
        assert isinstance(result[PurePath("test.md")], datetime)

        # Verify we got the exact commit timestamp, not datetime.now()
        assert result[PurePath("test.md")] == fixed_datetime, (
            f"Expected timestamp {fixed_datetime}, got {result[PurePath('test.md')]}. "
            f"If result is very recent, this suggests datetime.now() was returned instead."
        )


def test_get_last_modified_batch_multiple_files():
    """Test _get_last_modified_batch with multiple files"""
    import os

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        repo = git.Repo.init(tmpdir)

        # Create multiple files
        (tmpdir / "file1.md").write_text("content 1")
        (tmpdir / "file2.md").write_text("content 2")
        (tmpdir / "file3.txt").write_text("content 3")

        repo.index.add(["file1.md", "file2.md", "file3.txt"])

        # Set a specific commit date (2024-01-15 10:30:00 UTC)
        fixed_timestamp = 1705324200
        fixed_datetime = datetime.fromtimestamp(fixed_timestamp)

        # Set environment variables for git commit date
        old_author_date = os.environ.get("GIT_AUTHOR_DATE")
        old_committer_date = os.environ.get("GIT_COMMITTER_DATE")
        try:
            os.environ["GIT_AUTHOR_DATE"] = f"{fixed_timestamp} +0000"
            os.environ["GIT_COMMITTER_DATE"] = f"{fixed_timestamp} +0000"
            repo.index.commit("test commit")
        finally:
            # Restore original environment
            if old_author_date is not None:
                os.environ["GIT_AUTHOR_DATE"] = old_author_date
            elif "GIT_AUTHOR_DATE" in os.environ:
                del os.environ["GIT_AUTHOR_DATE"]
            if old_committer_date is not None:
                os.environ["GIT_COMMITTER_DATE"] = old_committer_date
            elif "GIT_COMMITTER_DATE" in os.environ:
                del os.environ["GIT_COMMITTER_DATE"]

        file_paths = [
            PurePath("file1.md"),
            PurePath("file2.md"),
            PurePath("file3.txt"),
        ]

        result = _get_last_modified_batch(repo, file_paths)

        assert len(result) == len(file_paths)
        for file_path in file_paths:
            assert file_path in result
            assert isinstance(result[file_path], datetime)

            # Verify we got the exact commit timestamp, not datetime.now()
            assert result[file_path] == fixed_datetime, (
                f"Expected timestamp {fixed_datetime} for {file_path}, "
                f"got {result[file_path]}. "
                f"If result is very recent, this suggests datetime.now() was returned instead."
            )


def test_get_last_modified_batch_file_without_history():
    """Test _get_last_modified_batch with a file that has no git history"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        repo = git.Repo.init(tmpdir)
        # Create initial commit
        (tmpdir / "dummy.txt").write_text("dummy")
        repo.index.add(["dummy.txt"])
        repo.index.commit("initial commit")

        # Create a file but don't commit it
        new_file = tmpdir / "new_file.md"
        new_file.write_text("new content")

        result = _get_last_modified_batch(repo, [PurePath("new_file.md")])

        assert len(result) == 1
        assert PurePath("new_file.md") in result
        # Should return datetime.now() for files with no history
        # We can't check exact value, but it should be very recent
        assert isinstance(result[PurePath("new_file.md")], datetime)


def test_get_last_modified_batch_absolute_paths(simple_filesystem):
    """Test _get_last_modified_batch with absolute paths"""
    _, repo = simple_filesystem
    repo_root = Path(repo.working_dir)

    # Use absolute paths
    file_paths = [
        PurePath(repo_root / "README.md"),
    ]

    result = _get_last_modified_batch(repo, file_paths)

    assert len(result) == 1
    assert file_paths[0] in result
    assert isinstance(result[file_paths[0]], datetime)


def test_get_last_modified_batch_path_outside_repo():
    """Test _get_last_modified_batch raises error for paths outside repo"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        repo = git.Repo.init(tmpdir)
        # Create initial commit
        (tmpdir / "dummy.txt").write_text("dummy")
        repo.index.add(["dummy.txt"])
        repo.index.commit("initial commit")

        # Create a file outside the repo
        with tempfile.TemporaryDirectory() as outside_dir:
            outside_file = Path(outside_dir) / "outside.md"
            outside_file.write_text("content")

            # Should raise ValueError from pathlib.Path.relative_to()
            with pytest.raises(ValueError):
                _get_last_modified_batch(repo, [PurePath(outside_file)])
