import re
from datetime import datetime

from repo_parser.processor import Processor
from repo_parser.resource import get_resources


def test_get_resources(simple_filesystem, default_processors):
    processors = [
        *default_processors,
        Processor(
            re.compile(r"Makefile"), lambda content: ("file", {}, content), False
        ),
    ]
    dir, repo = simple_filesystem
    result = get_resources(dir, processors, repo)

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
    result = get_resources(dir, processors, repo)

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
    result = get_resources(dir, processors, repo)

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
