# ScopeForge Eval — Learned Issues

What has actually gone wrong in nightly evals and been confirmed as a real,
repeated pattern (not a one-off). Entries are appended automatically by
`run_evals.py` when the same (function, fixture) pair scores below
threshold for 3 consecutive nights — a single bad night doesn't land here,
only a real pattern does. See `runs.jsonl` for the full run-by-run history
and `CRITERIA.md` for what's being scored.

Each entry's status should be updated to **closed** once the underlying
prompt/logic in `synergyai_app.py` has actually been fixed — leaving it open
after a fix just means the next 3-run streak (if the fix didn't work) won't
be able to tell you it's still broken.

No entries yet.
