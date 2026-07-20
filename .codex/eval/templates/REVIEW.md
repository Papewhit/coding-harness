# Wave Review Template v2

Reviewer 从波次集成 SHA 启动，只读检查：

- scope 外文件或重叠 owner；
- evaluator / product fix / evidence 是否混提交；
- contract/schema/profile/gate hash 是否完整；
- Runtime 或在线 evaluator 是否仍有文本协议路径；
- SDK 是否越过 Adapter 边界或启用 Tool/Agent Runner；
- call ID/result、batch 完整性、error result 和 stop reason 测试；
- opaque continuation 是否丢失或泄漏；
- SDK retry、Pico retry 和 HTTP attempt 是否可审计；
- safety/permission/policy/repetition/architecture gate 是否退化；
- artifact 是否泄漏 secret。

输出 `accept|changes_requested|block`。Reviewer 不直接修复；修复另开 ticket。
