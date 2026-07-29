"""Hidden verifier for T04: retry_limit counts retries after the first lease."""

from __future__ import annotations

import sys


def main(root: str) -> None:
    sys.path.insert(0, root)
    from miniqueue import MiniQueue

    queue = MiniQueue()
    queue.enqueue("report", {"kind": "daily"}, retry_limit=2)
    assert queue.claim(1) is not None
    assert queue.fail("report", 1, retry_delay=1).state == "pending"
    assert queue.claim(3) is not None
    assert queue.fail("report", 3, retry_delay=1).state == "pending"
    assert queue.claim(5) is not None
    assert queue.fail("report", 5).state == "failed"
    assert queue.get("report").attempts == 3


if __name__ == "__main__":
    main(sys.argv[1])
