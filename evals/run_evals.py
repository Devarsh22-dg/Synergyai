#!/usr/bin/env python3
"""Nightly eval harness for ScopeForge's AI functions.

Runs each fixture in evals/fixtures/ through the real function it targets
(imported directly from synergyai_app.py via a Streamlit shim — no duplicate
prompt logic to drift out of sync), scores the output with Claude acting as
judge against evals/CRITERIA.md, and appends one row per (function, fixture)
to evals/runs.jsonl. Repeated low scores get written into evals/LEARNED.md so
the pattern survives across runs instead of being rediscovered every night.

Usage:
    python3 evals/run_evals.py            # real run, needs ANTHROPIC_API_KEY
    python3 evals/run_evals.py --dry-run   # verifies wiring, no API calls
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

EVALS_DIR = Path(__file__).parent
REPO_ROOT = EVALS_DIR.parent
RUNS_FILE = EVALS_DIR / "runs.jsonl"
LEARNED_FILE = EVALS_DIR / "LEARNED.md"
CRITERIA_FILE = EVALS_DIR / "CRITERIA.md"
REPORT_FILE = EVALS_DIR / "latest_report.md"

LOW_SCORE_THRESHOLD = 3.0      # below this, a run is "concerning"
REPEAT_STREAK_TO_PROMOTE = 3   # this many concerning runs in a row -> LEARNED.md

# Functions a fixture is allowed to target. Single source of truth: both
# run_target_function() and the --dry-run check read this, so a fixture pointing
# at an unwired function fails during the dry run rather than at 07:00 UTC
# halfway through a real, API-consuming run.
SUPPORTED_FUNCTIONS = (
    "analyze_gaps",
    "generate_stories",
    "process_meeting",
    "generate_change_impact",
)

JUDGE_SCHEMA = {
    "type": "object",
    "properties": {
        "criteria_scores": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "criterion": {"type": "string"},
                    "score": {"type": "integer", "minimum": 1, "maximum": 5},
                    "note": {"type": "string", "description": "One sentence justifying the score."},
                },
                "required": ["criterion", "score", "note"],
            },
        },
        "overall_score": {"type": "number", "description": "Average of criteria_scores, as a decimal."},
        "missed_seeded_issues": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Which of the fixture's seeded_issues were NOT properly caught/handled by the output. Empty if all were caught, or if the fixture provided none.",
        },
        "summary": {"type": "string", "description": "1-2 sentence summary of the output's quality."},
    },
    "required": ["criteria_scores", "overall_score", "missed_seeded_issues", "summary"],
}


def load_app():
    """Installs the streamlit shim, then imports synergyai_app so its real
    functions (same prompts/schemas the deployed app uses) can be called
    directly, headlessly."""
    sys.path.insert(0, str(EVALS_DIR))
    sys.path.insert(0, str(REPO_ROOT))
    from streamlit_shim import shim
    sys.modules["streamlit"] = shim
    # Submodules need their own sys.modules entries — Python resolves
    # `import streamlit.components.v1` by dotted-path lookup, not just
    # attribute access on the parent module object.
    sys.modules["streamlit.components"] = shim.components
    sys.modules["streamlit.components.v1"] = shim.components.v1
    import synergyai_app  # noqa: E402
    return synergyai_app


def load_fixtures():
    fixtures = []
    for path in sorted((EVALS_DIR / "fixtures").glob("*.json")):
        with open(path) as f:
            data = json.load(f)
        data["_path"] = path.name
        fixtures.append(data)
    return fixtures


def run_target_function(app, fixture):
    fn = fixture["function"]
    if fn == "analyze_gaps":
        return app.analyze_gaps(fixture["input_text"], notes=fixture.get("notes") or None)
    elif fn == "generate_stories":
        return app.generate_stories(fixture["input_text"])
    elif fn == "process_meeting":
        return app.process_meeting(fixture["input_text"])
    elif fn == "generate_change_impact":
        # input_text is the change request; context_text is the existing project
        # content it's assessed against (the function handles an empty context).
        return app.generate_change_impact(
            fixture["input_text"], fixture.get("context_text", "")
        )
    else:
        raise ValueError(
            f"Fixture '{fixture['_path']}' targets unknown function '{fn}'. "
            "Add a branch here and list it in SUPPORTED_FUNCTIONS, matching CRITERIA.md."
        )


def judge_output(app, fixture, output):
    criteria_text = CRITERIA_FILE.read_text()
    system = (
        "You are a strict but fair evaluator scoring an AI business-analyst tool's output. "
        "You are given the full criteria document for ALL functions this tool has — find and "
        "apply only the section for the function under test. Score honestly; a run with real "
        "problems should score low. Don't be swayed by confident-sounding prose if the content "
        "doesn't actually satisfy the criterion."
    )
    user_prompt = (
        f"Full criteria document (find the section for function '{fixture['function']}'):\n\n{criteria_text}\n\n"
        f"---\nFixture under test: {fixture['fixture_name']}\n"
        f"Fixture description: {fixture.get('description', '')}\n"
        f"Seeded issues this fixture is designed to surface (empty list if none specified):\n"
        f"{json.dumps(fixture.get('seeded_issues', []), indent=2)}\n\n"
        f"Input given to the function:\n{fixture['input_text']}\n\n"
    )
    # Some functions are assessed against existing project content as well as their
    # primary input (change impact, for one). Without it the judge can't tell a
    # grounded reference from an invented one, so groundedness would be unscoreable.
    if fixture.get("context_text", "").strip():
        user_prompt += (
            "Existing project content the function was given as context:\n"
            f"{fixture['context_text']}\n\n"
        )
    user_prompt += (
        f"---\nActual output produced by the function:\n{json.dumps(output, indent=2, default=str)}\n\n"
        "Score this output against the criteria for its function."
    )
    return app.call_structured(
        system, user_prompt, "submit_eval_score",
        "Submit the eval score for this output.", JUDGE_SCHEMA, max_tokens=1500,
    )


def append_run(row):
    with open(RUNS_FILE, "a") as f:
        f.write(json.dumps(row) + "\n")


def load_history(function, fixture_name):
    if not RUNS_FILE.exists():
        return []
    rows = []
    with open(RUNS_FILE) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if row.get("function") == function and row.get("fixture") == fixture_name:
                rows.append(row)
    return rows


def update_learned(function, fixture_name, streak_rows):
    """Appends a lesson to LEARNED.md the first time a (function, fixture) pair
    hits REPEAT_STREAK_TO_PROMOTE consecutive concerning runs. Idempotent-ish:
    it checks for an existing open entry for this pair before adding another."""
    marker = f"<!-- streak:{function}:{fixture_name} -->"
    text = LEARNED_FILE.read_text() if LEARNED_FILE.exists() else ""
    if marker in text:
        return  # already flagged; don't spam the file every night

    latest = streak_rows[-1]
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    missed = sorted({issue for row in streak_rows for issue in row.get("missed_seeded_issues", [])})
    entry = (
        f"\n## {date} — {function} / {fixture_name} {marker}\n\n"
        f"{REPEAT_STREAK_TO_PROMOTE} consecutive runs scored below {LOW_SCORE_THRESHOLD} "
        f"(latest: {latest['overall_score']}).\n\n"
        f"Consistently missed: {', '.join(missed) if missed else '(varies by run — see runs.jsonl)'}\n\n"
        f"Latest judge summary: {latest['summary']}\n\n"
        "**Status: open.** This needs a real look — likely a prompt clarification in "
        "synergyai_app.py, not something to keep re-flagging nightly.\n"
    )
    with open(LEARNED_FILE, "a") as f:
        f.write(entry)


def write_report(results, fixtures_attempted):
    lines = [f"# Eval Report — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}\n"]
    if fixtures_attempted and not results:
        lines.append(
            "⚠️ **0 of "
            f"{fixtures_attempted} fixture(s) produced a score — every judge/generation call "
            "failed.** This is NOT the same as passing; check the workflow log for the actual "
            "API error (look for `[st.error]` lines)."
        )
        REPORT_FILE.write_text("\n".join(lines) + "\n")
        return
    lines.append("| Function | Fixture | Score | Missed Seeded Issues | Flag |")
    lines.append("|---|---|---|---|---|")
    any_flags = False
    for r in results:
        flag = ""
        if r["overall_score"] < LOW_SCORE_THRESHOLD:
            flag = "⚠️ below threshold"
            any_flags = True
        if r.get("promoted"):
            flag = "🔴 repeated — see LEARNED.md"
            any_flags = True
        missed = "; ".join(r.get("missed_seeded_issues", [])) or "—"
        lines.append(f"| {r['function']} | {r['fixture']} | {r['overall_score']} | {missed} | {flag} |")
    if len(results) < fixtures_attempted:
        lines.append(f"\n⚠️ {fixtures_attempted - len(results)} of {fixtures_attempted} fixture(s) failed to produce a score at all (see log).")
    elif not any_flags:
        lines.append("\nAll fixtures at or above threshold tonight.")
    REPORT_FILE.write_text("\n".join(lines) + "\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Verify wiring without calling the API.")
    args = parser.parse_args()

    app = load_app()
    fixtures = load_fixtures()
    print(f"Loaded {len(fixtures)} fixture(s): {[f['fixture_name'] for f in fixtures]}")

    if args.dry_run:
        for fixture in fixtures:
            assert "input_text" in fixture and fixture["input_text"].strip(), f"Empty input_text in {fixture['_path']}"
            assert fixture["function"] in SUPPORTED_FUNCTIONS, (
                f"Unknown function '{fixture['function']}' in {fixture['_path']} — "
                f"add a branch in run_target_function() and list it in SUPPORTED_FUNCTIONS."
            )
        print("Dry run OK — shim imports cleanly, fixtures well-formed, no API calls made.")
        return

    results = []
    for fixture in fixtures:
        print(f"Running {fixture['fixture_name']} ({fixture['function']})...")
        output = run_target_function(app, fixture)
        judgment = judge_output(app, fixture, output)
        if not judgment:
            print(f"  Judge call failed for {fixture['fixture_name']}, skipping.")
            continue

        row = {
            "date": datetime.now(timezone.utc).isoformat(),
            "function": fixture["function"],
            "fixture": fixture["fixture_name"],
            "model": app.current_model(),
            "overall_score": judgment.get("overall_score"),
            "criteria_scores": judgment.get("criteria_scores", []),
            "missed_seeded_issues": judgment.get("missed_seeded_issues", []),
            "summary": judgment.get("summary", ""),
        }
        append_run(row)

        history = load_history(fixture["function"], fixture["fixture_name"])
        recent = history[-REPEAT_STREAK_TO_PROMOTE:]
        streak = len(recent) == REPEAT_STREAK_TO_PROMOTE and all(
            r["overall_score"] < LOW_SCORE_THRESHOLD for r in recent
        )
        row["promoted"] = streak
        if streak:
            update_learned(fixture["function"], fixture["fixture_name"], recent)

        results.append(row)
        print(f"  Score: {row['overall_score']} — {row['summary']}")

    write_report(results, len(fixtures))
    if fixtures and not results:
        # Every fixture failed to produce a score — that's a broken run, not
        # a clean one. Exit non-zero so the Action shows red instead of green.
        sys.exit(1)
    print(f"\nReport written to {REPORT_FILE}")


if __name__ == "__main__":
    main()
