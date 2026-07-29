# Current Evaluation State

- **Control revision:** `eval-control-v4.2`
- **Updated at:** `2026-07-26`
- **Current Wave:** `W6R5`
- **Wave state:** `blocked`
- **Waiting reason:** `none`
- **Current objective:** W6R5 is closed blocked after the user stopped remediation of the R-03 exact-string Oracle measurement defect.
- **Source SHA:** `e65f370e49fe2ef749e017f33f509997eb1a0cd5`
- **Candidate SHA:** `e65f370e49fe2ef749e017f33f509997eb1a0cd5`
- **Source tree:** `b306d8a29f863b64fcb2a45316a5cee8aa44dc7e`
- **Control baseline SHA:** `f9626c0a6c3c72907318f0616d0379cbb586404f`

## Gates

| Gate | State | Binding / reason |
|---|---|---|
| `native_eval_ready` | `pending` | R-01, R-02, and R-03 are invalid measurement evidence, so W6R5 produced no valid live product result. |
| `native_resume_ready` | `pending` | W6R5 did not authorize formal Resume evaluation. |

## Current Wave Tickets

| Ticket | State | Binding |
|---|---|---|
| `EVAL-063-H` | `needs_remediation` | Responsible Ticket for `W6R5-EVAL-063-R-MD-003`: the HSMOKE-V4-A exact-string `contains` Oracle rejects a semantically equivalent sentence. Revision 5 remains historical at Accepted commit `e65f370e49fe2ef749e017f33f509997eb1a0cd5`; further modification is not authorized. |
| `AUDIT-063-A` | `accepted` | Revision 5 audit handoff `sha256:3c745440be19c14a18fe4efed9ce829fed4f2e295cc39f306017281cc620462c`; its pre-live deterministic verdict remains historical and does not override MD-003. |
| `TOOL-063-G` | `accepted` | Deterministic Gate handoff `sha256:4bf5d9188bcafacd708a5dcb88a6042127cb8b0c26ff92d3d381a17fb2767aa7`; accepted pre-live evidence remains historical, while the live measurement contract now needs remediation. |
| `EVAL-063-R` | `needs_remediation` | R-03 is preserved as invalid measurement evidence with exact HTTP attempts=`6`; no replacement or rerun is authorized. R-01 and R-02 also remain invalid. |
| `EVAL-063-M` | `pending` | Unstarted because its required valid `EVAL-063-R` dependency was not produced; no fake handoff or Gate decision was generated. |

## Open Findings

- `W6R5-EVAL-063-R-MD-003` — `measurement_defect`; Responsible Ticket=`EVAL-063-H`, affected Ticket=`EVAL-063-R`, invalidated Rows=`1`. HSMOKE-V4-A completed `read_file -> patch_file -> read_file`, and the final file existed with the intended semantic edit; only an exact-string `contains` mismatch failed. R-03 therefore cannot support a product semantic conclusion.
- `W6R5-CR-001` — `change_request`; no product or measurement repair is authorized in W6R5.

## Closed Wave Decision

- W6R5=`blocked`: the user stopped remediation and requested review of unaccepted Evaluation v2 proposals before any new plan revision.
- R-01/R-02/R-03 are immutable invalid measurement evidence, not valid product results.
- `native_eval_ready` remains `pending`; it is neither accepted nor rejected.
- Evaluation v2 proposals are not accepted, W7 is not authorized, and no later Wave has started.

## Next action

The `program_supervisor` and user review the two unaccepted proposals under `docs/enhancements/pico-v3-evaluation-v2/` and decide whether and how to establish a new plan revision.

## Human review

- **Source diff:** `f9626c0a6c3c72907318f0616d0379cbb586404f..e65f370e49fe2ef749e017f33f509997eb1a0cd5`
- **Changed source files:** `benchmarks/v3/native-provider/human-smoke-v4.json`, `scripts/run_v3_native_human_smoke_v4.py`, `tests/test_v3_native_human_smoke_v4.py`
- **Review scope:** W6R5 source changes only; exclude `.codex/eval/**` by default.

## Authoritative references

- **Wave procedure:** `.codex/eval/waves/W6R5-human-smoke-measurement-recovery.md`
- **Final Wave handoff:** `.codex/eval/state/W6R5-wave-handoff.json` (`sha256:a63be33487ac1ee71a9ab3ec467b851a27bfd4595ec6a2b9d6ab895dfb8df831`)
- **R-03 immutable Ticket handoff:** `.codex/eval/handoffs/EVAL-063-R.json` (`sha256:05066a7ebdbca1459a91dd245b015a2aaa1eca15af34f9d6fb2c245bf80c8b88`; its earlier evaluation-failure classification is superseded by MD-003)
- **R-03 immutable Process result:** `F:\dev\llm\pico-eval-artifacts\native-provider-human-smoke-v4\process-manifests\W6R5-EVAL-063-R-03.result.json` (`sha256:8ecd883349d8a12a560953fd7b2c6e3b7e06c9c3f2ed7e6dcf625497a0afc08d`; exact HTTP attempts=`6`)
- **R-03 immutable Artifact:** `F:\dev\llm\pico-eval-artifacts\native-provider-human-smoke-v4\e65f370e49fe2ef749e017f33f509997eb1a0cd5` (summary `sha256:6e6227693e8ff1b6590b06df2b8e8b8b51bea93dd5df5d96898b4fc63bbf0906`; inventory `sha256:6ffbfad170604827fd6956a4af7aec6be9a387ad11ae6cfffa7a56811f723cdd`)
- **Revision-5 EVAL-063-H handoff:** `.codex/eval/handoffs/EVAL-063-H.json` (`sha256:163de1abc1c2ed170db559d31e463c3def12de54d8565a602b7fed040a354dae`)
- **Freeze:** `.codex/eval/state/FREEZE.json` (`sha256:3e593c72bcba9e98c5808ee02e0e010b48a1dcadb0cda0a4e42a56594bc99989`)
