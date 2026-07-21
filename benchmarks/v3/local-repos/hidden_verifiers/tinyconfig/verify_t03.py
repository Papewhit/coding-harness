"""Hidden verifier for tinyconfig T03; run with the candidate repo as argv[1]."""

from __future__ import annotations

import sys
from pathlib import Path


def assert_safe_error(load_settings, config_error, secret: str) -> None:
    try:
        load_settings({"DATABASE_PORT": secret})
    except config_error as error:
        message = str(error)
        assert "DATABASE_PORT" in message
        assert secret not in message
        assert error.__cause__ is not None
    else:
        raise AssertionError("invalid port must raise ConfigError")


def main(repo: Path) -> None:
    sys.path.insert(0, str(repo))
    from tinyconfig import ConfigError, load_settings

    assert load_settings({"DATABASE_PORT": "1"}).database_port == 1
    assert load_settings({"DATABASE_PORT": "65535"}).database_port == 65535
    assert_safe_error(load_settings, ConfigError, "db-password=unforgettable")
    try:
        load_settings({"DATABASE_PORT": "70000"})
    except ConfigError as error:
        assert "DATABASE_PORT" in str(error)
        assert "70000" not in str(error)
    else:
        raise AssertionError("out-of-range port must raise ConfigError")


if __name__ == "__main__":
    main(Path(sys.argv[1]).resolve())
