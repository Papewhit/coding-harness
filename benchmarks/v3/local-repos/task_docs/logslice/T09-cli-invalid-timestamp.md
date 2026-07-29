# T09 — Report invalid CLI timestamps cleanly

When `python -m logslice.cli` receives `--timestamp` with an invalid ISO-8601
value, it currently exposes an implementation traceback.  Treat this as a
regular command-line validation error instead.

The command must exit with argparse's error status (`2`), write a concise
message containing `invalid timestamp` to stderr, and not print a traceback.
Valid ISO-8601 timestamps, including the trailing `Z` form, must continue to
render normally.
