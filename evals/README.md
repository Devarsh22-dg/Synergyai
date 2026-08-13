# ScopeForge Eval Loop

Nightly, automated quality check for the app's AI functions — runs the real
`synergyai_app.py` prompts against fixed synthetic fixtures, scores the
output with Claude as judge, and tracks the trend over time. Same pattern as
the `narad` daily-brief loop: a criteria file, a learned-lessons file that
only grows when something's a real repeated pattern (not noise), and a hard
gate.

## Files

| File | Role |
|---|---|
| `CRITERIA.md` | What good output looks like, per function. Stable. |
| `LEARNED.md` | Confirmed repeated failures (3+ consecutive bad nights). Grows over time. |
| `runs.jsonl` | One JSON line per (function, fixture) per run — full history. |
| `latest_report.md` | This run's results, human-readable. Overwritten nightly. |
| `fixtures/*.json` | Synthetic (never real client data) inputs with seeded issues a good run should catch. |
| `streamlit_shim.py` | Lets `synergyai_app.py` be imported without a real Streamlit session. |
| `run_evals.py` | The harness. `--dry-run` verifies wiring without calling the API. |
| `check_evals.py` | Hard gate — non-zero exit if a rolling average drops below 3.0/5. |

## Running locally

```bash
python3 evals/run_evals.py --dry-run   # no API key needed, verifies wiring
python3 evals/run_evals.py             # real run, needs ANTHROPIC_API_KEY
python3 evals/check_evals.py           # check the gate against runs.jsonl
```

## How it's wired up

`.github/workflows/nightly_evals.yml` runs this at 07:00 UTC daily (free —
GitHub Actions), commits `runs.jsonl`/`LEARNED.md`/`latest_report.md` back to
`main`, and fails the Actions job if the gate trips. A failing Action shows
up in the repo's Actions tab, which also means it surfaces automatically in
any daily brief that already watches this repo for failing Actions.

The separate nightly code-maintenance routine (RemoteTrigger, 08:00 UTC —
after evals so its report is fresh) reads `LEARNED.md` and
`latest_report.md` and factors confirmed, repeated issues into its summary.

**Setup required, once:** add `ANTHROPIC_API_KEY` as a GitHub Actions repo
secret (Settings → Secrets and variables → Actions → New repository secret).
This has to be done by hand — no automated process should ever be handed a
credential to enter on your behalf.

## Adding a new fixture

1. Add a criteria section to `CRITERIA.md` for the function, if it doesn't have one.
2. Add `evals/fixtures/<name>.json` with `function`, `fixture_name`,
   `description`, `input_text`, and (recommended) `seeded_issues` — specific
   problems planted in the input that a good run should catch. This is what
   makes the eval actually test something, not just "did it return JSON."
3. Add a branch for the function in `run_target_function()` in `run_evals.py`
   if it's not `analyze_gaps`, `generate_stories`, or `process_meeting`.
4. `python3 evals/run_evals.py --dry-run` to confirm it loads before it runs for real.
