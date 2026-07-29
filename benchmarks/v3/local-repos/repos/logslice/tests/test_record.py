from datetime import datetime, timedelta, timezone

import pytest

from logslice.record import LogRecord, display_timestamp, normalize_timestamp, parse_timestamp


def test_record_normalizes_level_and_naive_timestamp() -> None:
    record = LogRecord(datetime(2025, 1, 2, 3, 4, 5), "warning", "disk nearly full")

    assert record.level == "WARNING"
    assert record.timestamp == datetime(2025, 1, 2, 3, 4, 5, tzinfo=timezone.utc)


def test_record_rejects_empty_message() -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        LogRecord(datetime.now(timezone.utc), "INFO", "")


def test_normalize_timestamp_converts_to_utc() -> None:
    original = datetime(2025, 1, 2, 11, 4, 5, tzinfo=timezone(timedelta(hours=8)))

    assert normalize_timestamp(original) == datetime(2025, 1, 2, 3, 4, 5, tzinfo=timezone.utc)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("2025-01-02T03:04:05", datetime(2025, 1, 2, 3, 4, 5, tzinfo=timezone.utc)),
        ("2025-01-02T03:04:05Z", datetime(2025, 1, 2, 3, 4, 5, tzinfo=timezone.utc)),
        ("2025-01-02T11:04:05+08:00", datetime(2025, 1, 2, 3, 4, 5, tzinfo=timezone.utc)),
    ],
)
def test_parse_timestamp_normalizes_supported_forms(raw: str, expected: datetime) -> None:
    assert parse_timestamp(raw) == expected


def test_display_timestamp_uses_zulu_suffix() -> None:
    value = datetime(2025, 1, 2, 11, 4, 5, tzinfo=timezone(timedelta(hours=8)))

    assert display_timestamp(value) == "2025-01-02T03:04:05Z"
