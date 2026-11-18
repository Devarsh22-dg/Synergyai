"""ScopeBot's ability to act: plan a queue of generation jobs, run them in
order, and ask the user when the request is ambiguous.

Before this, ScopeBot was a plain text call with no tools — asked to run a gap
analysis it would explain how to click the tab rather than doing it.

Design notes:

* This module deliberately knows nothing about Streamlit and imports nothing
  from synergyai_app. The app passes in a `deps` dict of its own generator
  functions, so the planner and executor can be unit-tested with fakes and no
  API key. Keeping it a separate module also keeps a large new surface out of
  synergyai_app.py, and out of the files the nightly routine may not touch.

* Jobs are executed in the order the model planned them, and a job may consume
  the previous job's output via `input_source="previous_step"`. That is what
  makes "update the BRD, then write stories for the updated BRD" work as one
  request rather than two disconnected ones.

* Results are written into the same `proj[...]` keys the tabs already read, so
  a queued job shows up in its normal tab with no separate display surface.
"""

# Keys here must match DOC_TYPE_CODES in synergyai_app.py.
DOC_TYPES = [
    "BRD (Business Requirements Document)",
    "FRD (Functional Requirements Document)",
    "Data Dictionary",
    "Use Cases",
    "As-Is / To-Be Process Document",
]

JOB_ACTIONS = [
    "analyze_gaps",
    "generate_document",
    "generate_stories",
    "generate_test_cases",
    "generate_glossary",
    "generate_prioritization",
]

EDITABLE_FIELDS = ["description", "client", "status"]
PROJECT_STATUSES = ["Planning", "In Progress", "On Hold", "Complete"]

AGENT_TOOLS = [
    {
        "name": "queue_jobs",
        "description": (
            "Queue one or more generation jobs to run in order. Use this when the user asks "
            "for work to be DONE (generate, draft, update, analyze, create), rather than asking "
            "a question about how something works. Multi-step requests become multiple jobs in "
            "the order they should run — e.g. 'update the BRD from the new requirements then "
            "write stories for it' is a generate_document job followed by a generate_stories "
            "job whose input_source is previous_step. Only queue jobs you are confident the "
            "user actually asked for; if the request is ambiguous, call ask_clarifying_question "
            "instead."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "jobs": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "action": {
                                "type": "string",
                                "enum": JOB_ACTIONS,
                                "description": "Which generator to run.",
                            },
                            "doc_type": {
                                "type": "string",
                                "enum": DOC_TYPES,
                                "description": "Required only when action is generate_document.",
                            },
                            "instructions": {
                                "type": "string",
                                "description": (
                                    "Focus areas or specific instructions for this job, in the "
                                    "user's own terms. Pass an empty string if they gave none."
                                ),
                            },
                            "input_source": {
                                "type": "string",
                                "enum": ["repository", "previous_step"],
                                "description": (
                                    "Where this job's source content comes from. 'repository' "
                                    "uses the project's uploaded documents and last analysis. "
                                    "'previous_step' uses the output of the job before it — use "
                                    "this when the user's wording ties one step to another "
                                    "('...and then stories for THAT'). The first job in a queue "
                                    "must always be 'repository'."
                                ),
                            },
                        },
                        "required": ["action", "instructions", "input_source"],
                    },
                },
                "summary": {
                    "type": "string",
                    "description": "One sentence telling the user what is about to run, in plain language.",
                },
            },
            "required": ["jobs", "summary"],
        },
    },
    {
        "name": "ask_clarifying_question",
        "description": (
            "Ask the user a question instead of guessing. Use this when the request could "
            "reasonably mean more than one thing — an unnamed document type, an unclear source, "
            "or an instruction that could apply to several modules. Asking is strongly preferred "
            "over queueing the wrong job, because generation overwrites the previous result."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "question": {"type": "string", "description": "The question, in one sentence."},
                "why": {
                    "type": "string",
                    "description": "Briefly, what you'd do differently depending on the answer.",
                },
            },
            "required": ["question", "why"],
        },
    },
    {
        "name": "update_project_field",
        "description": (
            "Update one of the project's own fields. Use when the user asks to set, change or "
            "write the project description, client, or status."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "field": {"type": "string", "enum": EDITABLE_FIELDS},
                "value": {"type": "string", "description": "The new value. For status, one of the allowed statuses."},
            },
            "required": ["field", "value"],
        },
    },
]

