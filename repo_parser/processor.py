import re
from dataclasses import dataclass

import frontmatter


@dataclass
class Processor:
    """
    Processor class to process files based on a pattern.
    """

    pattern: re.Pattern
    process: callable
    read_content: bool


def _process_markdown(file_contents: str):
    metadata, _ = frontmatter.parse(file_contents)

    filetype = metadata.get("type", "file")
    metadata.pop("type", None)  # remove "type" from the metadata

    return filetype, metadata, file_contents


# default processors: not exported as it's probably almost never what you want
# in a production system
DEFAULT_PROCESSORS = [
    Processor(re.compile("\.md$"), _process_markdown, True),
]
