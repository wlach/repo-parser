import re
from pathlib import Path, PurePath

import frontmatter
import pytest

from repo_parser.filesystem import Dir, File, Processor


@pytest.fixture
def default_processors():
    def _process_markdown(file_contents: str):
        metadata, _ = frontmatter.parse(file_contents)

        filetype = metadata.get("type", "file")
        metadata.pop("type", None)  # remove "type" from the metadata

        return filetype, metadata, file_contents

    return [
        Processor(re.compile("\.md$"), _process_markdown, True),
    ]


@pytest.fixture
def example_dir():
    return Path(__file__).parent / "example"


@pytest.fixture
def simple_filesystem():
    return Dir(
        path=PurePath("test"),
        files=[
            File(
                name="README.md",
                src_path=PurePath("README.md"),
                content="This is a test",
            ),
        ],
        dirs=[
            Dir(
                path=PurePath("test") / "service-example",
                files=[
                    File(
                        name="README.md",
                        src_path=PurePath("test") / "service-example" / "README.md",
                        content="---\ntype: service\nlanguage: python\n---\nThis is a service",
                    ),
                    File(
                        name="service.py",
                        src_path=PurePath("test") / "service-example" / "service.py",
                        content="print('hello world')",
                    ),
                    File(
                        name="Makefile",
                        src_path=PurePath("test") / "service-example" / "Makefile",
                        content=None,  # Presuming Makefile content is not read
                    ),
                ],
                dirs=[
                    Dir(
                        path=PurePath("test") / "service-example" / "docs",
                        files=[
                            File(
                                name="testing.md",
                                src_path=PurePath("test")
                                / "service-example"
                                / "docs"
                                / "testing.md",
                                content="Something about testing",
                            ),
                        ],
                        dirs=[],
                    )
                ],
            )
        ],
    )
