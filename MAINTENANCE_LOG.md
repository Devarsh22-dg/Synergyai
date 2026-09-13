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

- **Edits made in the Story / Test Case `st.data_editor` tables are never
  written back to project state, so the RTM and Change Impact Analyzer
  silently use the stale, pre-edit AI output** (raised 2026-08-30).
  `proj["stories"]` is set once, at generation time (`synergyai_app.py`
  around line 2291); the `story_editor`'s edited frame (`edited_df`,
  ~line 2298) is used locally for exports and to build test cases but
  never written back. `proj["test_cases"]` (~line 2319) has the same gap:
  the `tc_editor`'s edited frame (`edited_tc_df`, ~line 2332) is likewise
  never saved. `build_rtm_rows()` (~line 1521) and the Change Impact
  Analyzer's context builder both read `proj["stories"]`/
  `proj["test_cases"]` directly, so a BA who corrects a bad story or
  deletes a wrong test case in the table, then builds the RTM or runs a
  change-impact check, gets results based on the discarded version with
  no indication anything was dropped. Not a one-line fix: the story table
  is unrenamed (safe to write back as-is), but the test-case table is
  rendered with Title-Case column headers, so writing `edited_tc_df` back
  needs the same display-vs-storage split as the already-open "User
  Stories table shows raw dict keys" item above, not a trivial patch.

- **Six `generate_*` functions give no UI feedback when the AI validly
  returns an empty list** (raised 2026-08-30). Data Dictionary
  (`generate_data_dictionary`, line 1352, called ~2150), As-Is/To-Be
  (~2157), Stories (`generate_stories`, line 1399, called ~2280), Test
  Cases (`generate_test_cases`, line 1418, called ~2317), Glossary
  (`generate_glossary`, line 1445, called ~1846), and Prioritization
  (`generate_prioritization`, line 1463, called ~2079) all follow the
  pattern `if <rows>: <save + counters>` with no `else` — a real API
  failure and a legitimate "the AI found nothing here" response look
  identical to the end user (screen unchanged, no message). `analyze_gaps`
  already handles this correctly, showing `st.info("No significant gaps
  detected...")` even for zero results. Fixing this cleanly touches 6
  call sites and needs a wording/UX call (what should each of the six
  empty-state messages say), so left for a decision rather than an
  automated guess.

- **Generated download filenames never include the project name**
  (raised 2026-09-05). All `st.download_button(..., file_name=...)` call
  sites use fixed generic names (`test_cases.xlsx`,
  `business_glossary.xlsx`, `requirements_traceability_matrix.xlsx`,
  etc. — roughly 10 call sites across the file). A BA working several
  client projects in the same session gets identically-named files
  across projects, risking an accidental overwrite or mix-up once saved
  locally. The individual change (prefix each with a sanitized project
  name) is mechanically simple and needs no UX wording judgment, but it
  touches enough call sites, and enough already-downloaded-file naming
  conventions in the wild, that it's left for a decision rather than an
  automated sweep across all of them in one night.

- **Dashboard "drafted"/"found" counters mix additive and replace
  semantics** (raised 2026-09-06). `documents_drafted` (~line 2216,
  2223, 2230), `stories_drafted` (~2346), and `test_cases_drafted`
  (~2374) all increment (`+= len(...)`) every time the user
  regenerates, even though the underlying data (`proj["stories"]`,
  `proj["test_cases"]`, `proj["last_doc_draft"]`) is replaced, not
  appended to, on each regeneration. `glossary_terms_found` (~1919-1920),
  by contrast, is reassigned (`= len(terms)`) on every regeneration. A
  BA who regenerates User Stories three times (5 stories each time)
  sees "User Stories Drafted: 15" on the dashboard while the actual
  Story table has 5 rows; regenerating the glossary three times (10
  terms each time) shows "Glossary Terms: 10", not 30. The dashboard's
  own caption calls these "activity" metrics, so it's a real judgment
  call whether all four should read as cumulative activity or as a
  current count — not a one-line fix, needs a decision on intended
  semantics (and possibly a wording change either way).

- **Two tabs silently truncate carried-over context to 2,000
  characters, with no notice, unlike every other truncation point in
  the file** (raised 2026-09-06). Documentation Generator (~line
  2198-2202) and Story Creator (~line 2331-2335) both pre-fill their
  notes text area with `proj.get("extracted_text", "")[:2000]` when a
  project has no repository documents selected. Every other place the
  file truncates AI-bound text (the shared `truncate()`/`MAX_CHARS`
  15,000-char path) shows a `st.caption(...)` notice when it cuts
  something off; this 2,000-char slice does not. A BA who ran a
  10,000+ character gap analysis, then opens Documentation Generator or
  Story Creator with no repo docs selected, gets a silently truncated
  starting point and may generate a document from a fraction of their
  actual source material without any indication anything was cut.
  Whether the right fix is a truncation caption, raising the limit to
  match `MAX_CHARS`, or dropping the slice entirely is a UX call, not a
  mechanical one — left for a decision.

