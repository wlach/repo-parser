"""
A library for extracting metadata out of a source repository.
"""

__version__ = "0.0.2"

from .filesystem import scan
from .processor import Processor
from .resource import Resource, get_resources

__all__ = [
    "Processor",
    "Resource",
    "get_resources",
    "scan",
]
