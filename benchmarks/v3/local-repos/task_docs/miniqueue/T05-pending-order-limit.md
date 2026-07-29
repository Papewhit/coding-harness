# T05 — Pending order and limit

Fix `MiniQueue.pending()` so work whose `available_at` equals `now` is ready.
Keep the existing ascending availability and FIFO ordering, and preserve
correct `limit` behavior including `limit=0`. Do not change the public API.

Run `python hidden_verifiers/miniqueue/verify_t05_pending_order_limit.py <repo>`
against a fresh working copy of the repository.