- **`.txt` uploads have no binary-content check, unlike Source URL
  fetches and zip-backed uploads** (raised 2026-09-07).
  `extract_text_from_upload`'s `.txt` branch (~line 1063-1071) falls
  back to `raw.decode("cp1252", errors="ignore")` whenever
  `utf-8-sig` decoding fails, and `cp1252` maps every byte 0-255 to
  some character, so that fallback can never itself raise. A binary
  file renamed to end in `.txt` (a screenshot or PDF saved with the
  wrong extension, plausible since `file_uploader(type=[...])` only
  filters by extension) is silently accepted as garbled "text" with no
  warning, and can reach an AI prompt as meaningless content — the
  same failure class already fixed for Source URL fetches
  (2026-09-05) and for zip-backed uploads (see today's entry below).
  The obvious fix is a binary-content heuristic before decoding (e.g.
  rejecting raw bytes containing a NUL byte), but that has a genuine
  tradeoff: a small number of real `.txt` files saved as UTF-16
  without a BOM would also contain NUL bytes and currently still
  decode (as garbled-but-non-erroring text) via the same cp1252
  fallback, so a NUL-byte reject would newly block a rare but genuine
  case. Whether that tradeoff is acceptable, and the exact wording, is
  a decision, not a mechanical fix.

- **No cap on repository size or document count per project** (raised
  2026-09-09). Individual uploads are size-capped (`MAX_UPLOAD_BYTES`,
  plus the zip-bomb guard), but nothing bounds how many documents or
  how much cumulative text a project's `proj["documents"]` list can
  hold (`st.file_uploader(..., accept_multiple_files=True)` with no
  batch or session limit, all held in `st.session_state`). Every
  downstream tab concatenates all *selected* repo docs into one
  prompt, bounded only at the AI-call layer by `MAX_CHARS` truncation,
  not before. A user repeatedly uploading large files can grow session
  memory without bound. The right cap (doc count vs. total chars vs.
  total bytes) and what happens at the limit (reject newest, warn-only,
  evict oldest) is a product decision, not a mechanical fix.

- **Chat transcript display is never trimmed, unlike what's sent to the
  API** (raised 2026-09-09). `st.session_state["chat_history"]` is
  rendered in full on every rerun (~line 2613-2634:
  `for msg in st.session_state["chat_history"]: st.chat_message(...)`),
  while only what's *sent to Claude* is capped
  (`_recent_chat_messages`, `MAX_CHAT_MESSAGES_SENT`). In a very
  long-lived session this means unbounded DOM/session-state growth for
  display, even though the original API-cost/context-limit problem is
  already solved. Minor, non-urgent — but capping *displayed* history
  is itself a UX call (truncate vs. paginate vs. "load earlier
  messages"), not a mechanical fix.

- **Individual chat messages are silently truncated for the API with no
  on-screen trace anywhere** (raised 2026-09-10). `_recent_chat_messages`
  (~line 1658-1679, `MAX_CHAT_MESSAGE_CHARS = 6000`) appends a
  `"[...truncated for length...]"` marker to any single message over
  6,000 characters, but only in the copy sent to Claude — the message
  stored in `chat_history` and rendered on screen is untouched, per the
  function's own docstring. Every other truncation point in the file
  (`truncate()`/`MAX_CHARS`) shows an `st.caption` notice when it cuts
  something off; this one shows nothing, anywhere. Distinct from the
  open "chat transcript display never trimmed" item directly above
  (that one is unbounded *display* growth over a long session; this is
  a truncation that already happens per-message today with zero visible
  trace). Whether to surface it — an inline caption under the sent
  message, a toast, or leaving it as intentionally invisible cost/
  context-limit plumbing — is a UX call, not a mechanical fix.

- **PDF embedded images are fully decompressed into memory before any
  size check runs, unlike docx/pptx uploads** (raised 2026-09-11).
  `extract_pdf_with_annotations()` (~line 881) accesses `img.data`
  (~line 926) to get each embedded image's raw bytes; pypdf inflates
  the image's compressed stream in full at that point.
  `_assert_safe_archive()` (~line 1027) guards zip-backed uploads
  (docx/pptx) against a decompression-bomb by checking each member's
  *declared* uncompressed size before extracting anything — PDFs have
  no equivalent pre-check. `MAX_IMAGE_BYTES` (~line 697) only runs
  afterward, inside `_prepare_image_for_vision()`, by which point the
  oversized buffer already exists in memory. PDF image streams
  commonly use DEFLATE-family compression (the same family zip uses),
  so a small, crafted PDF well under `MAX_UPLOAD_BYTES` could still
  contain a highly-compressible synthetic image that expands to a very
  large in-memory buffer during that single `.data` access — the same
  risk class the archive guard exists to close, via a different file
  format. A robust fix (checking declared pixel dimensions in the
  image's XObject dictionary before pypdf decodes it, mirroring what
  `_assert_safe_archive` does for zip sizes) needs verification against
  real adversarial PDF samples that aren't available in this routine;
  a partial fix (checking `len(img.data)` right after each image, before
  moving to the next) only bounds cumulative damage across a document's
  images, not the peak memory of decoding one crafted image — a
  genuine tradeoff, left for a decision rather than a guessed patch.

- **User-typed free text is echoed back through markdown-interpreting
  widgets, so a BA's own input can visibly mangle the page** (raised
  2026-09-12). `st.caption(f"Notes accounted for: \"{proj['last_notes'][:200]}\"")`
  (~line 2168) and `st.markdown(f"**Change request:** {latest['request_text']}")`
  / `st.markdown(f"**{prev['request_text']}**")` (~lines 2537, 2559) all
  interpolate raw text the BA typed into a `st.text_area` — not AI
  output — directly into a markdown-parsing call. A change request or
  note containing a leading `#`, an unmatched `**`, or a `---` line
  renders as a heading/broken bold run/rule instead of literal text. Not
  an XSS risk (`unsafe_allow_html` isn't set at any of these sites), just
  a rendering/copy bug. The obvious-looking fix (swap `st.markdown` for
  `st.write`) does not actually fix it — `st.write` on a plain string
  falls through to the same markdown renderer. A real fix needs either a
  small markdown-escaping helper before interpolation, or `st.text()`
  (which changes the visual style to monospace/preformatted) — a
  judgment call on the tradeoff, not a mechanical one-line patch, so left
  for a decision.

- **`fetch_url_text`'s per-chunk timeout doesn't bound the total time a
  Source URL fetch can take** (raised 2026-09-13). `requests.get(...,
  timeout=10, stream=True, ...)` (~line 1185) with `requests`, a
  `timeout` on a streamed response bounds connect time and the gap
  between successive reads, not total elapsed time — a server that
  trickles at least one byte every few seconds (deliberately or just
  slow) can keep the request open far longer than the 10s the code
  implies, all while staying under the existing `MAX_FETCH_URL_BYTES`
  size cap. A real gap, but closing it means tracking wall-clock time
  across the `iter_content` loop and picking a ceiling value (and
  whether that ceiling applies to the whole redirect chain or resets
  per hop) — a small design call, not a one-line patch, so left open
  rather than guessed at.

- **New project names are deduplicated case-sensitively** (raised
  2026-09-13). The "create project" flow (~line 1804) checks `new_name
  in st.session_state["projects"]`, a plain dict-key membership test, so
  "Alpha-FinTech Migration" and "alpha-fintech migration" are treated as
  two different projects. The code change itself is small
  (case-fold the comparison), but whether project names should be
  unique case-insensitively, and what to do about any existing
  differently-cased duplicates already sitting in a user's session, is
  a product decision rather than a mechanical fix.

---

## 2026-09-13

**Committed**

- `7b73389` Fix UTF-32 BOM misdetected as UTF-16 in .txt uploads
- `19c0eb8` Sort Business Glossary terms case-insensitively

**Worth knowing**

- A background review agent read `synergyai_app.py` end to end (all
  2676 lines, explicitly excluding every item already sitting in Open
  items above and everything already fixed in prior dated entries) and
  `requirements.txt` against actual imports — no drift (re-confirmed
  directly too: every top-level import maps to a pinned package or the
  stdlib, and every pinned package is used; `streamlit-authenticator` is
  unused in this file by design, documented as being for `auth.py`,
  which was not opened).
- **Fixed — a UTF-32-encoded `.txt` upload was silently decoded as
  UTF-16, producing garbled text with no error.** `extract_text_from_
  upload`'s `.txt` branch (~line 1078) checked only the first two bytes
  for a UTF-16 BOM (`\xff\xfe` or `\xfe\xff`), but a UTF-32 LE BOM's
  first two bytes are the identical `\xff\xfe` — `bytes.decode("utf-16")`
  on UTF-32 bytes doesn't raise, it just produces mojibake (confirmed
  directly: decoding UTF-32 LE-encoded "hello" as UTF-16 yields spaced-
  out garbage, not an exception). Fixed by checking the 4-byte UTF-32 LE
  and BE BOM patterns first, before the narrower 2-byte UTF-16 check.
  Verified standalone through the app's own code (not just in
  isolation): a UTF-32 LE upload now extracts cleanly, a UTF-16 LE
  upload is unaffected (regression check), and a plain UTF-8 upload is
  unaffected.
- **Fixed — the Business Glossary table sorted terms ASCII-case-
  sensitively, not alphabetically.** `gl_df.sort_values("Term")`
  (~line 1977) used pandas' default string sort, so every uppercase-
  initial term sorted before every lowercase-initial term (e.g. "Zebra"
  before "api") — confusing for a BA scanning an alphabetized glossary.
  Fixed with a case-folded sort key. Verified standalone: `["Zebra",
  "api", "Banana", "apple"]` now sorts to `["api", "apple", "Banana",
  "Zebra"]`.
- Two new open items raised above: `fetch_url_text`'s per-read (not
  total) timeout, and case-sensitive project-name deduplication. Both
  need a small design call (a timeout ceiling/strategy; a
  case-insensitive-uniqueness policy decision) rather than being
  mechanical fixes.
