# T02 — Support nested configuration keys

Callers may pass nested mappings instead of flat environment-style keys, for
example:

```python
{"app": {"debug": "true"}, "database": {"host": "db", "port": "15432"}}
```

Update `load_settings` so it accepts this representation as well as the
existing flat keys. A flat key takes precedence when both forms provide the
same value. Missing nested fields retain the existing defaults. Malformed
nested sections (anything other than a mapping) must raise `ConfigError` that
names the offending section.
