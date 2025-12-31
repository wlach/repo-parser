import re
from collections.abc import Callable
from dataclasses import dataclass


@dataclass
class Processor:
    """
    Processor class to process files based on a pattern.
    """

    pattern: re.Pattern
    process: Callable
    read_content: bool
