from pathlib import PurePath

from pytest_unordered import unordered

from repo_parser.processor import DEFAULT_PROCESSORS
from repo_parser.resource import Resource, get_resources


def test_get_resources(simple_filesystem):
    assert get_resources(simple_filesystem, DEFAULT_PROCESSORS) == Resource(
        name="test",
        path=PurePath(),
        type="repo",
        metadata={},
        content=None,
        children=unordered(
            [
                Resource(
                    name="README.md",
                    path=PurePath("README.md"),
                    type="file",
                    content="This is a test",
                    metadata={},
                    children=[],
                ),
                Resource(
                    name="service-example",
                    path=PurePath(),
                    type="service",
                    content=None,
                    metadata={"language": "python"},
                    children=[
                        Resource(
                            name="README.md",
                            path=PurePath("README.md"),
                            type="file",
                            content="---\ntype: service\nlanguage: python\n---\nThis is a service",
                            metadata={"language": "python"},
                            children=[],
                        ),
                        Resource(
                            name="testing.md",
                            path=PurePath("docs/testing.md"),
                            type="file",
                            content="Something about testing",
                            metadata={},
                            children=[],
                        ),
                    ],
                ),
            ]
        ),
    )
