# Current Evaluation State

- **Control revision:** `eval-control-v4`
- **Updated at:** `2026-07-26`
- **Current Wave:** `W6R4`
- **Wave state:** `passed`
- **Waiting reason:** `none`
- **Current objective:** W6R4 is closed with its authorized work and conclusions complete; `native_eval_ready` is rejected independently of the passed Wave state.
- **Source SHA:** `0d8c21c3484b069c71a7a8b784b74330530163d2`
- **Candidate SHA:** `none`
- **Control checkpoint SHA:** `1184bd39123e3898061417a275c4083f61ad8102`

## Gates

| Gate | State | Binding / reason |
|---|---|---|
| `native_eval_ready` | `rejected` | `program_supervisor` accepted the selection and valid smoke evidence, accepted `W6R4-EF-001` as an `evaluation_failure`, and rejected the Gate. |
| `native_resume_ready` | `pending` | `TOOL-062-G` has not run. |

## Current Wave Tickets

W6R4 has no native Tickets. Responsible Ticket `EVAL-059-O` revision 2 is `accepted` at `0d8c21c3484b069c71a7a8b784b74330530163d2`; worker handoff `sha256:47f971316f3eab2b93dafe6a66f1e1c5601f8e2d7c2b4e5671a489a4c14480dc`, independent review `sha256:27cc4f3f7fe43fd0e5f2bdb256c398c80be83d2621f7bc883011701af6aac0f6`.

## Open Findings

None requiring remediation. `program_supervisor` accepted `W6R4-EF-001` as the terminal `evaluation_failure`; it does not imply a product-repair request. `W6R4-SMOKE-MD-001`, `W6R4-MD-001`, and `W6R4-MD-002` are resolved `measurement_defect` findings with their invalid or superseded evidence preserved.

## Next action

No action is authorized. Any repair requires a separate `program_supervisor` `change_request`; automatic repair, another smoke run, and W7 are not authorized. `program_supervisor` provides the private config locator value out of band; this record persists only the public locator environment-variable name `PICO_NATIVE_PROVIDER_CONFIG`. W7 remains `not_started`.

## Human review

- **Source diff:** `cffe1bd0344eb66d218c2e24cae19fca63b2cbf0..0d8c21c3484b069c71a7a8b784b74330530163d2`
- **Changed source files:** `pico/evaluation/native_provider.py`, `pico/evaluation/native_provider_live.py`, `tests/test_native_provider_evaluator.py`, `tests/test_native_provider_live.py`
- **Review Artifact:** `F:\dev\llm\pico-eval-artifacts\native-provider-reselection\cffe1bd0344eb66d218c2e24cae19fca63b2cbf0\selection\EVAL-059-O-R1-review.json` (`sha256:c9f4364bd4b79ee87b9a97176a2045e2c1cf2f7120105ec41e2bafe89dc72f97`)
- **Revision 2 Review Artifact:** `F:\dev\llm\pico-eval-artifacts\native-provider-reselection\345261c3f644ddea92065f105bc754e223d0eff4\selection\EVAL-059-O-R2-review.json` (`sha256:27cc4f3f7fe43fd0e5f2bdb256c398c80be83d2621f7bc883011701af6aac0f6`)
- **Smoke result:** valid `FAIL`; `HSMOKE-V3-A` failed, `HSMOKE-V3-B` passed; `6` provider HTTP attempts; no rerun.
- **Summary path:** `F:\dev\llm\pico-eval-artifacts\native-provider-human-smoke-v3\W6R4-0d8c21c3484b069c71a7a8b784b74330530163d2-R1\summary.json` (`sha256:0af9cbc8e35e93b02bcd69da18b1991a756c2b5b9ba649317346c2bec1c10a49`)
- **Human Review:** `F:\dev\llm\pico-eval-artifacts\native-provider-human-smoke-v3\W6R4-0d8c21c3484b069c71a7a8b784b74330530163d2-R1\human-review.md` (`sha256:149fdc5cfb10bfe065e7a8364cc963e488cc536b8823b3e05ba057584ace53c7`)

## Authoritative references

