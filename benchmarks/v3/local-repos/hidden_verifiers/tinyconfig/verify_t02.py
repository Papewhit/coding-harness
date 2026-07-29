"""Hidden verifier for tinyconfig T02; run with the candidate repo as argv[1]."""

from __future__ import annotations

import sys
from pathlib import Path


def main(repo: Path) -> None:
    sys.path.insert(0, str(repo))
    from tinyconfig import ConfigError, load_settings

    nested = {"app": {"debug": "true"}, "database": {"host": "db.internal", "port": "15432"}}
    settings = load_settings(nested)
    assert (settings.debug, settings.database_host, settings.database_port) == (True, "db.internal", 15432)
    overridden = dict(nested, DATABASE_HOST="flat.example")
    assert load_settings(overridden).database_host == "flat.example"
    assert load_settings({"database": {"host": "only-host"}}).database_port == 5432
    try:
        load_settings({"database": "not-a-mapping"})
    except ConfigError as error:
        assert "database" in str(error)
    else:
        raise AssertionError("malformed database section must raise ConfigError")


if __name__ == "__main__":
    main(Path(sys.argv[1]).resolve())
