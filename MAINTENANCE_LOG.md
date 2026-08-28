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

---

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