- `evals/latest_report.md` is still the same stale 2026-08-18 report
  (Nightly Evals Action still failing per the standing Open items entry
  — not re-investigated further tonight, no new evidence).
  `evals/LEARNED.md` still has no entries (open or closed) — nothing to
  act on or close there tonight.
- `auth.py`, `db.py`, `AUTH_ENABLED`, and `check_access()` were not
  touched or read beyond confirming import lines, per standing
  instructions. Confirmed no stale references to the deleted
  `otp_email.py` remain anywhere in the repo.
- `python3 -m py_compile synergyai_app.py` and `evals/run_evals.py
  --dry-run` both passed on the unmodified file before any change, and
  again after each of tonight's two commits; dependencies weren't
  preinstalled in this session's environment, so a throwaway venv was
  created from `requirements.txt` (as in prior nights) to run the
  dry-run check and the additional standalone verification described
  above — no changes to the environment's own packages.

## 2026-09-12

**Committed**

- `6fcbee4` Warn when a repo upload silently overwrites an existing
  document

**Worth knowing**

- A background review agent read `synergyai_app.py` end to end
  (~2666 lines, excluding everything already in Open items and every
  prior dated entry) looking for new, safe, narrowly-scoped issues.
  Two findings came back: the overwrite-warning gap fixed tonight, and
  the markdown-escaping issue above (left as suggest-only, per its own
  reasoning — the seemingly-obvious fix doesn't work, and severity is
  low/cosmetic, not security-relevant).
- **`6fcbee4` verified beyond compile/dry-run:** before committing, ran
  the upload handler's dedup/overwrite logic in isolation against three
  cases in the same batch (a name matching an existing repo document, a
  name repeated twice within the batch, and a genuinely new name) and
  confirmed the message correctly distinguishes "replaced an existing
  document" from "appeared more than once in this selection" and that
  the final repository still ends up with exactly one entry per name.
- `requirements.txt` was checked directly against actual imports in both
  `synergyai_app.py` and `auth.py`/`db.py`'s import lines — no drift.
- `evals/latest_report.md` is still the same stale 2026-08-18 report
  (Nightly Evals Action still failing per the standing Open items
  entry — not re-investigated further tonight, no new evidence).
  `evals/LEARNED.md` still has no entries (open or closed) — nothing to
  act on or close there tonight.
- `auth.py`, `db.py`, `AUTH_ENABLED`, and `check_access()` were not
  touched or read beyond confirming import lines, per standing
  instructions. Confirmed no stale references to the deleted
  `otp_email.py` remain anywhere in the repo.
- `python3 -m py_compile synergyai_app.py` and
  `evals/run_evals.py --dry-run` both passed on the unmodified file
  before any change, and again after tonight's edit; dependencies
  weren't preinstalled in this session's environment, so a throwaway
  venv was created from `requirements.txt` (as in prior nights) to run
  the dry-run check — no changes to the environment's own packages.

## 2026-09-11

**Committed**

- `e19a372` Fix Source URL fetch mojibake on pages with no Content-Type
  charset
- `f8673cf` Fix merged Word table cells duplicating text in extracted
  content

**Worth knowing**

- **`e19a372` root cause:** `requests` defaults `resp.encoding` to
  `ISO-8859-1` (RFC 2616) whenever a `Content-Type: text/html` response
  omits a `charset` param — which is the common case for UTF-8 pages
  that only declare their charset via a `<meta>` tag, since most modern
  sites do exactly that. The pre-existing `resp.encoding or "utf-8"`
  fallback never fired because that RFC default is truthy, not `None`,
  so every such page was decoded as Latin-1 and sent to Claude (and
  shown to the BA) as mojibake, with no error anywhere. Verified the
  exact behavior against the pinned `requests==2.34.2` directly before
  touching anything. Fix hands BeautifulSoup the raw bytes so its own
  sniffer (BOM / `<meta charset>`) does the work, only passing the
  header's encoding as a hint when the server actually declared one —
  tested all three cases (no header charset, explicit non-UTF-8 header
  charset with no `<meta>` tag, `text/plain`) with mocked responses
  before committing.
- **`f8673cf` root cause:** python-docx returns the identical `Cell`
  object once per grid column a horizontally-merged cell spans, so the
  original `[cell.text for cell in row.cells]` turned any merged
  header/grouping cell (common in requirements tables) into repeated
  text in the extracted line. Fix dedupes consecutive cells by object
  identity, not text content — verified directly with python-docx that
  this correctly leaves two *distinct* adjacent cells holding equal
  text alone, and that vertically-merged cells (a separate case, each
  row still correctly shows its own content) are unaffected.
- Both fixes went further than the background review agent's own
  report: the agent flagged the docx merge-duplication finding as
  "suggest only, not safe to auto-fix," citing no real merged-cell
  sample document to verify against. Before accepting that, a synthetic
  merged-cell `.docx` was built and run through the actual
  `extract_docx_with_formatting()` end-to-end (not just the isolated
  cell-iteration logic), which resolved the agent's stated uncertainty
  directly — the fix was then applied. The agent's third finding (PDF
  embedded-image decompression, below) was left as suggest-only for a
  different reason — no adversarial PDF sample was available to verify
  a fix against, and a partial fix only bounds cumulative damage rather
  than the actual risk — so that one is a new open item, not a fix.
- A background review agent read `synergyai_app.py` end to end
  (~2650+ lines, excluding everything already in Open items and every
  prior dated entry) looking for new, safe, narrowly-scoped issues.
  `requirements.txt` was checked directly against actual imports in
  both `synergyai_app.py` and `auth.py` — no drift (all third-party
  imports map onto a pinned requirement; standard-library imports need
  no entry).
- One new open item raised above: PDF embedded images are fully
  decompressed into memory before any size check runs, unlike zip-backed
  (docx/pptx) uploads which are checked before extraction.
- Checked the Nightly Evals GitHub Action directly: last night's
  scheduled run (#40, on `7c26e49`, the commit this routine started
  from tonight) failed with the standing symptom, same as every run
  since 2026-08-19. No new diagnostic information — status on the
  standing Open items entry is unchanged; not re-investigated further
  per that entry's own reasoning (a third guess at the same symptom
  isn't warranted without new evidence).
- `evals/LEARNED.md` still has no entries (open or closed) — nothing to
  act on or close there tonight.
- `auth.py`, `db.py`, `AUTH_ENABLED`, and `check_access()` were not
  touched or read beyond confirming import lines, per standing
  instructions. Confirmed no stale references to the deleted
  `otp_email.py` remain anywhere in the repo.
- `python3 -m py_compile synergyai_app.py` and
  `evals/run_evals.py --dry-run` both passed before each of tonight's
  two commits; dependencies weren't preinstalled in this session's
  environment, so a throwaway venv was created from `requirements.txt`
  (as in prior nights) to run the dry-run check and the additional
  targeted functional verification described above — no changes to the
  environment's own packages.

## 2026-09-10

**Committed**

- `fbb8436` Truncate change_request_text before sending to the API, like
  every other primary AI input (this single commit also carries the
  Process Transcript fix below — see Worth knowing)

**Worth knowing**

- A background review agent read `synergyai_app.py` end to end (all
  ~2650 lines, explicitly excluding every item already sitting in Open
  items above and everything already fixed in prior dated entries) and
  `requirements.txt` against actual imports in both `synergyai_app.py`
  and `auth.py`'s import lines — no drift.
