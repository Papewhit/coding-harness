"""Hidden verifier for T05: ready-at-now work is FIFO and limit-aware."""

from __future__ import annotations

import sys


def main(root: str) -> None:
    sys.path.insert(0, root)
    from miniqueue import MiniQueue

    queue = MiniQueue()
    queue.enqueue("late", {}, available_at=8)
    queue.enqueue("first", {}, available_at=5)
    queue.enqueue("second", {}, available_at=5)
    queue.enqueue("future", {}, available_at=9)
    assert [job.id for job in queue.pending(5, limit=2)] == ["first", "second"]
    assert [job.id for job in queue.pending(8, limit=3)] == ["first", "second", "late"]
    assert queue.pending(8, limit=0) == []


if __name__ == "__main__":
    main(sys.argv[1])
