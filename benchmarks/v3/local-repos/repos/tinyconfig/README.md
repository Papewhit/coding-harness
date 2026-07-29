# tinyconfig

`tinyconfig` is a deliberately small configuration helper used by the local
repository benchmark.  It reads a few application settings from an environment
mapping and reports invalid values.

Run the package's visible smoke check with:

```powershell
python -c "from tinyconfig import load_settings; print(load_settings({}))"
```

The task-specific acceptance tests are intentionally not included in this
repository snapshot.
