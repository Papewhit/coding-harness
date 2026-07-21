import logging

import pytest

from logslice.levels import is_enabled, level_number, normalize_level


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("debug", "DEBUG"),
        (" INFO ", "INFO"),
        ("Warning", "WARNING"),
        ("ERROR", "ERROR"),
        ("critical", "CRITICAL"),
    ],
)
def test_normalize_level_accepts_case_and_surrounding_whitespace(raw: str, expected: str) -> None:
    assert normalize_level(raw) == expected


def test_level_number_uses_standard_logging_values() -> None:
    assert level_number("debug") == logging.DEBUG
    assert level_number("critical") == logging.CRITICAL


@pytest.mark.parametrize(
    ("record_level", "minimum_level", "expected"),
    [
        ("DEBUG", "INFO", False),
        ("INFO", "INFO", True),
        ("WARNING", "INFO", True),
        ("ERROR", "CRITICAL", False),
    ],
)
def test_is_enabled_compares_numeric_severity(
    record_level: str, minimum_level: str, expected: bool
) -> None:
    assert is_enabled(record_level, minimum_level) is expected


def test_invalid_level_names_are_explained() -> None:
    with pytest.raises(ValueError, match="unknown log level"):
        normalize_level("verbose")
