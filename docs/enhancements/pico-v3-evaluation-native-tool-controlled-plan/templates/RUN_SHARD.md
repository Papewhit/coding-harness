# Run Shard Ticket Template v2

参数：`phase`、`shard_id`、`case_ids`、`run_snapshot_sha`、`evaluator_sha`、`taskset_sha`、`provider_selection_sha`、`native_gate_sha`、`sdk_decision_sha`、`artifact_root`。

规则：

- checkout 必须 clean 且 HEAD=`run_snapshot_sha`；
- 不允许修改或提交源码；
- 只运行给定 case IDs；
- 输出到 `<artifact_root>/<phase>/<run_snapshot_sha>/<shard_id>/`；
- manifest 记录 model/profile/wire dialect/adapter mode/SDK version/capabilities；
- `stream=false`、SDK retry=0，Pico attempt 数按 freeze；
- 每次 HTTP attempt、call ID、result、protocol error、duplicate call 和 text envelope 均入 rows；
- provider/infrastructure failure 不删除；
- opaque continuation 只记录 hash/type/count；
- 不创建共享 summary，由 aggregate ticket 汇总。

完成后返回 artifact path、manifest hash、row count、HTTP attempt count 和失败分类。源码出现任何 diff、核心 hash 不一致或 SDK 发生隐式 retry 时 shard 无效。
