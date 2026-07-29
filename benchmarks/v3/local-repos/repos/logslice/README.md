# logslice

`logslice` is a deliberately small logging formatter used by the local coding
benchmark.  It has no third-party dependencies and can be run directly from a
checkout:

```powershell
$env:PYTHONPATH = (Get-Location)
python -m logslice.cli --message "worker started"
```

The package turns a timestamp, a severity level, and a message into one line of
plain text.  It also includes a tiny command-line interface for producing a
single log record.  The modules are intentionally separate: record parsing,
line formatting, logging configuration, and command-line argument handling
have different responsibilities.

This repository is a benchmark fixture.  Do not add network dependencies or
replace its standard-library command-line interface.
