# ScopeForge Eval Criteria

What "good" looks like for each AI function, scored 1-5 by an LLM judge against
the fixture's source content and expected signals. Stable — changes rarely.
See `LEARNED.md` for what's actually gone wrong and been corrected over time.

## Scoring scale (applies to every criterion below)

- **5** — Fully meets the bar, nothing to fix.
- **4** — Meets the bar with a minor nitpick.
- **3** — Partially meets it; a BA would need to touch it up.
- **2** — Misses something a BA would notice immediately.
- **1** — Wrong, invented, or unusable.

Overall score for a run is the average of its criteria. A run **fails the gate**
(see `check_evals.py`) if the rolling average for any function drops below 3.0.

## analyze_gaps (Elicitation Analysis & Gap Detector)

- **Groundedness** — every open question/gap is traceable to something actually
  present or notably absent in the fixture text. No invented requirements.
- **Coverage** — the gaps a human BA would flag in this fixture (deliberately
  seeded ambiguities/missing NFRs) are actually caught.
- **Actionability** — each "why_it_matters" gives a BA something they could
  actually take to a stakeholder, not generic filler.
- **Summary quality** — the summary reflects what the findings actually say;
  it should not describe problems that never appear in open_questions.

## generate_stories (Agile Story & Backlog Creator)

- **Groundedness** — every story maps to a real requirement in the fixture.
- **Format compliance** — "As a <role>, I want <capability>, so that
  <benefit>" format and Gherkin GIVEN/WHEN/THEN acceptance criteria, every time.
- **Coverage** — the fixture's distinct requirements each produce a story;
  nothing obviously present is skipped.
- **Non-duplication** — no near-identical stories for the same requirement.

## process_meeting (Meeting Intelligence & Actionizer)

- **Groundedness** — decisions/action items are things actually said in the
  transcript, not inferred beyond what's stated.
- **Owner/date discipline** — uses "Unassigned"/"Not specified" rather than
  guessing when the transcript doesn't state one.
- **Summary quality** — the executive summary would let someone who missed the
  meeting understand what happened in a few seconds.
- **Completeness** — every explicit action item in the fixture is captured.

## generate_change_impact (Change Request Impact Analysis)

- **Groundedness** — every affected requirement cited actually exists in the
  provided project context, quoted or identified accurately. No invented
  requirement IDs, and no requirement listed as affected that the change
  doesn't actually touch (false positives count against this).
- **Coverage** — the requirements a human BA would flag as affected are all
  identified, including indirect ones (audit logging, security/compliance
  constraints), not just the single most obvious match.
- **New-scope detection** — where the change introduces something with no
  existing requirement behind it, that's called out as new scope rather than
  silently folded into an existing requirement.
- **Impact calibration** — the stated impact level is proportionate to what the
  change actually does, and recommended actions are concrete enough for a BA to
  act on.

## Adding a new function's criteria

Copy one of the sections above, swap in what actually matters for that
function, and add a matching fixture in `fixtures/`. Keep each criterion
something a judge can actually assess from the fixture + output alone —
if a criterion needs information the judge doesn't have, it isn't testable.
