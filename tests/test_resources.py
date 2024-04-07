import re
from pathlib import PurePath

from pytest_unordered import unordered

from repo_parser.processor import Processor
from repo_parser.resource import Resource, get_resources


def test_get_resources(simple_filesystem, default_processors):
    processors = [
        *default_processors,
        Processor(
            re.compile(r"Makefile"), lambda content: ("file", {}, content), False
        ),
    ]
    assert get_resources(simple_filesystem, processors) == Resource(
        name="test",
        path=PurePath(),
        src_path=PurePath("test"),
        type="repo",
        metadata={},
        content=None,
        children=unordered(
            [
                Resource(
                    name="README.md",
                    path=PurePath("README.md"),
                    src_path=PurePath("README.md"),
                    type="file",
                    content="This is a test",
                    metadata={},
                    children=[],
                ),
                Resource(
                    name="service-example",
                    path=PurePath(),
                    src_path=PurePath("test/service-example"),
                    type="service",
                    content=None,
                    metadata={"language": "python"},
                    children=[
                        Resource(
                            name="README.md",
                            path=PurePath("README.md"),
                            src_path=PurePath("test/service-example/README.md"),
                            type="file",
                            content="---\ntype: service\nlanguage: python\n---\nThis is a service",
                            metadata={"language": "python"},
                            children=[],
                        ),
                        Resource(
                            name="Makefile",
                            path=PurePath("Makefile"),
                            src_path=PurePath("test/service-example/Makefile"),
                            type="file",
                            content=None,
                            metadata={},
                            children=[],
                        ),
                        Resource(
                            name="testing.md",
                            path=PurePath("docs/testing.md"),
                            src_path=PurePath("test/service-example/docs/testing.md"),
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
