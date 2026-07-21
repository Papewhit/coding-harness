"""Hidden verifier for T06: a lease expires exactly at its lease deadline."""

from __future__ import annotations

import sys


def main(root: str) -> None:
    sys.path.insert(0, root)
    from miniqueue import MiniQueue

    queue = MiniQueue()
    queue.enqueue("invoice", {"amount": 11}, available_at=0)
    leased = queue.claim(4, lease_seconds=6)
    assert leased is not None
    assert queue.reclaim_expired(10) == [leased]
    restored = queue.get("invoice")
    assert restored.state == "pending"
    assert restored.lease_until is None
    assert restored.available_at == 10
    assert restored.attempts == 1
    assert restored.payload == {"amount": 11}
    assert queue.claim(11) is restored


if __name__ == "__main__":
    main(sys.argv[1])