AGENT_SYSTEM_PROMPT = (
    "You are ScopeBot, embedded in ScopeForge, a tool business analysts use for requirements "
    "work. You can both answer questions AND do the work directly using your tools.\n\n"
    "Choosing what to do:\n"
    "- The user asks you to produce or change something ('draft a BRD', 'update the BRD and "
    "write stories for it', 'find the gaps') -> queue_jobs.\n"
    "- The user asks to set the project description, client or status -> update_project_field.\n"
    "- The request is genuinely ambiguous -> ask_clarifying_question. Prefer asking over "
    "guessing: every generator overwrites the previous result for that module, so a wrong guess "
    "destroys work.\n"
    "- The user asks a general question about BA practice, or about how ScopeForge works -> "
    "just answer in text, no tool. Keep it to a few short paragraphs or a brief list.\n\n"
    "Do not claim you have done something unless you actually queued it with a tool. Never "
    "describe the clicks a user could perform themselves as if that were the work being done."
)


def validate_jobs(jobs):
    """Returns a list of human-readable problems with a planned queue; empty if valid.

    The model picks these values, so they are checked before anything runs rather
    than trusted — a bad plan should surface as a message, not a traceback partway
    through a queue that has already overwritten one module's results.
    """
    problems = []
    if not jobs:
        return ["The plan contained no jobs."]
    for i, job in enumerate(jobs, start=1):
        action = job.get("action")
        if action not in JOB_ACTIONS:
            problems.append(f"Step {i}: unknown action '{action}'.")
            continue
        if action == "generate_document":
            if job.get("doc_type") not in DOC_TYPES:
                problems.append(
                    f"Step {i}: generate_document needs a doc_type from the supported list, got "
                    f"'{job.get('doc_type')}'."
                )
        if job.get("input_source") not in ("repository", "previous_step"):
            problems.append(f"Step {i}: input_source must be 'repository' or 'previous_step'.")
        if i == 1 and job.get("input_source") == "previous_step":
            problems.append("Step 1 cannot use 'previous_step' — there is no previous step.")
    return problems


def describe_job(job):
    """One-line human description of a planned job, for the confirmation list."""
    action = job.get("action")
    if action == "generate_document":
        label = f"Draft {job.get('doc_type', 'document')}"
    else:
        label = {
            "analyze_gaps": "Analyze requirements for gaps",
            "generate_stories": "Generate user stories",
            "generate_test_cases": "Generate test cases from the stories",
            "generate_glossary": "Build the business glossary",
            "generate_prioritization": "Prioritize requirements (MoSCoW)",
        }.get(action, action)
    if job.get("input_source") == "previous_step":
        label += " (using the previous step's output)"
    instructions = (job.get("instructions") or "").strip()
    if instructions:
        label += f" — {instructions}"
    return label


