# Current Evaluation State

- **Control revision:** `eval-control-v4`
- **Updated at:** `2026-07-24`
- **Current Wave:** `W6R4`
- **Wave state:** `waiting`
- **Waiting reason:** `user_decision`
- **Current objective:** Authorize and execute profile reselection from the accepted W6R3 source, then run one newly authorized human smoke for the selected profile.
- **Source SHA:** `cffe1bd0344eb66d218c2e24cae19fca63b2cbf0`
- **Candidate SHA:** `none`

## Gates

| Gate | State | Binding / reason |
|---|---|---|
| `native_eval_ready` | `pending` | W6R3 deterministic recovery passed; W6R4 reselection and an accepted authorized human smoke have not run. |
| `native_resume_ready` | `pending` | `TOOL-062-G` has not run. |

## Current Wave Tickets

W6R4 has no Tickets. The `integrator` performs the Wave steps directly and starts local Processes where required.

## Open Findings

None.

## Next action

`program_supervisor` authorizes W6R4 live provider HTTP under the existing frozen cases/criteria, identifies the permitted configured profiles or permits all configured candidates, provides the private config locator value out of band, and confirms the Artifact root plus frozen attempts/retry/budget; control files persist only the public locator environment-variable name and authorization confirmation.

## Human review

- **Source diff:** `not_applicable`
- **Changed source files:** `none`
- **Summary path:** `none until W6R4 smoke completes`

## Authoritative references

- **Current Wave procedure:** `.codex/eval/waves/W6R4-profile-reselection-human-smoke.md`
- **Latest Wave handoff:** `.codex/eval/state/W6R3-wave-handoff-r2.json` (`sha256:521b1f3e30c393cbefd449cbff5057992cdca3167a327ec612532cc7335c8823`)
- **Accepted source tree:** `5ebb6a2cd62e96753fe3502a3b5846319db7386f`
- **Freeze:** `.codex/eval/state/FREEZE.json` (`sha256:4ca55e089cbf34acf60d33c88d17dcf9819f216acb09e5c99ad72464ef7d9a85`)
- **W6R3 Gate Artifact:** `F:\dev\llm\pico-eval-artifacts\native-deterministic-gate\W6R3-TOOL-059-G-02`
