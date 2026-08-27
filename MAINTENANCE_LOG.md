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

---

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
