"""Hidden verifier for tinyconfig T01; run with the candidate repo as argv[1]."""

from __future__ import annotations

import sys
from pathlib import Path


def main(repo: Path) -> None:
    sys.path.insert(0, str(repo))
    from tinyconfig import ConfigError, load_settings

    true_values = ("true", " TRUE ", "1", "yes", "ON")
    false_values = ("false", " False ", "0", "no", "off")
    for value in true_values:
        assert load_settings({"APP_DEBUG": value}).debug is True
    for value in false_values:
        assert load_settings({"APP_DEBUG": value}).debug is False
    assert load_settings({}).debug is False
    try:
        load_settings({"APP_DEBUG": "perhaps"})
    except ConfigError as error:
        assert "APP_DEBUG" in str(error)
    else:
        raise AssertionError("unsupported APP_DEBUG must raise ConfigError")


if __name__ == "__main__":
    main(Path(sys.argv[1]).resolve())
