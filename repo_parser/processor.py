import re
from dataclasses import dataclass

import frontmatter


@dataclass
class Processor:
    pattern: re.Pattern
    process: callable
    read_content: bool


def _parse_markdown(file_contents: str):
    metadata, _ = frontmatter.parse(file_contents)

    filetype = metadata.get("type", "file")
    metadata.pop("type", None)  # remove "type" from the metadata

    return filetype, metadata, file_contents


DEFAULT_PROCESSORS = [
    Processor(re.compile("\.md$"), _parse_markdown, True),
]
