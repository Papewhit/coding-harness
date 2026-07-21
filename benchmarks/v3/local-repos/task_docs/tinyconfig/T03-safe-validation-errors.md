# T03 — Keep validation errors stable and secret-safe

Configuration validation messages must not reveal user-supplied values. This
matters because invalid input can contain credentials copied from deployment
configuration. Update invalid-port errors so they identify `DATABASE_PORT` and
the validation rule, but never include the supplied text or a converted value.

The exception must remain `ConfigError`, chained from the original `ValueError`
for non-integer input, and valid ports must keep working.
