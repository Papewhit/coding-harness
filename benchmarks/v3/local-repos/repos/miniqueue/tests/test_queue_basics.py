from __future__ import annotations

import pytest

from miniqueue import MiniQueue


def test_enqueue_copies_payload_and_rejects_duplicate_ids() -> None:
    queue = MiniQueue()
    payload = {"customer": "Ada"}
    job = queue.enqueue("email", payload)
    payload["customer"] = "Grace"

    assert job.payload == {"customer": "Ada"}
    with pytest.raises(ValueError, match="duplicate job id"):
        queue.enqueue("email", {})


def test_enqueue_rejects_negative_retry_limit() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        MiniQueue().enqueue("email", {}, retry_limit=-1)


def test_claim_requires_positive_lease_duration() -> None:
    queue = MiniQueue()
    queue.enqueue("email", {}, available_at=0)

    with pytest.raises(ValueError, match="positive"):
        queue.claim(1, lease_seconds=0)


def test_complete_requires_a_lease() -> None:
    queue = MiniQueue()
    queue.enqueue("email", {})

    with pytest.raises(ValueError, match="leased"):
        queue.complete("email")


def test_fail_requires_a_lease_and_valid_delay() -> None:
    queue = MiniQueue()
    queue.enqueue("email", {})

    with pytest.raises(ValueError, match="leased"):
        queue.fail("email", 1)

    queue.claim(1)
    with pytest.raises(ValueError, match="non-negative"):
        queue.fail("email", 1, retry_delay=-1)


def test_complete_clears_lease() -> None:
    queue = MiniQueue()
    queue.enqueue("email", {})
    leased = queue.claim(1)

    assert leased is not None
    complete = queue.complete("email")
    assert complete.state == "complete"
    assert complete.lease_until is None


def test_pending_rejects_negative_limit() -> None:
    queue = MiniQueue()
    with pytest.raises(ValueError, match="non-negative"):
        queue.pending(1, limit=-1)


def test_reclaim_ignores_active_and_terminal_jobs() -> None:
    queue = MiniQueue()
    queue.enqueue("active", {})
    queue.enqueue("done", {})
    assert queue.claim(1) is not None
    assert queue.claim(1) is not None
    queue.complete("done")

    assert [job.id for job in queue.reclaim_expired(2)] == []
    assert queue.get("active").state == "leased"
    assert queue.get("done").state == "complete"
