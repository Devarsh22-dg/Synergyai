# Nightly Maintenance Log

A durable record of what the "SynergyAI Nightly Maintenance" routine does each
night. It runs at 08:00 UTC against `main` — see the prompt in its
[routine settings](https://claude.ai/code/routines/trig_01H2YoqPK99K3Sic5ejeqDQk).

**Why this file exists.** Commits already record what changed. What they do not
record is what the routine *considered and deliberately did not do* — the
"Suggestions — needs approval" items it raises each night. Those lived only in
claude.ai session transcripts, which are hard to search, easy to lose track of,
and were being lost entirely on nights when the routine could not push. This
file keeps that half of the record in the repo alongside the code.

**How it is maintained.** The routine appends a dated section at the end of each
run, before finishing. Entries are append-only: correct a wrong entry by adding
a follow-up note under a later date rather than rewriting history, so the
reasoning trail stays intact.

---

## Open items awaiting a decision

Carried forward until resolved. The routine adds to this list; remove an item
only once it is actually decided.

- **ScopeBot cannot act on requests** (raised 2026-08-27). ScopeBot is a plain
  text call (`call_chat`, no tools) whose prompt tells it to "steer back to how
  ScopeForge's modules might help." Asked to run a gap analysis or generate
  stories, it explains how rather than doing it. Making it act means giving it
  tool access to the app's own functions — a real design change, not a nightly
  fix, so it needs a decision on scope before anything is built.

- **auth.py's CAPABILITIES list references a removed "risk score" field**
  (raised 2026-08-28). Line 33's Elicitation Analysis description tells new
  users results come "flagged with a risk score," but risk score was removed
  from the gap-analysis schema on 2026-08-27 and replaced with a gap count
  (see the 2026-08-27 entry below). auth.py is permanently off-limits to the
  automated routine, so this stale copy needs a human edit.

- **`call_structured_multimodal` (image descriptions) doesn't warn on a
  truncated response** (raised 2026-08-28). `call_text` and `call_chat` were
  brought in line with `call_structured`'s truncation check tonight; this
  third call site still has none. Left alone deliberately: its docstring
  frames image description as a "bonus signal" that already silently returns
  `[]` on failure, so it's a real open question whether a truncation warning
  fits that intentional silent-degrade design or is just noise — needs a call
  on whether to align it with the other two.

- **User Stories table shows raw dict keys instead of Title Case headers,
  unlike every other generated table** (raised 2026-08-28). The Meeting
  Action Items table had the identical issue and was fixed tonight, but the
  Stories table's `edited_df` is also fed into `generate_test_cases()` via
  `.to_dict("records")`, which reads lowercase keys (`requirement`,
  `user_story`, `acceptance_criteria`), and is used as-is for the Excel/CSV
  exports. A safe fix needs a separate display copy rather than an in-place
  rename, so downstream test-case generation and the exports aren't affected
  — more than a one-line change, left for a night with room to verify the
  export path too.

- **Explore a standalone, sellable AI test-matrix product** (raised
  2026-08-28, interactive planning session, not the nightly routine;
  corrected same day — first logged this as "build an in-app QA module for
  ScopeForge," which was a misread of what was actually said). While kicking
  off a one-week manual QA pass, a one-off "ScopeForge Test Matrix" artifact
  was generated as internal tooling: reading the actual app code (not specs)
  to produce use cases, detailed test cases, and a trackable pass/fail
  matrix. Devarsh's actual idea is that *the tool that generates artifacts
  like this* — pointed at a client's codebase — might be sellable on its
  own, as a separate product/offering, independent of ScopeForge's BA
  niche. Very early conversation, no direction chosen (feature vs. spinoff
  vs. consulting-accelerator angle all still open, see the same day's
  session for the first pass at this). Revisit after the freeze.

- **Nightly Evals GitHub Action has been failing every single night since
  2026-08-19, and still is** (raised 2026-08-29). Every scheduled run from
  #2 (2026-08-19) through last night's #27 (2026-08-28) shows
  `conclusion: failure`, including two nights *after* the 2026-08-26 commit
  (`7eefbd0`, "Revert the custom http_client — it broke production on newer
  SDKs") that was believed to have closed this out. Last night's actual
  job log: every one of the 7 fixtures failed with
  `[st.error] AI request failed: Connection error.` — the exact same
  symptom chased on 2026-08-18 through three different diagnoses (IPv6
  routing, a malformed secret value, an httpx/httpx2 SDK mismatch). The
  `ANTHROPIC_API_KEY` secret is confirmed present (masked but non-empty in
  the job env), so either the "malformed secret" fix didn't fully take, or
  the connection failure has a different/additional cause specific to the
  GitHub Actions network path that hasn't been isolated yet. Net effect:
  **no eval run has actually scored a fixture since 2026-08-18**, and
  `evals/latest_report.md` / `LEARNED.md` are silently stale (the
  "Commit results" step is skipped whenever the harness step fails, so
  nothing ever overwrites the old, artificially-clean report from before
  the harness's own error-surfacing bug was fixed — see run #10's commit
  message). This routine reads those files every night to decide what
  counts as a confirmed AI-output regression; that signal has effectively
  been dark for 11 nights. Needs Devarsh to check the actual secret value
  and/or investigate connectivity from a GitHub Actions runner to
  api.anthropic.com directly — not a nightly-routine fix, and given two
  earlier "fixes" for this exact symptom already turned out wrong (one of
  them broke production), a third guess isn't warranted without new
  evidence.

- **Raw exception text is shown directly to end users in several
  `st.error`/`st.warning` calls** (raised 2026-08-29). E.g. `f"AI request
  failed: {e}"` (four call sites: `call_text`, `call_chat`,
  `call_structured`, `call_structured_multimodal`) and `f"Couldn't read
  this file: {e}"` / `f"Couldn't reach this URL: {e}"`. For a tool heading
  toward SOC2-relevant use, surfacing raw library/exception internals to
  end users is worth a deliberate decision — there's a real tradeoff
  (sanitizing also removes legitimate troubleshooting detail for the BA
  using the tool), and it's six-plus call sites, not one narrow fix, so
  left for Devarsh's judgment rather than an automated change.

- **Every generated-table `pd.DataFrame(...).rename(...)` block implicitly
  trusts that the AI's structured JSON matches the declared schema's
  required fields** (raised 2026-08-29). Two concrete crash sites from
  this pattern (Glossary, Prioritization tables) were fixed tonight by
  adding the same `reindex(..., fill_value="")` guard every other table
  already had; this is the broader pattern behind them. Anthropic's
  tool-use does not strictly guarantee required fields are present, so any
  of the remaining tables (action items, workshop agenda/questions,
  stories) could in principle hit the same class of crash on a field the
  model omits. Worth a shared "safe structured result" helper at some
  point, but that's a refactor across many call sites, not a nightly fix.

---

## 2026-08-29

**Committed**

- `437f771` Escape project name before rendering as HTML in section headers
- `eb53396` Fix example text being sent to AI as a real instruction
- `6b80036` Guard against malformed AI fields and unreadable archives crashing the app

**Worth knowing**

- `437f771` is a real (if low-severity) XSS fix: `section_header()` renders
  its `title`/`subtitle` arguments straight into `st.markdown(...,
  unsafe_allow_html=True)`, and two call sites interpolated the current
  project name — free text from an unvalidated "New Project Name" field —
  into that HTML. A project named e.g. `<img src=x onerror=...>` would
  execute as HTML wherever that project's name is shown again. Checked all
  6 `unsafe_allow_html=True` sites in the file; these were the only two
  that interpolate user-controlled data, so the fix is `html.escape()` at
  just those two spots rather than a change to `section_header()` itself.
  Session data only (no shared/multi-user state), so impact is scoped to
  self-XSS in the acting user's own session — still worth closing given
  the app's SOC2-relevant direction.
- `eb53396` was a genuine, silent bug: `st.text_area()`'s second positional
  argument is `value` (a real default), not placeholder text. The
  Documentation Generator's "special instructions" box passed its example
  text positionally, so every draft generated without the user manually
  clearing the box first sent "e.g., Ensure the regulatory compliance
  section is highly detailed." to the AI as an actual instruction — every
  sibling instructions box elsewhere in the file correctly uses
  `placeholder=`, which is how this stood out.
- `6b80036` bundles three unrelated small crash-guards found in the same
  pass, all the same failure class as recent nights: code trusting
  AI-returned JSON shape or upload bytes more strictly than the schema
  actually guarantees. None of these were reachable via the eval fixtures
  (which is why the eval loop hasn't caught them) — they need a null
  field, a missing field, or a malformed archive to trigger.
- Did NOT act on a fourth candidate from tonight's review:
  `call_structured_multimodal` not discarding a max-tokens-truncated
  result. This is the same issue already sitting in Open items (raised
  2026-08-28) — re-reading it tonight didn't change the open question
  (whether a truncation check fits the function's intentional
  silent-degrade design), so it's left as-is rather than re-raised or
  acted on unilaterally.
- Full pass tonight covered synergyai_app.py end to end (read via a
  background review pass, then independently verified line-by-line before
  any fix) and requirements.txt against actual imports (no drift). Three
  more things came up that looked plausible but weren't safe to act on
  unilaterally — see the new entries above in Open items.
- evals/latest_report.md (dated 2026-08-18) and evals/LEARNED.md (no open
  entries) turned out to be stale and unreliable, not just quiet: checked
  the actual GitHub Actions run history for `Nightly Evals` rather than
  taking the files at face value, and found every scheduled run since
  2026-08-19 has failed with the AI calls themselves erroring
  (`Connection error`) — see the new Open items entry above for the full
  timeline. So step 3 of tonight's process (checking LEARNED.md for
  confirmed regressions) had nothing real to check against; that's a gap
  worth Devarsh knowing about even though tonight's code fixes came from
  direct code review, not the eval signal.

## 2026-08-28

**Committed**

- `d0e8ecc` Remove stale README reference to deleted email-verification setup
- `ff5ca84` Warn on truncated AI text output; fix stale copy

**Worth knowing**

- `ff5ca84` extends last night's truncation fix (`c2aaa1b`, which covered
  `call_structured`) to the two remaining plain-text call sites, `call_text`
  and `call_chat`. `call_text` backs the Documentation Generator, so a draft
  cut off at the token ceiling was previously rendered and offered for
  download with no indication it was incomplete — same bug class as last
  night, different call site. Unlike `call_structured`, which discards a
  truncated result outright (a partial JSON object misrepresents
  completeness), these two now warn but still return the partial text, since
  discarding a cut-off draft or chat reply would throw away something the
  user can still read and salvage.
- The same commit also removed a dangling "risk score" mention in
  `analyze_gaps`'s system prompt (schema no longer has that field, per
  2026-08-27), added the missing "Traceability & Change Impact" module to
  ScopeBot's system prompt (it only named 4 of the app's 5 tabs), and gave
  the Meeting Action Items table the same column-rename treatment every
  other generated table already gets.