- **Fixed — `generate_change_impact()`'s `change_request_text` was the
  one primary AI-input field in the file with no `truncate()`/
  `MAX_CHARS` guard.** Verified directly by reading the function and
  its only call site (~line 2504, Change Request Impact Analyzer):
  `change_request_text` comes from an unbounded `st.text_area` with no
  `max_chars`, while the function's other argument (`existing_context`)
  was already truncated two lines below with a caption. A BA pasting a
  long change request (e.g. a multi-paragraph email thread) had it sent
  to the API completely unbounded with no notice. Now truncated with
  the identical pattern already used for `existing_context`.
- **Fixed — the Process Transcript button showed a second, redundant
  "Couldn't extract any readable text" error stacked on top of
  `extract_text_from_upload`'s own message.** Verified directly that
  `extract_text_from_upload` already shows a specific `st.error`/
  `st.warning` on every code path that returns empty text for the only
  two file types this uploader accepts (`.txt`, `.docx`); the call site
  (~line 1977) then added its own generic error on the same condition.
  Matches the file's two other call sites of `extract_text_from_upload`,
  neither of which double-messages. Fix removes the duplicate; the
  branch that skips `process_meeting()` on empty text is unchanged.
- Both fixes above landed in a single commit (`fbb8436`) rather than
  two separate ones — a staging oversight, not intentional bundling.
  Each was independently verified before being applied and is
  self-contained; noted here so the commit list above isn't misread as
  one fix covering two unrelated call sites.
- One new open item raised above: individual chat messages are
  silently truncated for the API with no on-screen trace anywhere —
  distinct from the already-open "chat transcript display never
  trimmed" item, which is about unbounded *display* growth, not this
  invisible per-message truncation.
- Checked the Nightly Evals GitHub Action directly: last night's
  scheduled run (#39, on `b2d5595`, the commit this routine started
  from tonight) failed with the identical
  `[st.error] AI request failed: Connection error.` symptom on every
  one of the 7 fixtures, same as every run since 2026-08-19. No new
  diagnostic information — status on the standing Open items entry is
  unchanged.
- `evals/LEARNED.md` still has no entries (open or closed) — nothing to
  act on or close there tonight.
- `auth.py`, `db.py`, `AUTH_ENABLED`, and `check_access()` were not
  touched or read beyond confirming import lines, per standing
  instructions. Confirmed no stale references to the deleted
  `otp_email.py` remain anywhere in the repo.
