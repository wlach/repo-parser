import re
from dataclasses import dataclass


@dataclass
class Processor:
    """
    Processor class to process files based on a pattern.
    """

    pattern: re.Pattern
    process: callable
    read_content: bool
