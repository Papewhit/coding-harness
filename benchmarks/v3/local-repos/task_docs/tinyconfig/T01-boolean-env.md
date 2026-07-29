# T01 — Parse a boolean environment value

`load_settings` currently treats every non-empty `APP_DEBUG` value as true.
Implement conventional boolean parsing for that setting.

Accepted values are case-insensitive `true`, `false`, `1`, `0`, `yes`, `no`,
`on`, and `off`. Whitespace around a value is ignored. An unsupported value
must raise `ConfigError` and name `APP_DEBUG`; do not silently choose a value.

Keep the public API unchanged and preserve the default of `false` when the key
is absent.
