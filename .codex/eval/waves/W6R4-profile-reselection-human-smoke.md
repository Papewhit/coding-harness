# W6R4 — Profile Reselection 与 Authorized Human Smoke

**Ticket-local term — profile reselection:** 在 accepted W6R3 source 上，使用既有 frozen cases、public profile manifests、Oracle v2 和 `native_eval_ready` criteria 重新运行获授权的 configured candidate profiles，并生成新的版本化 selection Artifact；禁止修改 selection criteria。

W6R4 没有 Tickets。当前 `integrator` 直接执行，必要的 provider calls 以本地 Processes 运行。没有源码修改时，不创建 `implementer`/`reviewer` Thread、worktree、Accepted commit、Git bundle 或 annotated tag。

## Entry binding

- Source SHA：从 `CURRENT.md` 读取，当前为 `cffe1bd0344eb66d218c2e24cae19fca63b2cbf0`。
- Previous handoff：`.codex/eval/state/W6R3-wave-handoff-r2.json`。
- Human smoke manifest/runner：使用 `FREEZE.json` 中已接受的 v3 bindings。
- Entry state：在 `program_supervisor` 授权真实 provider HTTP 前为 `waiting/user_decision`。

## Step 1 — Authorization

授权必须说明：允许使用的 configured profile names（或明确允许全部已配置 candidates）、Artifact root，以及沿用 frozen attempts/retry/budget。`program_supervisor` 另行带外提供 private config locator value；控制文件只记录 configured profile names、公开环境变量名 `PICO_NATIVE_PROVIDER_CONFIG` 和 `private_config_locator_provided_out_of_band=true`，不得记录 locator value、secret、raw endpoint credential、展开后的命令行或 opaque continuation 内容。

## Step 2 — Profile reselection

1. 在 clean Canonical environment checkout accepted source SHA。
2. 启动 Process 前，由 launch environment 注入 `PICO_NATIVE_PROVIDER_CONFIG`；Process manifest 和日志只记录未展开的环境变量引用，不记录其值。对每个获授权 candidate profile 启动一个 Process，命令模板固定为：

   ```bash
   uv run python scripts/run_native_provider_conformance.py \
     --case-set <FROZEN_CASE_SET> \
     --provider <PROFILE_NAME> \
     --expected-profile <FROZEN_PUBLIC_PROFILE_JSON> \
     --repetitions <FROZEN_REPETITIONS> \
     --artifact-dir <ARTIFACT_ROOT>/native-provider-reselection/<SOURCE_SHA>/<PROFILE_NAME>
   ```

3. 每个 Process 写独占目录；不得把多个 profiles 写入同一目录。
4. 不复用与当前 source/evaluator/Oracle/profile-manifest hashes 不完全一致的旧 conformance 结论；旧 Artifacts 保持不可变。
5. `integrator` 只按既有 `native_eval_ready` criteria 判定 eligibility 和选择；不得因 human smoke 历史结果、任务表现或期望结论修改标准。
6. 将 selection、summary、manifest 和 hash inventory 写入：

   ```text
   <ARTIFACT_ROOT>/native-provider-reselection/<SOURCE_SHA>/selection/
   ```

7. 若测量无效，分类为 `measurement_defect`，只修测量装置并重跑受影响 profile。若测量有效但没有 profile eligible，分类为 `evaluation_failure`：保留结果，`native_eval_ready=rejected`，W7 不启动；不自动开启 repair Wave。

## Step 3 — Authorized human smoke

只有 selection 产生唯一 eligible profile 后执行：

```bash
uv run python scripts/run_v3_native_human_smoke_v3.py \
  --authorized-live \
  --provider <SELECTED_PROFILE_NAME> \
  --config "$PICO_NATIVE_PROVIDER_CONFIG" \
  --frozen-profile <FROZEN_PUBLIC_PROFILE_JSON> \
  --output-dir <ARTIFACT_ROOT>/native-provider-human-smoke-v3/W6R4-<SOURCE_SHA>
```

- 只执行一次已授权 smoke；不得为了取得成功结果自动重复。
- Process manifest、日志和 human review 记录上述未展开 argv template；不得记录 shell 展开后的 `--config` 值。
- 证据绑定关系或 runner 无效属于 `measurement_defect`；有效 smoke 的语义失败属于 `evaluation_failure`。
- `integrator` 按 `templates/HUMAN_REVIEW.md` 生成：

  ```text
  <ARTIFACT_ROOT>/native-provider-human-smoke-v3/W6R4-<SOURCE_SHA>/human-review.md
  ```

- 完成后将 Wave 设为 `waiting/user_decision`，等待 `program_supervisor` 接受或拒绝该 smoke。

## Step 4 — Decision and close

- `program_supervisor` 接受有效 smoke：`native_eval_ready=accepted`。
- `program_supervisor` 拒绝，或有效 smoke 失败：`native_eval_ready=rejected`。
- `integrator` 更新 `FREEZE.json`、`CURRENT.md`，生成 `.codex/eval/state/W6R4-wave-handoff.json`，并创建一个只含 W6R4 控制文件的 control checkpoint commit。
- W6R4 状态为 `passed`，因为已授权工作和结论均完整；Gate 状态单独表示 `accepted|rejected`。
- `native_eval_ready=accepted` 时，同一 `integrator` 直接进入 W7；否则 W7 保持 `not_started`，由 `program_supervisor` 决定是否提出新的 `change_request`。

## Exit Gate

Selection 与 smoke 的 source/evaluator/cases/profile/Gate hashes 完整；HTTP attempts 可审计；没有 secret/opaque continuation 泄漏；`program_supervisor` 的接受或拒绝已记录；`CURRENT.md` 只有一个下一动作。
