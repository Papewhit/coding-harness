# miniqueue

`miniqueue` is a deliberately small in-memory queue.  It is a benchmark
fixture, not a production queue: data is not persisted and callers supply
timestamps explicitly.  This keeps every behavior deterministic.

## Lifecycle

Jobs start as `pending`, become `leased` when claimed, and end as either
`complete` or `failed`.  A failed job with remaining retries returns to
`pending`.  A lease may also return to `pending` through reclamation.

## Time semantics

An integer timestamp represents an instant.  Availability and expiry edges
are intentionally tested by this fixture.  `pending()` is an administrative
view and is also used by `claim()`, so their ordering must agree.  Jobs are
ordered first by `available_at`, then by insertion order.

## Retry semantics

The original lease increments `attempts`.  `retry_limit` describes how many
additional leases are permitted after the original one.  A retry delay is
added to the supplied failure timestamp.  Payloads are copied at enqueue so
the queue owns its stored representation.
