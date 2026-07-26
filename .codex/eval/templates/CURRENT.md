# Current Evaluation State

- **Control revision:** `eval-control-v4`
- **Updated at:** `<ISO8601>`
- **Current Wave:** `<WAVE_ID>`
- **Wave state:** `not_started|running|waiting|passed|blocked`
- **Waiting reason:** `user_decision|credential_or_access|external_service|none`
- **Current objective:** `<ONE_SENTENCE>`
- **Source SHA:** `<SHA>`
- **Candidate SHA:** `<SHA_OR_NONE>`

## Gates

| Gate | State | Binding / reason |
|---|---|---|
| `native_eval_ready` | `pending|accepted|rejected` | `<PATH/HASH/REASON>` |
| `native_resume_ready` | `pending|accepted|rejected` | `<PATH/HASH/REASON>` |

## Current Wave Tickets

| Ticket | State | Responsible role | Reason / binding | Next action |
|---|---|---|---|---|
| `<ID>` | `pending|running|needs_remediation|accepted|not_applicable|blocked` | `<ROLE>` | `<NOT_APPLICABLE_REASON_AND_BINDING_OR_NONE>` | `<ONE_ACTION>` |

## Open Findings

| Finding | Type | Responsible Ticket | Required action |
|---|---|---|---|
| `<ID>` | `implementation_defect|measurement_defect|evaluation_failure|change_request` | `<ID_OR_NONE>` | `<ONE_ACTION>` |

## Next action

`<ONE_EXACT_ACTION>`

## Human review

- **Source diff:** `<BASE_SHA>..<CANDIDATE_SHA>` or `not_applicable`
- **Changed source files:** `<LIST_OR_NONE>`
- **Summary path:** `<PATH_OR_NONE>`

## Authoritative references

- **Latest Wave handoff:** `<PATH>` (`sha256:<HASH>`)
- **Freeze:** `.codex/eval/state/FREEZE.json` (`sha256:<HASH>`)
- **Artifacts:** `<PATHS_OR_NONE>`
