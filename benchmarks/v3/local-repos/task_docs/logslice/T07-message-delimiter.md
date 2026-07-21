# T07 — Add a delimiter before the message

The rendered record header must be visibly separated from its message so that
downstream shell tools can split the line without guessing where the level
ends.

Update `logslice.formatter.format_record` so a normal record renders exactly
as:

```text
2025-01-02T03:04:05Z [INFO] | worker started
```

The timestamp formatting, bracketed severity, and message contents must remain
unchanged.  Do not change the CLI interface or introduce a third-party
dependency.
