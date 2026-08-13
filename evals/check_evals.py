#!/usr/bin/env python3
"""Hard gate over evals/runs.jsonl — mirrors the role check_brief.py plays for
Narad. Exits non-zero if any (function, fixture) pair's rolling average over
its last 5 runs has dropped below the floor. A non-zero exit fails the
GitHub Actions job, which surfaces as a red X in the repo's Actions tab —
which Narad's own daily repo-scan already watches for, so a real regression
shows up in the morning brief too, for free.

This does not block anything in the app itself (there's no "publish" step to
gate) — it's a visible, unmissable signal that something needs a look.
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

RUNS_FILE = Path(__file__).parent / "runs.jsonl"
FLOOR = 3.0
WINDOW = 5


def main():
    if not RUNS_FILE.exists() or RUNS_FILE.stat().st_size == 0:
        print("No eval runs recorded yet — nothing to gate on.")
        return 0

    by_pair = defaultdict(list)
    with open(RUNS_FILE) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            by_pair[(row["function"], row["fixture"])].append(row)

    failed = []
    for (function, fixture), rows in by_pair.items():
        recent = rows[-WINDOW:]
        scores = [r["overall_score"] for r in recent if r.get("overall_score") is not None]
        if not scores:
            continue
        avg = sum(scores) / len(scores)
        status = "OK" if avg >= FLOOR else "BELOW FLOOR"
        print(f"{function} / {fixture}: {avg:.2f} avg over last {len(scores)} run(s) — {status}")
        if avg < FLOOR:
            failed.append((function, fixture, avg))

    if failed:
        print(f"\n{len(failed)} function/fixture pair(s) below the {FLOOR} floor:")
        for function, fixture, avg in failed:
            print(f"  - {function} / {fixture}: {avg:.2f}")
        print("\nSee evals/latest_report.md and evals/LEARNED.md for detail.")
        return 1

    print(f"\nAll function/fixture pairs at or above the {FLOOR} floor.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
