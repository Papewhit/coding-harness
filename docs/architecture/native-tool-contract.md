# Native Tool Contract

本文定义 provider adapter 与 Coda 上层之间的原生模型/工具调用边界。合同位于
`coda/providers/contracts.py`，只包含 Python 标准库类型，不包含任何 provider SDK
对象。当前 Runtime 仍通过 `coda/providers/base.py` 中既有的 prompt-to-text
`ModelClient` 工作；本次只新增并行的 `NativeModelClient` 边界，不切换 active Runtime。

## 交换模型

一次 `ModelRequest` 包含文本 prompt、输出 token 上限、工具声明、`ToolChoice`、上一批
`ToolCallResult`，以及可选的 `ProviderContinuation`。adapter 返回的 `ModelResponse`
同时保留：

- `text`：本轮可见文本，可以与工具调用同时存在；
- `tool_calls`：结构化 `ToolCall` 列表；
- `stop_reason`：归一化的 `StopReason`；
- `continuation`：下一次请求需要原样回传的 provider 私有状态；
- `metadata`：JSON-safe 的公开元数据。

`ToolCall.call_id` 与 `ToolCallResult.call_id` 都必须是非空字符串。一次 response 内不得有
重复 call ID，一次 request 内不得有重复 result call ID。后续执行层必须使用 provider
给出的 call ID 做一对一匹配，包括未知工具、参数错误、权限或安全拒绝以及未执行调用；
不得自行生成替代 ID。

## JSON-safe 不变量

所有合同的 `to_dict()` 输出只能由以下值组成：字符串、整数、有限浮点数、布尔值、
`null`、数组，以及字符串键的对象。NaN、Infinity、SDK 对象、迭代器、bytes 和非字符串
对象键会在边界处失败。工具 schema、参数、结果、continuation 和 metadata 在构造时会被
规范化，避免调用方随后修改原输入对象而改变合同内容。

合同不编码或解析 `<tool>` / `<final>` 文本信封。是否支持 native tools 是 profile 的
能力判断；adapter 不支持时应由后续 wiring 标记为不 eligible，不得通过文本协议降级。

## Profile identity

`ProviderContinuation.profile_id` 是公开、非空且稳定的 profile 身份，不是显示名称。
生成方应让它绑定以下配置：provider、model、wire dialect、adapter mode、SDK package/version、
base URL fingerprint、capabilities 和 retry 设置。身份中不得包含 API key、Authorization
header、原始 credential 或带敏感查询参数的 URL。

Continuation 只能回传给相同 profile identity 的 adapter。跨 profile 使用必须失败，避免
把一种 wire dialect 的私有状态交给另一种 adapter 解释。

## Continuation schema

持久化形状如下：

```json
{
  "profile_id": "openai-responses:profile-hash",
  "payload": {
    "provider_specific": "opaque JSON value"
  }
}
```

`payload` 可以是任意 JSON value，而不限定为对象。Core、Session 和 Checkpoint 只保存并
原样回传它，不检查内部 block 类型、不摘要 reasoning/thinking block，也不持久化 SDK
对象。`ProviderContinuation.stable_hash()` 对 profile identity 与规范化 payload 一并计算
SHA-256；它用于证据和一致性检查，不会暴露或解释私有内容。

公开 trace/report 不应写入 payload，只记录类型、数量与 hash 等允许字段。若本地策略不能
安全保存某类 opaque block，应关闭相应 provider 能力，而不是修改或丢弃 continuation。
