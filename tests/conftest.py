from pathlib import Path, PurePath

import pytest

from repo_parser.filesystem import Dir, File


@pytest.fixture
def example_dir():
    return Path(__file__).parent / "example"


@pytest.fixture
def simple_filesystem():
    return Dir(
        path=PurePath("test"),
        files=[
            File(name="README.md", content="This is a test"),
        ],
        dirs=[
            Dir(
                path=PurePath("test") / "service-example",
                files=[
                    File(
                        name="README.md",
                        content="---\ntype: service\nlanguage: python\n---\nThis is a service",
                    ),
                    File(name="service.py", content="print('hello world')"),
                ],
                dirs=[
                    Dir(
                        path=PurePath("test") / "service-example" / "docs",
                        files=[
                            File(name="testing.md", content="Something about testing"),
                        ],
                        dirs=[],
                    )
                ],
            )
        ],
    )
