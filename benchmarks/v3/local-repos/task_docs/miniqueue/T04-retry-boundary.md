# T04 — Retry boundary

`retry_limit` is the number of retry leases allowed after the original lease.
Fix the retry decision in `miniqueue/queue.py` so a job with `retry_limit=2`
can be leased and failed three times in total, becoming terminal only after
the third failure. Preserve the existing validation and API.

Run `python hidden_verifiers/miniqueue/verify_t04_retry_boundary.py <repo>`
against a fresh working copy of the repository.