- `python3 -m py_compile synergyai_app.py` and
  `evals/run_evals.py --dry-run` both passed before committing;
  dependencies weren't preinstalled in this session's environment, so a
  throwaway venv was created from `requirements.txt` to run the
  dry-run check (no changes to the environment's own packages).

## 2026-09-09

**Committed**

- `1df5b19` Warn when duplicate filenames in one upload batch silently
  overwrite each other

**Worth knowing**

- A background review agent read `synergyai_app.py` end to end (all
  ~2634 lines, explicitly excluding every item already sitting in Open
  items above and everything already fixed in prior dated entries) and
  `requirements.txt` against actual imports — no drift, confirmed
  directly (every top-level import in `synergyai_app.py` and the
  import lines of `auth.py` map to a pinned package or the stdlib).
- **Fixed — the "Add to Repository" button's success count didn't
  reflect that two files with the same name in one upload batch
  silently overwrite each other.** `add_doc_to_repo()` (~line 547)
  dedupes by name, replacing any existing document with a matching
  name; the button handler (~line 1810) counted every processed file
  toward "Added N document(s)" with no check for same-batch name
  collisions, so a user who selected two same-named files (plausible
  via drag-and-drop from different folders, or multiple file-picker
  invocations before hitting the button) silently lost the first
  file's content with a success message implying nothing was lost.
  Verified directly by reading `add_doc_to_repo` and the call site
  before fixing. Fix tracks repeated filenames within the batch and
  appends a note to the success message naming them and stating only
  the last version of each was kept — narrow, self-contained, no
  AI/prompt/auth involvement, no change to the underlying
  last-write-wins storage behavior.
- Two new open items raised above from the same review: no cap on
  repository size/document count per project, and the chat transcript
  display growing unbounded (only what's sent to the API is capped).
  Both are product/UX decisions (what limit, what happens at the
  limit, truncate vs. paginate), not mechanical fixes.
- Checked the Nightly Evals GitHub Action directly (not just the stale
  `evals/latest_report.md`, still dated 2026-08-18): last night's run
  (#38, on `3c286ba`) failed with the identical
  `[st.error] AI request failed: Connection error.` symptom on every
  fixture, same as every run since 2026-08-19. No new diagnostic
  information — status on the standing Open items entry is unchanged.
- `evals/LEARNED.md` still has no entries (open or closed) — nothing
  to act on or close there tonight.
- `auth.py`, `db.py`, `AUTH_ENABLED`, and `check_access()` were not
  touched or read beyond confirming import lines / docstring headers,
  per standing instructions. Confirmed no stale references to the
  deleted `otp_email.py` remain anywhere in the repo.
- `python3 -m py_compile synergyai_app.py` and
  `evals/run_evals.py --dry-run` both passed before committing;
  `bs4`/other dependencies weren't preinstalled in this session's
  environment, so a throwaway venv was created from `requirements.txt`
  to run the dry-run check (no changes to the environment's own
  packages).

## 2026-09-08

**Committed**

- `3dae7f7` Show empty-state messages for Key Decisions, Recommended Next
  Actions, and Workshop Prep agenda/questions

**Worth knowing**

- A background review agent read `synergyai_app.py` end to end (all 2624
  lines, explicitly excluding every item already sitting in Open items
  above and everything already fixed in prior dated entries) and
  `requirements.txt` against actual imports — no drift.
- **Fixed — three more fields silently render nothing when the AI validly
  returns an empty list, same bug class as the already-open "six
  `generate_*` functions give no UI feedback on an empty result" item but
  in three different functions not on that item's list.** `process_meeting`
  (~line 1981) showed no message at all for an empty `decisions` list, even
  though `action_items` two lines below it already has an explicit `else:
  st.caption(...)` for the same case. `generate_change_impact` (~line 2508)
  had the identical gap for `recommended_actions`, with `affected_
  requirements` directly above it already handling it. `generate_workshop_
  prep` (~line 2036-2047) had it for both `agenda` and `questions`, with no
  sibling field in that block handling it either way. All three verified
  by reading the exact code (not just the agent's report) before fixing;
  each fix copies the sibling `else: st.caption(...)` idiom already
  present and working in the same function, so no new UX wording was
  invented — this is why these were safe to fix directly rather than left
  for the standing open item (that one needs a wording decision across six
  *different* functions that have no existing sibling pattern to copy).
- Two secondary observations came up but weren't logged as new open items:
  (1) the "Build / Refresh RTM" button fully overwrites `proj["rtm_rows"]`
  from scratch, discarding any hand-edits made in the RTM's own
  `st.data_editor` if the user regenerates afterward — same class of gap
  as the already-open "editor edits never written back to project state"
  item, just widening it to a fourth table (RTM) rather than a separate
  issue, matching how the Glossary/RTM widening was handled on 2026-08-30;
  (2) `fetch_url_text`'s Content-Type check (added 2026-09-05) only
  rejects a fixed list of known-binary types, so a server that omits the
  header entirely still sails through to the HTML parser — narrow,
  low-likelihood in practice, and adjacent to the already-open `.txt`
  binary-content item rather than a new decision on its own.
- Checked the Nightly Evals GitHub Action run history directly: last
  night's scheduled run (#37, on `82f6aab`) also failed, identical shape
  and identical `[st.error] AI request failed: Connection error.` symptom
  on every fixture as every run since 2026-08-19. No new diagnostic
  information in the job log beyond what's already in the standing Open
  items entry — status unchanged, no new guess warranted.
- `evals/LEARNED.md` still has no entries (open or closed) — nothing to
  act on or close there tonight.
- `auth.py`, `db.py`, `AUTH_ENABLED`, and `check_access()` were not
  touched or read beyond confirming their locations/import lines, per
  standing instructions.

## 2026-09-07

**Committed**

- `a8658ec` Catch all zipfile parse failures, not just
  BadZipFile/OSError, in archive safety check

**Worth knowing**

- A background review agent read `synergyai_app.py` end to end
  (explicitly excluding every item already sitting in Open items
  above and everything already fixed in prior dated entries) and
  `requirements.txt` against actual imports — no drift (every
  installed package version in a fresh venv matched the file's pins
  exactly, `pip list` cross-checked against `requirements.txt`).
- **Fixed — a corrupted zip-backed upload (.docx/.pptx/.xlsx) with a
  malformed central-directory filename entry crashed the app instead
  of showing the existing "isn't a readable Office document" message.**
  `_assert_safe_archive` (~line 1016) only caught
  `zipfile.BadZipFile`/`OSError` around
  `zipfile.ZipFile(uploaded_file)`, but the constructor can also raise
  `UnicodeDecodeError` while parsing a central-directory entry whose
  UTF-8 flag bit is set but whose filename bytes aren't valid UTF-8 —
  confirmed directly with a hand-crafted malformed zip reproducing the
  exact exception, not just by reading the code. Neither the
  function's own except clause nor the call site (which only catches
  `ValueError`) covered that, so the exception propagated fully
  unhandled, crashing that Streamlit run with a raw traceback. Widened
  the except clause to `Exception`, matching the same broad-except
  pattern the rest of `extract_text_from_upload` already uses for
  every other parsing failure. Verified standalone (loaded through
  evals' own `streamlit_shim`): the malformed-zip case now raises the
  friendly `ValueError`; a plain garbage-bytes upload and a valid
  archive are both unaffected.
- One new open item raised above (`.txt` uploads silently accepting
  binary content via the cp1252 fallback) — real gap, same class
  already fixed for Source URLs and zip-backed uploads, but the
  obvious fix (a NUL-byte check) has a genuine edge-case tradeoff
  against non-BOM UTF-16 text files, so left for a decision rather
  than guessed at.
- Checked the Nightly Evals GitHub Action run history directly (not
  `evals/latest_report.md`, still dated 2026-08-18, or
  `evals/LEARNED.md`, still no entries): last night's scheduled run
  (#36, on `e017bbe`) also failed, identical shape to every run since
  2026-08-19 (`Run eval harness` step fails, `Commit results` step
  skipped). No new information — status on the standing Open items
  entry is unchanged.
- `auth.py`, `db.py`, `AUTH_ENABLED`, and `check_access()` were not
  touched or read beyond confirming their locations/import lines, per
  standing instructions.

## 2026-09-06

**Committed**

- `928931d` Warn instead of silently calling the AI when the story
  table is empty for test-case generation

**Worth knowing**

- A background review agent read `synergyai_app.py` end to end
  (explicitly excluding every item already sitting in Open items above
  and everything already fixed in prior dated entries) and
  `requirements.txt` against actual imports — no drift (also verified
  directly: every top-level import in `synergyai_app.py`, plus the
  import block at the top of `auth.py` — nothing else in that file —
  maps to one of the 11 pinned packages, and every pinned package is
  used). Every installed package version in a fresh venv matched the
  file's pins exactly (`pip list` cross-checked against
  `requirements.txt`).
- **Fixed — "Generate Test Cases" called the AI with an empty prompt
  when the story table was emptied.** The story `data_editor`
  (~line 2352) has `num_rows="dynamic"`, so a user can delete every row
  in one action. `edited_df.to_dict("records")` was then passed
  straight to `generate_test_cases()` (~line 2371) with no check,
  unlike every sibling "Generate ..." button in the file (User
  Stories, Prioritization, Change Impact, Glossary), which all warn and
  skip the AI call when their input is empty. Verified the gap
  directly by reading the call site and confirming `stories` (the
  value checked at ~line 2349, before the expander renders) and
  `edited_df`/`story_records` (the value actually sent, after any
  in-table edits) are different values — so a non-empty initial
  generation does not protect against an empty edited table at click
  time. Fixed by checking `story_records` for emptiness immediately
  before the AI call and showing "Add at least one user story first."
  (same short, direct wording style as every other in-file warning of
  this kind) instead of calling the AI. No change to the empty-result
  UX-feedback question already sitting in Open items above — this is a
  different gap (empty *input*, not an empty *AI response*).
- Two new open items raised above (dashboard counter semantics, silent
  2,000-char truncation in two tabs) — both are real, narrowly-scoped
  UX questions surfaced by tonight's review, but each needs a wording/
  design decision rather than being a mechanical fix, so neither was
  acted on.
- Checked the Nightly Evals GitHub Action run history directly (not
  `evals/latest_report.md`, still dated 2026-08-18, or
  `evals/LEARNED.md`, still no entries): last night's scheduled run
  (#35, on `a0005d8`) also failed, identical shape to every run since
  2026-08-19 (`Run eval harness` step fails, `Commit results` step
  skipped). No new information — status on the standing Open items
  entry is unchanged.
- `auth.py`, `db.py`, `AUTH_ENABLED`, and `check_access()` were not
  touched or read beyond confirming their locations/import lines, per
  standing instructions.

## 2026-09-05

**Committed**

- `8325cf1` Preserve hyperlinked text in .docx extraction; reject binary
  content when fetching Source URLs

**Worth knowing**

- A background review agent read `synergyai_app.py` end to end
  (explicitly excluding every item already sitting in Open items above
  and everything already fixed in prior dated entries) and
  `requirements.txt` against actual imports — no drift. One high-
  confidence finding and three borderline observations came back; the
  high-confidence one plus a second candidate surfaced while verifying it
  were independently re-verified against the pinned dependency versions
  (`python-docx==1.2.0`) and standalone constructed test files before
  being fixed.
- **Fixed — `fetch_url_text` decoded binary responses as garbled "text"
  with no Content-Type check.** The function downloaded and decoded the
  entire response body before ever looking at `Content-Type`, then fed
  anything that wasn't `text/plain` straight into
  `BeautifulSoup(body, "html.parser")`, which never raises on garbage
  input. Pasting a link to a PDF, image, or other binary file (plausible
  in this workflow — a BA linking to a spec sheet or exported diagram
  instead of a webpage) silently added decoded-binary noise to the
  project's document repository and downstream AI prompts, with no error
  shown. Fixed by checking `Content-Type` immediately after the response
  headers arrive (before downloading or decoding the body) and rejecting
  known-binary types (`image/*`, `video/*`, `audio/*`, `font/*`, PDF,
  zip, octet-stream, legacy Office formats) with a clear
  `st.error`-surfaced message, via the same `ValueError` path
  `_assert_public_url`'s SSRF check already uses. Verified standalone:
  PDF and image content types are rejected before any body bytes are
  read; HTML, `text/plain`, and pages with a missing/empty Content-Type
  header are unaffected; a JSON content-type is deliberately not
  rejected (falls through to the existing HTML-parser path unchanged —
  not the failure mode this fix targets).
- **Fixed — `.docx` hyperlinked text silently dropped when mixed with
  plain text in the same paragraph.** `extract_docx_with_formatting`
  (~line 810) iterated `para.runs` to rebuild each paragraph's text with
  markdown-style bold/italic/strikethrough markers. python-docx does not
  include a paragraph's hyperlinks in `.runs` — a hyperlink's runs live
  under a separate `Hyperlink` object — so a paragraph like "See
  attached: `<link>policy document</link>` for details." kept the plain
  text but dropped "policy document" entirely, with no warning. The
  existing `if not para.runs: ... para.text` fallback only covered a
  paragraph that was *entirely* a hyperlink (a real case, already
  working); a mixed paragraph has non-empty `para.runs` from its plain
  text, so it never hit that fallback. Verified directly against the
  pinned `python-docx==1.2.0`: `Paragraph.text` does include hyperlink
  text (confirmed from its docstring and by inspection), which is why
  the hyperlink-only case worked and masked this gap. Fixed by iterating
  `para.iter_inner_content()` instead and pulling a `Hyperlink`'s own
  `.runs` in place, preserving both document order and per-run
  bold/italic/strike formatting. Verified standalone with constructed
  `.docx` files covering mixed plain+hyperlink+plain, hyperlink-only,
  plain-only, bold-plain, and bold-hyperlink paragraphs — only the mixed
  case changed output (hyperlink text now included), all others
  byte-for-byte unaffected.
- Two borderline observations came up but weren't logged as open items
  since neither needs a decision on its own: (1) the Glossary and RTM
  `st.data_editor` tables have the same never-written-back-to-project-
  state gap as the already-open Story/Test Case editor item above — just
  widening that item's known scope, not a separate issue; (2) one more
  `generate_*` function (`generate_document`, the Documentation
  Generator's markdown path) may share the already-open "no UI feedback
  on a valid empty AI result" pattern — plausible but very rare in
  practice for a free-text generation call, not independently verified,
  and covered by the same open decision as the six already listed.
- Checked the Nightly Evals GitHub Action run history directly (not
  `evals/latest_report.md`, still dated 2026-08-18, or `evals/LEARNED.md`,
  still no entries): last night's scheduled run (#34, on `a050c98`) also
  failed, same shape and same `[st.error] AI request failed: Connection
  error.` symptom on every fixture as every run since 2026-08-19. No new
  information — status on the standing Open items entry is unchanged.
- `evals/LEARNED.md` has no entries (open or closed) — nothing to act on
  or close there tonight.
- `auth.py`, `db.py`, `AUTH_ENABLED`, and `check_access()` were not
  touched or read beyond confirming their locations, per standing
  instructions.

## 2026-09-04

**Committed**

- `3423252` Fix header-only CSV/XLSX uploads being treated as empty
- `6f5bdf5` Move PDF "no extractable text" warning to after annotations/images
  are appended

**Worth knowing**

- A background review agent read `synergyai_app.py` end to end (explicitly
  excluding every item already sitting in Open items above and everything
  already fixed in prior dated entries) and `requirements.txt` against actual
  imports — no drift. Two candidate findings came back; both were
  independently re-verified against the actual file and standalone test
  scripts before being fixed. One initial candidate (stale `st.multiselect`
  selections after a document is removed) was checked against the pinned
  `streamlit==1.62.0` source and ruled out — the widget already filters stale
  values out of session state rather than raising, so it was never a bug.
- **Fixed — header-only CSV/XLSX uploads discarded their column names.**
  `extract_text_from_upload` (line ~1072/1078) used `df.empty` to decide
  whether a CSV/XLSX upload had extractable text, but `df.empty` is `True`
  whenever a DataFrame has zero *rows*, even if it has real column headers.
  Verified directly against the pinned `pandas==3.0.5`: a CSV with a header
  row and no data rows (e.g. `Name,Email,Phone\n`, the shape of a Data
  Dictionary starter template a BA would plausibly upload) round-trips to
  `df.empty == True`, so the header text was silently discarded and the
  file reported as empty via a misleading "it may be empty" warning. Same
  root cause for an XLSX sheet with only a header row. Fixed by checking
  `len(df.columns) > 0` instead, at both call sites. Verified standalone
  (loading the app through evals' own `streamlit_shim`) that: a header-only
  CSV now keeps its column names in the extracted text; a genuinely empty
  sheet (no header, no data — `len(df.columns) == 0`) still produces empty
  text and still triggers the warning, so that path wasn't weakened; and a
  normal data CSV/XLSX is byte-for-byte unaffected.
- **Fixed — PDF "may be scanned/image-only" warning fired before
  annotations/images were appended to the extracted text.**
  `extract_pdf_with_annotations` (line ~884) checked `text.strip()` against
  the raw page-text layer only, before reviewer-comment annotations (~897)
  and vision-described images (~916) were appended to that same `text`
  variable and returned. A scanned PDF with no text layer but with sticky-
  note comments or embedded screenshots showed the "it may be a
  scanned/image-only document" warning even though the function went on to
  populate `text` with real, usable content from those sources — misleading
  for exactly the kind of document (a scanned/annotated PDF) this pipeline
  exists to handle. Moved the check to the end of the function, after every
  source (page text, annotations, vision descriptions) has had a chance to
  contribute. Verified standalone with a real pypdf-built PDF: a text-less
  page carrying only a sticky-note annotation no longer triggers the
  warning (the annotation content is genuinely present in the returned
  text), while a truly empty page (no text, no annotations, no images)
  still triggers it exactly as before.
- Checked the Nightly Evals GitHub Action run history directly (not
  `evals/latest_report.md`, still dated 2026-08-18, or `evals/LEARNED.md`,
  still no entries): last night's scheduled run (#33, on `399e786`) also
  failed, same shape as every run since 2026-08-19 (`Run eval harness` step
  fails, `Commit results` step skipped). No new information — status on the
  standing Open items entry is unchanged.
- `evals/LEARNED.md` has no entries (open or closed) — nothing to act on or
  close there tonight.
- `auth.py`, `db.py`, `AUTH_ENABLED`, and `check_access()` were not touched
  or read beyond confirming their locations, per standing instructions.

## 2026-09-03

**Committed**

- `f45beb0` Cap per-image byte size before vision decode; fix alpha
  flattening and image ordering

**Worth knowing**

- A background review agent read `synergyai_app.py` end to end (all 2572
  lines, explicitly excluding every item already sitting in Open items
  above and everything already fixed in prior dated entries). Four
  candidate findings came back; three were verified and fixed, one was
  judged too trivial to act on or log.
- **Fixed — missing per-image size cap.** `MAX_UNCOMPRESSED_BYTES` (200MB)
  only bounds the *whole* zip-backed archive's declared uncompressed size
  (`_assert_safe_archive`); it does nothing to stop one single embedded
  image from being close to that entire budget. `_prepare_image_for_vision`
  (line ~698) had no independent check before handing bytes to
  `Image.open()`. Added a 15MB `MAX_IMAGE_BYTES` check at the top of that
  function, using the same silent-skip-to-`None` path already used for an
  unreadable image — no new failure mode, no downstream change. Note for
  context: PIL's own default `Image.MAX_IMAGE_PIXELS` guard already catches
  true pixel-count decompression bombs (raises `DecompressionBombError`,
  caught by the function's existing broad `except Exception`), so this
  fix closes the *byte-size* gap specifically — a large-but-legal image
  well under PIL's pixel-count ceiling could still be tens or hundreds of
  MB and force an expensive decode with nothing stopping it before now.
- **Fixed — alpha channel silently dropped, not flattened.**
  `img.convert("RGB")` on an RGBA/transparent source (same function)
  discards alpha directly rather than compositing onto a background first,
  so a transparent PNG screenshot/diagram embedded in a doc could reach
  Claude vision with black or undefined-color regions where it should read
  as blank — degrading description quality on exactly the kind of content
  (UI screenshots, diagrams) this pipeline exists to read accurately. Now
  composites onto a white background before converting, only when the
  source actually has an alpha channel (RGBA/LA/P-with-transparency);
  plain RGB sources are untouched. Verified standalone: a fully-transparent
  RGBA test image now round-trips to a white pixel instead of black.
- **Fixed — image descriptions matched to images by position, not the
  model's own `image_number`.** `IMAGE_ANALYSIS_SCHEMA` requires the model
  to return a 1-based `image_number` per entry specifically so answers can
  be matched back to the image sent, but `describe_images_with_vision`
  (line ~756) never read that field — it just iterated the returned array
  in order and re-numbered by position. If the model's array order ever
  diverged from input order for even one image, the description attributed
  to "image 3" would silently be describing a different image, with
  nothing to catch it. Now sorts by `image_number` when it's a clean
  1..n permutation of the batch; falls back to original order otherwise
  (a missing/duplicate number is more likely a minor model slip than a
  sign the whole batch is untrustworthy). Verified standalone with an
  out-of-order two-item list.
- **Not acted on, not logged as an open item** — too trivial to need a
  decision, just noting it: `extract_text_from_upload` (line ~1019) derives
  the extension as `name.split(".")[-1]`, so a file with no extension at
  all (some OS file pickers allow bypassing the uploader's `type=[...]`
  filter via "All files") produces a confusing error like
  `Unsupported file type: .myfile` — a stray dot prepended to the whole
  filename rather than a real extension. Narrow, rare, cosmetic-only.
- All three fixes verified with a standalone script loading
  `synergyai_app.py` through evals' own `streamlit_shim` (oversized bytes
  rejected, a normal RGB image still round-trips, a transparent RGBA image
  composites to white) before committing, in addition to
  `python3 -m py_compile` and `evals/run_evals.py --dry-run`.
- Checked the Nightly Evals GitHub Action run history directly (not
  `evals/latest_report.md`, still dated 2026-08-18, or `evals/LEARNED.md`,
  still no entries): last night's scheduled run (#32, on `30ed1fb`) also
  failed — same shape as every run since 2026-08-19 (`Run eval harness`
  step fails, `Commit results` step skipped). No new information — status
  on the standing Open items entry is unchanged.
- `evals/LEARNED.md` has no entries (open or closed) — nothing to act on
  or close there tonight.
- `auth.py`, `db.py`, `AUTH_ENABLED`, and `check_access()` were not
  touched or read, per standing instructions.

## 2026-09-02

**Committed**

- `29afaac` Add UTF-8 BOM to CSV downloads so Excel renders non-ASCII
  content correctly

**Worth knowing**

- All four `st.download_button(..., <df>.to_csv(index=False), ...,
  mime="text/csv")` call sites (Meeting Action Items line 1955,
  Prioritization line 2126, Backlog Stories line 2318, Test Cases line
  2352) passed a plain `str` payload. Verified directly against the
  pinned `streamlit==1.62.0` source
  (`runtime/download_data_util.py::convert_data_to_bytes_and_infer_mime`):
  a `str` payload is encoded via bare `.encode()` (UTF-8, no BOM); the
  app's own `mime="text/csv"` argument is used as-is regardless of the
  function's inferred mimetype, so switching to a `bytes` payload has no
  other effect. Windows Excel opened by double-click decodes a BOM-less
  CSV using the system codepage, not UTF-8, so any accented name, em
  dash, or curly quote coming out of the AI (common in generated content)
  would render as mojibake. Fixed by encoding with `utf-8-sig` instead of
  plain `str`, at all four sites — the same encoding the app already
  treats as correct on the upload side (2026-08-31 fix). Verified
  standalone with non-ASCII sample data: the BOM is present and
  `.decode("utf-8-sig")` round-trips to the original CSV text exactly.
- Full pass tonight: a background review agent read `synergyai_app.py`
  end to end (explicitly excluding every item already sitting in Open
  items above and everything already fixed in prior dated entries) and
  `requirements.txt` against actual imports — no drift found. The CSV/BOM
  finding above was independently re-verified (exact line numbers,
  streamlit source, and a standalone encode/decode check) before being
  fixed. Two borderline items came up that weren't logged as new open
  items since neither needs a decision, just noting them: (1)
  `build_docx_from_markdown` strips `**`/`*`/`~~` markers via plain
  string replacement rather than applying real bold/italic/strikethrough
  Word runs, so emphasis and struck-through content are visually
  indistinguishable in the exported .docx — real fidelity gap, but fixing
  it means run-level formatting logic, not a one-line change; (2) several
  more `generate_*` functions' free-typed suggestion/focus fields
  (`generate_document`, `generate_data_dictionary`, `generate_asis_tobe`,
  `generate_glossary`, `generate_prioritization`, `generate_workshop_prep`)
  aren't routed through `truncate()`/`MAX_CHARS`, same class of thing
  already discussed and left alone for `analyze_gaps`'s "Additional
  Notes" field on 2026-08-30 (operator-typed, realistically short) — just
  noting it's not only that one call site.
- Checked the Nightly Evals GitHub Action run history directly (not
  `evals/latest_report.md`, still dated 2026-08-18, or `evals/LEARNED.md`,
  still no entries): last night's scheduled run (#31, on `4a05258`) also
  failed, same `[st.error] AI request failed: Connection error.` symptom
  on every fixture as every run since 2026-08-19. No new information —
  status on the standing Open items entry is unchanged.
- `auth.py`, `db.py`, `AUTH_ENABLED`, and `check_access()` were not
  touched or read beyond confirming their locations, per standing
  instructions.

## 2026-09-01

**Committed**

- `a93099f` Guard generate_test_cases against NaN/None leaking into the AI
  prompt as "nan"

**Worth knowing**

- Resolved the previously-unconfirmed "nan" open item (raised 2026-08-30)
  rather than leaving it open again. The live Streamlit widget isn't
  reachable from this container, so instead of guessing, verified the
  underlying pandas mechanics directly: a DataFrame column with a blank
  cell round-trips through `.to_dict("records")` as a real float `NaN` (or
  `None`), and `s.get(k) or ''` doesn't catch that because `NaN` is truthy
  in Python — `str(nan)` ("nan") would flow straight into the AI prompt.
  Fixed `generate_test_cases()` by routing the three story fields through
  `_blank_or_value()`, the same helper already used elsewhere in the file
  for exactly this NaN-vs-real-value distinction (originally added for
  Excel/Word cell values) — no new logic. Verified with a standalone
  script, loading `synergyai_app.py` through evals' own `streamlit_shim`,
  that a NaN/None story field now renders as an empty string in the built
  prompt text instead of "nan". This closes the item without needing to
  drive the actual `st.data_editor` widget in a browser: the fix is
  correct regardless of whether Streamlit fills a blank cell with `NaN` or
  `None`, since `_blank_or_value()` (via `pd.isna()`) treats both the same.
- Checked the Nightly Evals GitHub Action run history directly (not
  `evals/latest_report.md`, still dated 2026-08-18, or `evals/LEARNED.md`,
  still no entries): last night's scheduled run (#30, on `2dde763`) also
  failed, same symptom as every run since 2026-08-19. No new information —
  status on the standing Open items entry is unchanged.
- Full pass tonight read `synergyai_app.py` end to end directly (all
  ~2570 lines) and checked `requirements.txt` against actual imports in
  both `synergyai_app.py` and `auth.py` (imports only, not the rest of
  `auth.py`) — no drift. Re-checked every `unsafe_allow_html=True` call
  site for the 2026-08-29 XSS pattern (user-controlled text interpolated
  into raw HTML) — the two fixed then are still the only two; every other
  site passes only static strings. `auth.py`, `db.py`, `AUTH_ENABLED`, and
  `check_access()` were not touched or read beyond confirming their
  imports/locations. No other item looked both safe and self-contained
  enough to act on tonight — everything else that came up either matched
  an item already sitting in Open items above or wasn't confidently minor.

## 2026-08-31

**Committed**

- `dbc875d` Add missing FORMATTING_GUIDANCE to two AI calls; fix stale
  workshop-prep title; add CSV encoding fallback

**Worth knowing**

- `FORMATTING_GUIDANCE` (the constant that tells the model `**bold**` =
  critical/non-negotiable, `~~strikethrough~~` = removed/historical, and a
  "Reviewer Comments" section = stakeholder feedback) is appended to eight
  of the ten functions that consume raw extracted document text; two —
  `generate_workshop_prep` and `generate_change_impact` — were missing it,
  even though both are fed `proj["extracted_text"]` verbatim (workshop
  prep at line ~1969, change impact at line ~2413). A document with
  struck-through legacy content could have had workshop questions or a
  change-impact assessment built as if that removed content were still
  live requirements. Fixed by appending the same constant, no new logic.
- The Workshop Prep download's `.md` title read the live `focus_area`
  text_input widget value, not the value actually used to generate the
  content (`proj["workshop_prep"]` stores the result but never the focus
  text it was generated from). Editing the focus box after generating,
  then downloading without regenerating, produced a downloaded document
  whose title didn't match its body. Fixed the same way the file already
  handles this for the Documentation Generator (`proj["last_doc_type"]`
  stored alongside `proj["last_doc_draft"]` specifically so the displayed
  label can't drift from the live widget) — added `proj["workshop_prep_focus"]`
  and read it back instead of the live widget.
- CSV upload (`extract_text_from_upload`) had no encoding fallback,
  unlike the `.txt` branch in the same function, which already handles
  UTF-16 BOM, `utf-8-sig`, and a `cp1252` fallback. A CSV exported from
  Excel with curly quotes, accented names, or currency symbols is
  commonly `cp1252`/`latin-1`, and previously failed with a raw decode
  error surfaced via the generic exception handler instead of just being
  read. Added the same `try/except UnicodeDecodeError` → retry with
  `cp1252` pattern the `.txt` branch already uses.
- Full pass tonight: a background review agent read `synergyai_app.py`
  end to end (explicitly excluding every item already sitting in Open
  items above) and `requirements.txt` against actual imports — no drift
  found there, and `streamlit-authenticator` being present but unimported
  at module level is correct (it's used inside `auth.py`, which was not
  read beyond confirming that). Every candidate finding was independently
  re-verified against the actual file (line numbers, call sites, and the
  existing `last_doc_type` precedent) before being fixed. `auth.py`,
  `db.py`, `AUTH_ENABLED`, and `check_access()` were not touched or read.
- One borderline item came up that wasn't logged as an open item since it
  doesn't need a decision, just noting it: `extract_docx_with_formatting`
  and `extract_pptx_with_formatting` both silently drop "Reviewer
  Comments" extraction on any exception (~line 810-813) with no
  user-facing warning. This mirrors the app's established "bonus signal,
  degrade silently" design already used explicitly for image description
  (documented in `describe_images_with_vision`'s docstring) — plausibly
  intentional consistency rather than an oversight, just without an
  explicit comment saying so at that specific spot. Not confident enough
  either way to change it.
- Checked the Nightly Evals GitHub Action run history directly (not
  `evals/latest_report.md`, still dated 2026-08-18, or `evals/LEARNED.md`,
  still no entries): last night's scheduled run (#29, on `85d37ab`) also
  failed, same symptom as every run since 2026-08-19. No new information
  — status on the standing Open items entry is unchanged.
- `evals/run_evals.py --dry-run` and `python3 -m py_compile
  synergyai_app.py` both required a working `requests`/`bs4`/`pandas`/etc.
  install to run at all; this container had no packages installed, so
  they were run inside an isolated venv (`pip install -r
  requirements.txt`) built fresh for tonight's checks rather than into
  system Python. Both passed cleanly before and after tonight's edit.

## 2026-08-30

**Committed**

- `2521c72` Trim project name before dedup/storage; cap image extraction at
  MAX_IMAGES_PER_DOC

**Worth knowing**

- The project-name fix closes a real (if minor) bug: the New Project form
  stripped the name only for the "is it empty" check, so a name with
  incidental leading/trailing whitespace (e.g. pasted from another
  document) bypassed the duplicate-name check and created a second,
  visually-identical project that would never collide with future
  dup-checks either, since the raw value was also what got stored as the
  dict key.
- The image-extraction fix is a memory/latency cleanup, not a behavior
  change: `describe_images_with_vision()` already slices to the first
  `MAX_IMAGES_PER_DOC` (8) images before sending anything to Claude, but
  all three extractors (docx, PDF, pptx) were collecting *every* embedded
  image into memory first regardless of that cap. A document within the
  existing upload-size limits (20MB / 200MB decompressed) can legitimately
  contain far more than 8 images — a scanned packet, an image-heavy slide
  deck — so this was doing real, unbounded-ish work for output that was
  always going to be discarded. Output is unchanged: still the first 8
  images found, in the same order.
- Full pass tonight covered `synergyai_app.py` end to end (background
  review pass, then independently verified each finding — including exact
  line numbers and surrounding logic — before deciding what was safe) and
  `requirements.txt` against actual imports: no drift. `auth.py`, `db.py`,
  `AUTH_ENABLED`, and `check_access()` were not touched or read beyond
  confirming their locations, per standing instructions.
- Checked the actual GitHub Actions run history for the Nightly Evals
  workflow directly rather than trusting `evals/latest_report.md` (still
  dated 2026-08-18) or `evals/LEARNED.md` (still no entries): last night's
  scheduled run (#28, on `6722ed3`) also failed, same as every run since
  2026-08-19. No new information beyond what's already in the standing
  Open Items entry — status is unchanged, still needs Devarsh to check the
  secret/connectivity directly.
- Two smaller observations came up in review but weren't logged as open
  items — deliberately, since neither needs a decision, just noting them:
  `analyze_gaps()`'s free-typed "Additional Notes" field is appended to
  the AI prompt after `truncate(text)` is applied to the document text, so
  `MAX_CHARS` isn't a hard ceiling on that call's total prompt size
  (low-risk since notes are operator-typed, not adversarial, and
  realistically short); and large CSV/XLSX uploads are serialized to
  AI-facing text via `pandas.DataFrame.to_string()`, which re-renders with
  column alignment and can be noticeably larger/slower than the source
  file for a wide or many-row sheet within the current 20MB cap — a
  content-shaping decision, not something to change unilaterally.

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
