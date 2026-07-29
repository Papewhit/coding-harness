# T06 — Expired lease reclaim

Fix `MiniQueue.reclaim_expired()` so a lease is reclaimable exactly when
`now == lease_until`, not only after that instant. Reclamation must preserve
the job payload and attempt count while clearing the lease and making the job
claimable at `now`.

Run `python hidden_verifiers/miniqueue/verify_t06_expired_lease_reclaim.py <repo>`
against a fresh working copy of the repository.