- **Current Wave procedure:** `.codex/eval/waves/W6R4-profile-reselection-human-smoke.md`
- **Latest Wave handoff:** `.codex/eval/state/W6R4-wave-handoff.json` (`sha256:9b4f748e3340420cb8ffceffbcb81d4caa2c88c883abbbdce42a51e0faf8c8bb`)
- **Previous Wave handoff:** `.codex/eval/state/W6R3-wave-handoff-r2.json` (`sha256:521b1f3e30c393cbefd449cbff5057992cdca3167a327ec612532cc7335c8823`)
- **Accepted source tree:** `98d4c62a14dfc446c3ff5dceecea7eeb02c1b941`
- **Freeze:** `.codex/eval/state/FREEZE.json` (`sha256:d2357c2c29b527beb07f00e7c3dea7dbce5d61e8e503eb9cbde5fe3e229adf5f`)
- **W6R3 Gate Artifact:** `F:\dev\llm\pico-eval-artifacts\native-deterministic-gate\W6R3-TOOL-059-G-02`
- **Original W6R4 Artifact root:** `F:\dev\llm\pico-eval-artifacts\native-provider-reselection\cffe1bd0344eb66d218c2e24cae19fca63b2cbf0`
- **First replacement W6R4 Artifact root:** `F:\dev\llm\pico-eval-artifacts\native-provider-reselection\345261c3f644ddea92065f105bc754e223d0eff4`
- **Current W6R4 Artifact root:** `F:\dev\llm\pico-eval-artifacts\native-provider-reselection\0d8c21c3484b069c71a7a8b784b74330530163d2`
- **Selection:** `dashscope-o` uniquely selected from hard-Gate-eligible `dashscope-o` and `dashscope-a`; `deepseek` was excluded before comparison.
- **Selection Artifact:** `F:\dev\llm\pico-eval-artifacts\native-provider-reselection\0d8c21c3484b069c71a7a8b784b74330530163d2\selection\selection.json` (`sha256:245bb1032998d61496d18b3a9edcf89ac21b7b2c44ba997267e7a7f344a5b056`)
- **Selection Summary:** `F:\dev\llm\pico-eval-artifacts\native-provider-reselection\0d8c21c3484b069c71a7a8b784b74330530163d2\selection\summary.json` (`sha256:6e2cbe3c24a29f1c46b23a629d1e98b85a5e82a8a756da44148df1dff8609583`)
- **Selection Verification:** `F:\dev\llm\pico-eval-artifacts\native-provider-reselection\0d8c21c3484b069c71a7a8b784b74330530163d2\selection\verification.json` (`sha256:2c55f760241cc5c9feb2a38e1b773c39f8ba6e48a55aa82ccdb83d609eef10d9`)
- **Selection Inventory:** `F:\dev\llm\pico-eval-artifacts\native-provider-reselection\0d8c21c3484b069c71a7a8b784b74330530163d2\selection\inventory.json` (`sha256:d8c136a6ef1fe359d0a3fefa05493173c85eb9e3f464c5be6abdb1d958951cd0`)
- **Selection Manifest:** `F:\dev\llm\pico-eval-artifacts\native-provider-reselection\0d8c21c3484b069c71a7a8b784b74330530163d2\selection\manifest.json` (`sha256:699a294a9027f9109c235ee5b3e3d10b527669a1b23eb1017ff2c4ea43460cb8`)
- **Invalid Smoke Process manifest:** `F:\dev\llm\pico-eval-artifacts\native-provider-human-smoke-v3\process-manifests\W6R4-0d8c21c3484b069c71a7a8b784b74330530163d2.json` (`sha256:7cbc79bfc17a7fde1b5523034ad1e8be3c8337f575f0bfca126ee02d406f9d29`)
- **Invalid Smoke State marker:** `F:\dev\llm\pico-eval-artifacts\native-provider-human-smoke-v3\process-manifests\W6R4-0d8c21c3484b069c71a7a8b784b74330530163d2.state.json` (`sha256:bb28095487543c2322fe9b830847e5f74c10bacf0f3faa0745e5424f1b2cbb94`)
- **Smoke launch measurement defect:** `F:\dev\llm\pico-eval-artifacts\native-provider-human-smoke-v3\process-manifests\W6R4-SMOKE-MD-001.json` (`sha256:9d41cfb9825803481a453b3f2f6204f247f96742bbdda1c0186e663dfb528073`)
- **Replacement Smoke Process manifest:** `F:\dev\llm\pico-eval-artifacts\native-provider-human-smoke-v3\process-manifests\W6R4-0d8c21c3484b069c71a7a8b784b74330530163d2-R1.json` (`sha256:399e3d91efd3297784fcfbc2a0a57ea19f7ce8ac850d602d60311874196404ba`)
- **Replacement Smoke State marker:** `F:\dev\llm\pico-eval-artifacts\native-provider-human-smoke-v3\process-manifests\W6R4-0d8c21c3484b069c71a7a8b784b74330530163d2-R1.state.json` (`sha256:922fbfb2aa1e5eccec4220dba157024f599baa9c67856f38f8b35fd10b3215ec`)
- **Smoke Artifact root:** `F:\dev\llm\pico-eval-artifacts\native-provider-human-smoke-v3\W6R4-0d8c21c3484b069c71a7a8b784b74330530163d2-R1`
- **Smoke Summary:** `summary.json` (`sha256:0af9cbc8e35e93b02bcd69da18b1991a756c2b5b9ba649317346c2bec1c10a49`)
- **Scenario results:** `HSMOKE-V3-A\result.json` (`sha256:1511cf83db572bff83019c307b7d5159b0dc88e2cfcabae0b0b21794d73efc37`), `HSMOKE-V3-B\result.json` (`sha256:76883314f3ff9379ba99d5368fa9adee47da87e9023afb15d0e3fae2b742500e`)
- **Evaluation failure:** `W6R4-EF-001.json` (`sha256:df910751d8ab069736f5082f53e14b16abf77172fd9341df269b3cfe91d4b4c4`)
- **Smoke Inventory:** `inventory.json` (`sha256:69f616c7b18cc9bed6040adda173d03c3e20931884ef053844c6f6226541ef5e`)
- **Human Review:** `human-review.md` (`sha256:149fdc5cfb10bfe065e7a8364cc963e488cc536b8823b3e05ba057584ace53c7`)
- **HTTP accounting:** W6R4 total `442` = reselection `436` + invalid launcher `0` + valid smoke `6`.
- **Final decision:** W6R4 `passed`; `native_eval_ready=rejected`; `native_resume_ready=pending`; W7 `not_started`; no repair or rerun authorized.
- **Prepared Process manifests:** `dashscope-o` (`sha256:75c559524d833f437dd86efd9f33c76f50968d4d7ad9612dfccc89be5199d121`), `dashscope-a` (`sha256:60b7af067827ed49ae9314bc3c7d7572402ac1ac9f72efbf0874b340bb7856b8`), `deepseek` (`sha256:c115d929b95a4234dec8edff35ce7fa9a70ea08fc588cb59ad282c193c8bac2b`)
- **First replacement Process manifest:** `deepseek` (`sha256:7cbddf2d292070dacee7056df2de7b6cd2d2aadc5c13fe9d55caaabc2f8bf577`)
