# 配置

pico 的配置按下面这个优先级合并：

```
CLI 显式参数 > 环境变量 > 项目 .pico.toml > 全局 ~/.config/pico/config.toml > 代码默认
```

## Provider profile

provider 是 TOML 里的一段本地配置 profile，名字（如 `deepseek` `openai` `anthropic`）只用于人类辨识。Pico 不根据名字或 host 猜测 endpoint/协议；真正决定 wire 格式的是 `wire_dialect`，目前支持 `openai-responses` 和 `anthropic-messages`。

### .pico.toml 示例

放在仓库根目录，**不要提交真实 key**（默认已被 `.gitignore` 忽略）：

```toml
provider = "deepseek"

[providers.deepseek]
wire_dialect = "anthropic-messages"
api_key = "sk-..."
base_url = "https://api.deepseek.com/anthropic"
model = "deepseek-v4-pro"

[providers.deepseek.capabilities]
native_tools = true
strict_tool_schema = false
parallel_tool_calls = false
reasoning = false
thinking = true
opaque_continuation = true

[providers.openai]
wire_dialect = "openai-responses"
api_key = "sk-..."
base_url = "https://api.openai.com/v1"
model = "gpt-5.4"

[providers.anthropic]
wire_dialect = "anthropic-messages"
api_key = "sk-ant-..."
base_url = "https://api.anthropic.com"
model = "claude-sonnet-4-6"
```

`native_tools` 必须为 `true`，否则 coding session 在发出请求前即拒绝启动。其余能力分别声明 strict tool schema、并行 tool call、reasoning、thinking 以及 opaque continuation；不能用一个“高级推理”开关替代，也不会按 endpoint 自动开启。未声明的能力默认为 `false`。

旧配置中的 `protocol = "openai"` 和 `protocol = "anthropic"` 会分别确定性映射到上述两个 dialect。未知旧值，或同时提供相互冲突的 `protocol` 与 `wire_dialect`，会给出迁移错误而不会猜测。

session 创建时会锁定 model、profile、wire dialect、capabilities、base URL fingerprint 和 tool schema 签名。改变这些值后不能 resume 旧 session；API key 不属于 identity，可以安全轮换。早于该锁定格式的旧 session 会要求新建 session。

切 provider：

```bash
pico                       # 用 toml 里的默认 provider
pico --provider openai     # 临时切换
pico --provider anthropic --model claude-opus-4-6
```

## 环境变量

不写 toml 也能跑——只设环境变量即可：

| 变量 | 用途 |
|------|------|
| `PICO_PROVIDER` | 默认 provider |
| `PICO_API_KEY` / `PICO_BASE_URL` / `PICO_MODEL` | 通用 override |
| `ANTHROPIC_API_KEY` / `ANTHROPIC_BASE_URL` / `ANTHROPIC_MODEL` | Anthropic |
| `OPENAI_API_KEY` / `OPENAI_BASE_URL` / `OPENAI_MODEL` | OpenAI |
| `DEEPSEEK_API_KEY` / `DEEPSEEK_BASE_URL` / `DEEPSEEK_MODEL` | DeepSeek |

兼容历史 `.env`：`PICO_OPENAI_*` / `PICO_ANTHROPIC_*` / `PICO_DEEPSEEK_*` 仍然能用。

## 全局配置

`~/.config/pico/config.toml` 适合放跨项目都用的 provider profile。项目 `.pico.toml` 覆盖它，CLI 参数再覆盖项目。

## CLI 参数

```bash
pico --provider deepseek --model deepseek-v4-pro
pico --api-key sk-... --base-url https://...
pico --max-steps 50 --max-new-tokens 4096
pico --temperature 0.0
pico --approval ask          # ask | auto | never
pico --sandbox best_effort   # off | best_effort | required
pico --no-auto-dream         # 关闭后台 memory 整合
pico --cwd /path/to/repo     # 切换工作目录
pico --resume latest         # 续接上一个 session
pico --config /path/to/custom.toml
pico --inspect-provider         # 输出无 key、无原始 URL 的 profile identity
```

跑 `pico --help` 看完整参数。

## 默认值速查

| 项 | 默认 |
|----|------|
| `max-steps` | 50 |
| `max-new-tokens` | Anthropic 32000 / OpenAI 8192 / DeepSeek 8192 / fallback 4096 |
| `temperature` | 0.2 |
| `approval` | `ask` |
| `sandbox` | `off` |
| `dream-interval` | 24 小时 |
| `dream-min-sessions` | 5 |

## 调试

- `/session` 查看 session 文件路径和当前 runtime 标识
- `/context` 查看上下文用量切片
- `/usage` 查看 token / call 数
- 所有事件流写到 `.pico/sessions/<id>.events.jsonl`，可以用 `tail -f` 观察
- 每次运行的 trace 在 `.pico/runs/<run_id>/trace.jsonl`
