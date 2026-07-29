# `run_shard` Process Template（eval-control-v4）

`run_shard` 由 `integrator` 启动本地 Process，不创建模型 Thread。

`integrator` 在启动前为每个 Process 写 Process manifest，至少包含：`ticket_id`、`process_id`、`phase`、`case_ids`、`run_snapshot_sha`、`evaluator_sha`、`taskset_sha`、`provider_selection_sha`、`native_gate_sha`、`sdk_decision_sha`、`artifact_root` 和精确命令。

规则：

- checkout 必须 clean 且 HEAD=`run_snapshot_sha`；
- Process 不允许修改或提交 Git-tracked files；
- 每个 Process 只运行给定 case IDs，写入 `<artifact_root>/<phase>/<run_snapshot_sha>/<process_id>/`；
- Process manifest 记录 source/evaluator/taskset/profile/Gate/SDK hashes、model、wire dialect、adapter mode、SDK version、capabilities 和精确命令；
- `stream=false`、SDK retry=0；Pico attempts 按 Freeze；
- 每次 HTTP attempt、call ID、result、protocol error、duplicate call 和 text envelope 写入 Row；
- provider/infrastructure/task failure 不删除；
- opaque continuation 只记录 hash/type/count；
- 一个 Ticket 的全部 Processes 完成后，由 `integrator` 写一份 Ticket handoff，禁止每个 Process 写独立 handoff JSON。

每个 Process 只向 `integrator` 返回：exit code、Artifact path、Process manifest hash、Row count、HTTP attempt count、失败分类和日志 path/hash。Git-tracked files 有 diff、核心 hash 不一致、SDK 隐式 retry 或 Artifact 不可解析时，该 Process 无效并分类为 `measurement_defect`。