def run_jobs(jobs, proj, deps, repository_text, on_progress=None):
    """Executes a validated queue in order, writing results into `proj`.

    `deps` maps generator names to callables, so this is testable with fakes and
    the app stays the only thing that knows how to build them. `repository_text`
    is the project's source content, already assembled by the caller.

    Returns (results, errors): results is a list of per-step human-readable
    outcomes, errors a list of step failures. Execution stops at the first
    failure rather than running later steps against missing input — a step that
    depends on previous_step would otherwise silently generate from nothing.
    """
    results = []
    errors = []
    previous_output = None

    for i, job in enumerate(jobs, start=1):
        action = job["action"]
        instructions = (job.get("instructions") or "").strip()
        if on_progress:
            on_progress(i, len(jobs), describe_job(job))

        if job.get("input_source") == "previous_step" and previous_output:
            source_text = previous_output
        else:
            source_text = repository_text

        try:
            if action == "analyze_gaps":
                out = deps["analyze_gaps"](source_text, instructions or None)
                if out:
                    proj["gap_analysis"] = out
                    proj["extracted_text"] = source_text
                    n = len(out.get("open_questions", []))
                    results.append(f"Gap analysis: {n} possible gap(s) found.")
                    previous_output = source_text
                else:
                    errors.append(f"Step {i} (gap analysis) returned nothing.")
                    break

            elif action == "generate_document":
                doc_type = job["doc_type"]
                if doc_type == "Data Dictionary":
                    rows = deps["generate_data_dictionary"](source_text, instructions)
                    kind = "data_dictionary"
                elif doc_type == "As-Is / To-Be Process Document":
                    rows = deps["generate_asis_tobe"](source_text, instructions)
                    kind = "asis_tobe"
                else:
                    text = deps["generate_document"](doc_type, source_text, instructions)
                    rows = None
                    kind = "markdown"

                if kind == "markdown":
                    if not text:
                        errors.append(f"Step {i} ({doc_type}) returned nothing.")
                        break
                    proj["last_doc_draft"] = {"kind": "markdown", "text": text}
                    previous_output = text
                else:
                    if not rows:
                        errors.append(f"Step {i} ({doc_type}) returned nothing.")
                        break
                    proj["last_doc_draft"] = {"kind": kind, "rows": rows}
                    # A table-shaped document still needs a text form for any
                    # following step that consumes it.
                    previous_output = "\n".join(str(r) for r in rows)
                proj["last_doc_type"] = doc_type
                proj["documents_drafted"] = proj.get("documents_drafted", 0) + 1
                results.append(f"{doc_type} drafted.")

            elif action == "generate_stories":
                stories = deps["generate_stories"](source_text)
                if stories:
                    proj["stories"] = stories
                    proj["stories_drafted"] = proj.get("stories_drafted", 0) + len(stories)
                    results.append(f"{len(stories)} user story/stories generated.")
                    previous_output = "\n\n".join(
                        f"{s.get('requirement','')}: {s.get('user_story','')}\n{s.get('acceptance_criteria','')}"
                        for s in stories
                    )
                else:
                    errors.append(f"Step {i} (user stories) returned nothing.")
                    break

            elif action == "generate_test_cases":
                # Test cases derive from the stories already in the project, not
                # from raw source text, so a queue of "stories then test cases"
                # chains through project state rather than previous_output.
                stories = proj.get("stories", [])
                if not stories:
                    errors.append(f"Step {i} (test cases) needs user stories, and none exist yet.")
                    break
                cases = deps["generate_test_cases"](stories)
                if cases:
                    proj["test_cases"] = cases
                    proj["test_cases_drafted"] = proj.get("test_cases_drafted", 0) + len(cases)
                    results.append(f"{len(cases)} test case(s) generated.")
                else:
                    errors.append(f"Step {i} (test cases) returned nothing.")
                    break

            elif action == "generate_glossary":
                terms = deps["generate_glossary"](source_text)
                if terms:
                    proj["glossary"] = terms
                    proj["glossary_terms_found"] = len(terms)
                    results.append(f"{len(terms)} glossary term(s) extracted.")
                else:
                    errors.append(f"Step {i} (glossary) returned nothing.")
                    break

            elif action == "generate_prioritization":
                items = deps["generate_prioritization"](source_text)
                if items:
                    proj["prioritization"] = items
                    results.append(f"{len(items)} requirement(s) prioritized.")
                else:
                    errors.append(f"Step {i} (prioritization) returned nothing.")
                    break

        except Exception as e:  # noqa: BLE001 - surfaced to the user, not swallowed
            errors.append(f"Step {i} ({action}) failed: {e}")
            break

    return results, errors
