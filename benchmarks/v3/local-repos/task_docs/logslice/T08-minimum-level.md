# T08 — Honour the configured minimum level

`logslice.formatter.configure_logger` already accepts a `minimum_level`
argument, but the returned logger does not consistently honour it.

Make the configured threshold control the logger's effective level.  Inputs
use the same case-insensitive names accepted elsewhere in the package.  Invalid
levels should produce the package's existing useful `ValueError`; do not
silently choose a fallback level.  Preserve the existing one-handler and
non-propagating behaviour.