- Full review this pass covered synergyai_app.py end to end and
  requirements.txt against actual imports; no drift found there. Three
  things came up that looked at first like tonight's fixes but weren't safe
  to act on unilaterally — see the new entries above in Open items.

## 2026-08-27

**Committed**

- `c2aaa1b` Stop silently rendering truncated AI results; replace risk score with gap count
- `83e1545` Add Harborview scenario fixtures and eval coverage for change impact
- `35259d1` Read table content in uploaded Word and PowerPoint files
- `6831e95` Fix empty-file text leak, None leak, and error copy in upload handling

**Worth knowing**

- The truncation bug was the significant one. `call_structured` returned the
  model's tool output without checking `stop_reason`, so a response cut off at
  the token ceiling rendered as a finished analysis — producing "0 open items"
  beside a summary describing four specific gaps. A document with real problems
  read as clean. Shared `max_tokens` raised 2000 → 8000.
- The risk score was removed from the schema entirely, not just hidden: nothing
  defined the 0–100 scale, so the model invented it fresh each run and the same
  document could score differently while looking authoritative.

## 2026-08-26

**Committed**

- `13013cf` Pin direct dependencies to verified versions
- `d629ce8` Show readable names in the AI Model picker instead of raw API IDs
- `8e1ff08` Read PDFs that are encrypted with an empty user password
- `297bd7c` Bound the chat context sent to the API on long ScopeBot sessions
- `b075845` Read pictures and text inside grouped PowerPoint shapes
- `9f72fec` Cap the decompressed size of .docx/.pptx/.xlsx uploads
- `28952bf` Block SSRF via Source URLs: reject non-public addresses, validate every redirect hop
- `e1f2cab` Fix misleading repo-upload success message; drop dead pptx.util.Emu import

**Worth knowing**

- `28952bf` and `9f72fec` close two of the intake-hardening gaps identified in
  the earlier compliance review (SSRF via the Source URLs feature; zip-bomb
  expansion in Office uploads).
- `13013cf` pins direct dependencies only, not transitive ones — deliberately
  not a lockfile. Stricter reproducibility for audit purposes is still open.

## 2026-08-25

**Committed**

- `7cdb15a` Fix table-export crash on non-string AI fields; safer .txt decoding and empty-doc warning

---

## Before 2026-08-25

Not recorded here. The routine could not push to GitHub until 2026-08-26 (the
Claude GitHub App lacked write access), so several nights of verified fixes were
committed inside ephemeral containers and lost when those were reclaimed. Some
were later reapplied by hand; the rest exist only in the session transcripts
linked from the routine's page. This file starts from the point the record
became reliable.
