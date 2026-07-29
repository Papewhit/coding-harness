"""Small, deterministic queue primitives.

The module deliberately avoids clocks, threads, and external services so task
fixtures can exercise queue edge cases entirely offline.  Callers provide an
integer timestamp to every operation that needs one.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class Job:
    """One unit of work stored by :class:`MiniQueue`.

    ``attempts`` counts successful leases, including the original lease.
    ``retry_limit`` is the number of retries allowed after that original
    lease.  A failed job is either returned to ``pending`` or made terminal.
    """

    id: str
    payload: dict[str, Any]
    available_at: int
    retry_limit: int = 0
    attempts: int = 0
    state: str = "pending"
    lease_until: int | None = None
    sequence: int = field(default=0, repr=False)


class MiniQueue:
    """An in-memory queue with delayed work, leases, and retries.

    The public API intentionally stays small:

    * :meth:`enqueue` records pending work.
    * :meth:`claim` leases the next available pending job.
    * :meth:`fail` schedules another attempt or makes a job terminal.
    * :meth:`reclaim_expired` returns expired leases to the pending queue.
    * :meth:`pending` exposes pending jobs for administrative inspection.
    """

    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._next_sequence = 0

    def enqueue(
        self,
        job_id: str,
        payload: dict[str, Any],
        *,
        available_at: int = 0,
        retry_limit: int = 0,
    ) -> Job:
        """Add a job and reject duplicate identifiers."""
        if job_id in self._jobs:
            raise ValueError(f"duplicate job id: {job_id}")
        if retry_limit < 0:
            raise ValueError("retry_limit must be non-negative")
        job = Job(
            id=job_id,
            payload=dict(payload),
            available_at=available_at,
            retry_limit=retry_limit,
            sequence=self._next_sequence,
        )
        self._jobs[job_id] = job
        self._next_sequence += 1
        return job

    def get(self, job_id: str) -> Job:
        """Return a stored job by identifier."""
        return self._jobs[job_id]

    def pending(self, now: int, *, limit: int | None = None) -> list[Job]:
        """List work ready to be leased at ``now``.

        Jobs with the same availability time retain their insertion order.
        ``limit`` truncates the ordered result; a negative value is rejected.
        """
        if limit is not None and limit < 0:
            raise ValueError("limit must be non-negative")
        ready = [
            job
            for job in self._jobs.values()
            if job.state == "pending" and job.available_at < now
        ]
        ready.sort(key=lambda job: (job.available_at, job.sequence))
        return ready if limit is None else ready[:limit]

    def claim(self, now: int, *, lease_seconds: int = 30) -> Job | None:
        """Lease the first pending job, or return ``None`` when none is ready."""
        if lease_seconds <= 0:
            raise ValueError("lease_seconds must be positive")
        candidates = self.pending(now, limit=1)
        if not candidates:
            return None
        job = candidates[0]
        job.state = "leased"
        job.lease_until = now + lease_seconds
        job.attempts += 1
        return job

    def complete(self, job_id: str) -> Job:
        """Mark a leased job complete."""
        job = self.get(job_id)
        if job.state != "leased":
            raise ValueError("only leased jobs can complete")
        job.state = "complete"
        job.lease_until = None
        return job

    def fail(self, job_id: str, now: int, *, retry_delay: int = 0) -> Job:
        """Fail a lease and either retry it later or make it terminal."""
        job = self.get(job_id)
        if job.state != "leased":
            raise ValueError("only leased jobs can fail")
        if retry_delay < 0:
            raise ValueError("retry_delay must be non-negative")
        job.lease_until = None
        if job.attempts >= job.retry_limit:
            job.state = "failed"
        else:
            job.state = "pending"
            job.available_at = now + retry_delay
        return job

    def reclaim_expired(self, now: int) -> list[Job]:
        """Return leases that expired before ``now`` to the pending queue."""
        reclaimed: list[Job] = []
        for job in self._jobs.values():
            if job.state == "leased" and job.lease_until is not None and job.lease_until < now:
                job.state = "pending"
                job.available_at = now
                job.lease_until = None
                reclaimed.append(job)
        return reclaimed
