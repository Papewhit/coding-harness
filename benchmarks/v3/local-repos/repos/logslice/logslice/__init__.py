"""Small, dependency-free log line utilities."""

from .formatter import format_record
from .record import LogRecord, parse_timestamp

__all__ = ["LogRecord", "format_record", "parse_timestamp"]
