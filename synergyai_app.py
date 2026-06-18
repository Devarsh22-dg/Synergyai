import os
import io
import streamlit as st
import pandas as pd
import anthropic
import pypdf
from docx import Document

# --- Configuration & Setup ---
st.set_page_config(layout="wide", page_title="SynergyAI: Consulting Accelerator")

DEFAULT_MODEL = "claude-sonnet-4-6"
FAST_MODEL = "claude-haiku-4-5-20251001"

PROJECTS = ["Alpha-FinTech Migration", "Beta-Supply Chain Optimization", "Gamma-HR Platform Rollout"]
USERS = ["Alice (BA)", "Bob (PM)", "Charlie (PgM)"]

CHATBOT_SYSTEM_PROMPT = (
    "You are SynergyBot, an AI assistant embedded in a tool used by business analysts, "
    "project managers, and program managers. Answer questions about requirements engineering, "
    "BRD/FRD best practices, Agile story writing, stakeholder management, and JIRA/Azure DevOps "
    "workflows. Keep answers practical and concise (a few short paragraphs or a brief list). "
    "If a question doesn't relate to those domains, answer briefly and steer back to how the "
    "SynergyAI tool's modules (Elicitation Analysis, Documentation Generator, Story Creator, "
    "Meeting Actionizer) might help."
)

DOC_TYPE_CODES = {
    "BRD (Business Requirements Document)": "BRD",
    "FRD (Functional Requirements Document)": "FRD",
    "Data Dictionary": "Data_Dictionary",
    "Use Cases": "Use_Cases",
}

GAP_ANALYSIS_SCHEMA = {
    "type": "object",
    "properties": {
        "risk_score": {
            "type": "integer",
            "minimum": 0,
            "maximum": 100,
            "description": "Overall requirements risk score, 0 (low risk) to 100 (high risk).",
        },
        "risk_level": {
            "type": "string",
            "enum": ["Low", "Medium", "High", "Critical"],
        },
        "summary": {
            "type": "string",
            "description": "One or two sentence summary of the overall state of these requirements.",
        },
        "open_questions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "type": {
                        "type": "string",
                        "enum": [
                            "Ambiguity",
                            "Missing NFR",
                            "Conflict",
                            "Missing Stakeholder Input",
                            "Scope Risk",
                            "Other",
                        ],
                    },
                    "issue": {"type": "string", "description": "Specific description of the gap or ambiguity."},
                    "why_it_matters": {"type": "string", "description": "Why this needs to be resolved."},
                },
                "required": ["type", "issue", "why_it_matters"],
            },
        },
    },
    "required": ["risk_score", "risk_level", "open_questions"],
}

STORY_SCHEMA = {
    "type": "object",
    "properties": {
        "stories": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "requirement": {"type": "string", "description": "Short label for the source requirement/need."},
                    "user_story": {
                        "type": "string",
                        "description": "Format: As a <role>, I want <capability>, so that <benefit>.",
                    },
                    "acceptance_criteria": {
                        "type": "string",
                        "description": "Gherkin-style GIVEN/WHEN/THEN acceptance criteria.",
                    },
                },
                "required": ["requirement", "user_story", "acceptance_criteria"],
            },
        }
    },
    "required": ["stories"],
}

MEETING_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string", "description": "A short executive summary of the meeting."},
        "decisions": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Key decisions made during the meeting.",
        },
        "action_items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "action": {"type": "string"},
                    "owner": {"type": "string", "description": "Use 'Unassigned' if no owner is stated."},
                    "due_date": {"type": "string", "description": "Use 'Not specified' if no date is stated."},
                },
                "required": ["action", "owner", "due_date"],
            },
        },
    },
    "required": ["summary", "decisions", "action_items"],
}


# --- API Helpers ---

def get_api_key():
    key = None
    try:
        key = st.secrets.get("ANTHROPIC_API_KEY")
    except Exception:
        key = None
    if not key:
        key = os.environ.get("ANTHROPIC_API_KEY")
    return key


@st.cache_resource
def get_client():
    api_key = get_api_key()
    if not api_key:
        st.error(
            "🔑 **No Anthropic API key found.** Add `ANTHROPIC_API_KEY` to this app's "
            "Secrets (on Streamlit Community Cloud: **Settings → Secrets**), or set it as an "
            "environment variable if running locally."
        )
        st.stop()
    return anthropic.Anthropic(api_key=api_key)


def current_model():
    return st.session_state.get("model", DEFAULT_MODEL)


def call_text(system, user_prompt, max_tokens=1500, model=None):
    """Free-text generation call. Returns a string, or None on failure."""
    client = get_client()
    try:
        resp = client.messages.create(
            model=model or current_model(),
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user_prompt}],
        )
        return "".join(block.text for block in resp.content if block.type == "text")
    except Exception as e:
        st.error(f"AI request failed: {e}")
        return None


def call_chat(system, messages, max_tokens=800, model=None):
    """Multi-turn chat call. `messages` is a list of {'role', 'content'} dicts."""
    client = get_client()
    try:
        resp = client.messages.create(
            model=model or current_model(),
            max_tokens=max_tokens,
            system=system,
            messages=messages,
        )
        return "".join(block.text for block in resp.content if block.type == "text")
    except Exception as e:
        st.error(f"AI request failed: {e}")
        return None


def call_structured(system, user_prompt, tool_name, tool_description, schema, max_tokens=2000, model=None):
    """Forces Claude to return data matching `schema` via tool use. Returns a dict, or None on failure."""
    client = get_client()
    try:
        resp = client.messages.create(
            model=model or current_model(),
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user_prompt}],
            tools=[{
                "name": tool_name,
                "description": tool_description,
                "input_schema": schema,
            }],
            tool_choice={"type": "tool", "name": tool_name},
        )
        for block in resp.content:
            if block.type == "tool_use" and block.name == tool_name:
                return block.input
        st.error("The AI response didn't include the expected structured data. Try again.")
        return None
    except Exception as e:
        st.error(f"AI request failed: {e}")
        return None


# --- File Parsing ---

MAX_CHARS = 15000  # keeps prompt sizes/costs reasonable


def extract_text_from_upload(uploaded_file):
    """Extracts plain text from txt/pdf/docx/xlsx/csv uploads. Returns '' on failure."""
    name = uploaded_file.name
    ext = name.split(".")[-1].lower()
    uploaded_file.seek(0)
    try:
        if ext == "txt":
            return uploaded_file.read().decode("utf-8", errors="ignore")

        elif ext == "pdf":
            reader = pypdf.PdfReader(uploaded_file)
            pages = [page.extract_text() or "" for page in reader.pages]
            text = "\n".join(pages)
            if not text.strip():
                st.warning("No extractable text found in this PDF — it may be a scanned/image-only document.")
            return text

        elif ext == "docx":
            doc = Document(uploaded_file)
            return "\n".join(p.text for p in doc.paragraphs)

        elif ext == "csv":
            df = pd.read_csv(uploaded_file)
            return df.to_string(index=False)

        elif ext == "xlsx":
            xls = pd.ExcelFile(uploaded_file)
            parts = []
            for sheet in xls.sheet_names:
                df = xls.parse(sheet)
                parts.append(f"--- Sheet: {sheet} ---\n{df.to_string(index=False)}")
            return "\n\n".join(parts)

        else:
            st.error(f"Unsupported file type: .{ext}")
            return ""

    except Exception as e:
        st.error(f"Couldn't read this file: {e}")
        return ""


def truncate(text, limit=MAX_CHARS):
    if len(text) > limit:
        return text[:limit], True
    return text, False


# --- AI Task Functions ---

def analyze_gaps(text):
    truncated_text, was_truncated = truncate(text)
    if was_truncated:
        st.caption(f"⚠️ Document was long — analyzing the first {MAX_CHARS:,} characters.")
    system = (
        "You are a senior business analyst performing a requirements quality review. "
        "Carefully read the provided notes/transcript and identify ambiguities, missing "
        "non-functional requirements (performance, security, availability, etc.), stakeholder "
        "conflicts, and scope risks. Be specific and ground every finding in something actually "
        "present (or notably absent) in the text — do not invent details. If the text is sparse, "
        "it's fine to return fewer findings and a lower risk score."
    )
    user_prompt = f"Analyze the following content:\n\n{truncated_text}"
    return call_structured(
        system, user_prompt,
        "submit_gap_analysis",
        "Submit the structured requirements gap analysis.",
        GAP_ANALYSIS_SCHEMA,
    )


def generate_document(doc_type, context_text, user_suggestion):
    system = (
        "You are a senior business analyst drafting professional project documentation. "
        "Write a well-structured, realistic first draft in Markdown. Use clear section headers. "
        "Where the source content doesn't cover something, write '[Needs stakeholder input]' "
        "rather than inventing specifics."
    )
    user_prompt = (
        f"Document type to draft: {doc_type}\n\n"
        f"Special instructions / focus areas from the analyst:\n{user_suggestion}\n\n"
        f"Source content / requirements notes to base this on:\n{context_text if context_text.strip() else '(No source content provided — draft a generic template with clear placeholder sections.)'}"
    )
    return call_text(system, user_prompt, max_tokens=2500)


def generate_stories(source_text):
    system = (
        "You are a senior business analyst converting requirements into an Agile backlog. "
        "For each distinct requirement or need in the source text, write one user story in the "
        "format 'As a <role>, I want <capability>, so that <benefit>', plus Gherkin-style "
        "acceptance criteria (GIVEN/WHEN/THEN). Only create stories that are actually supported "
        "by the source text."
    )
    user_prompt = f"Source requirements/notes:\n\n{source_text}"
    result = call_structured(
        system, user_prompt,
        "submit_stories",
        "Submit the generated user stories and acceptance criteria.",
        STORY_SCHEMA,
        max_tokens=2500,
    )
    return result.get("stories", []) if result else []


def process_meeting(transcript_text):
    truncated_text, was_truncated = truncate(transcript_text)
    if was_truncated:
        st.caption(f"⚠️ Transcript was long — analyzing the first {MAX_CHARS:,} characters.")
    system = (
        "You are an assistant that turns raw meeting transcripts into structured minutes. "
        "Extract a concise executive summary, key decisions, and action items with an owner "
        "and due date if stated. Use 'Unassigned' / 'Not specified' rather than guessing."
    )
    user_prompt = f"Meeting transcript:\n\n{truncated_text}"
    return call_structured(
        system, user_prompt,
        "submit_meeting_minutes",
        "Submit the structured meeting minutes.",
        MEETING_SCHEMA,
    )


def chat_with_bot(history):
    return call_chat(CHATBOT_SYSTEM_PROMPT, history, max_tokens=800)


# --- Role-Specific Functions ---

def ba_module():
    st.header("💼 Strategic Requirements Hub")
    st.caption("AI-Augmented tools for Elicitation, Documentation, and Agile Workflow.")

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "🔍 Elicitation Analysis & Gap Detector",
        "📝 Automated Documentation Generator",
        "🎯 Agile Story & Backlog Creator",
        "💬 Meeting Intelligence & Actionizer",
        "⚙️ BA Dashboard"
    ])

    # --- Tab 1: Elicitation Analysis ---
    with tab1:
        st.subheader("1. Elicitation Analysis & Gap Detector")
        st.markdown("Upload raw notes or transcripts. AI will structure needs and identify open questions.")

        uploaded_file = st.file_uploader(
            "Upload Notes/Transcript or Document:",
            type=['txt', 'pdf', 'docx', 'xlsx', 'csv'],
            key="gap_uploader",
        )
        st.info("⚠️ **Note on File Intake:** For proprietary formats (e.g., Apple Pages/Numbers, Visio, or live Google Docs/Sheets), please export the content to a universal format like `.docx`, `.pdf`, or `.txt` before uploading.")

        if st.button("Analyze for Gaps", key="analyze_gaps_btn"):
            if uploaded_file is not None:
                with st.spinner("Extracting text from document..."):
                    text = extract_text_from_upload(uploaded_file)
                if not text.strip():
                    st.error("Couldn't extract any readable text from this file. Try a different format.")
                else:
                    st.session_state["extracted_text"] = text
                    with st.spinner("Cross-referencing against requirements quality standards..."):
                        result = analyze_gaps(text)
                    if result:
                        st.session_state["gap_analysis"] = result
            else:
                st.warning("Please upload a file to analyze.")

        result = st.session_state.get("gap_analysis")
        if result:
            n_open = len(result.get("open_questions", []))
            st.success(f"Analysis complete. Found {n_open} open item(s) for stakeholder follow-up.")
            if result.get("summary"):
                st.caption(result["summary"])
            st.metric(
                label="Requirements Risk Score",
                value=f"{result.get('risk_score', 0)}/100 ({result.get('risk_level', 'Unknown')})",
            )

            st.markdown("### ❓ Open Questions for Stakeholders")
            if n_open == 0:
                st.info("No significant gaps detected in this content.")
            for q in result.get("open_questions", []):
                st.warning(f"**{q.get('type', 'Issue')}:** {q.get('issue', '')}\n\n*Why it matters:* {q.get('why_it_matters', '')}")

    # --- Tab 2: Documentation Generator ---
    with tab2:
        st.subheader("2. Automated Documentation Generator")
        st.markdown("Generate a real first-draft document (BRD, FRD, Use Cases, Data Dictionary) from your requirements notes.")

        doc_type = st.selectbox(
            "Select Document Type to Draft",
            list(DOC_TYPE_CODES.keys()),
            key="doc_type_select",
        )

        prefill = st.session_state.get("extracted_text", "")
        context_text = st.text_area(
            "Source content (auto-filled from the Elicitation tab if available — edit freely):",
            value=prefill[:3000],
            height=150,
            key="doc_context",
        )

        user_suggestion = st.text_area(
            "Provide specific instructions or focus areas:",
            "e.g., Ensure the regulatory compliance section is highly detailed.",
            key="doc_suggestion",
        )

        if st.button(f"Generate Draft {doc_type}", key="generate_doc_btn"):
            with st.spinner(f"Drafting {doc_type}..."):
                draft = generate_document(doc_type, context_text, user_suggestion)
            if draft:
                st.session_state["documents_drafted"] = st.session_state.get("documents_drafted", 0) + 1
                st.session_state["last_doc_draft"] = draft
                st.session_state["last_doc_type"] = doc_type

        draft = st.session_state.get("last_doc_draft")
        if draft:
            st.success(f"Draft of {st.session_state.get('last_doc_type', doc_type)} generated.")
            st.markdown(draft)
            st.download_button(
                "⬇️ Download Draft (.md)",
                draft,
                file_name=f"{DOC_TYPE_CODES.get(doc_type, 'Document')}_draft.md",
                mime="text/markdown",
            )

    # --- Tab 3: Agile Story Creator ---
    with tab3:
        st.subheader("3. Agile Story & Backlog Creator")
        st.markdown("Convert validated requirements into ready-to-import User Stories and Gherkin Acceptance Criteria.")

        source_text = st.text_area(
            "Requirements / notes to convert into stories (auto-filled from Elicitation tab if available):",
            value=st.session_state.get("extracted_text", "")[:3000],
            height=150,
            key="story_source",
        )

        if st.button("Generate User Stories & Acceptance Criteria", key="generate_stories_btn"):
            if not source_text.strip():
                st.warning("Add some requirements text first.")
            else:
                with st.spinner("Drafting user stories and acceptance criteria..."):
                    stories = generate_stories(source_text)
                if stories:
                    st.session_state["stories"] = stories
                    st.session_state["stories_drafted"] = st.session_state.get("stories_drafted", 0) + len(stories)

        stories = st.session_state.get("stories", [])
        if stories:
            st.markdown("### User Story Drafts")
            story_df = pd.DataFrame(stories)
            edited_df = st.data_editor(story_df, use_container_width=True, num_rows="dynamic", key="story_editor")

            csv_data = edited_df.to_csv(index=False)
            st.download_button(
                "⬇️ Download Backlog (.csv — Jira/Azure DevOps import format)",
                csv_data,
                file_name="backlog_stories.csv",
                mime="text/csv",
            )
        else:
            st.info("Generate stories to see them here.")

    # --- Tab 4: Meeting Intelligence ---
    with tab4:
        st.subheader("4. Meeting Intelligence & Actionizer")
        st.markdown("Transform raw meeting transcripts into structured minutes, decisions, and action items.")

        uploaded_transcript = st.file_uploader(
            "Upload Meeting Transcript (.txt or .docx):",
            type=['txt', 'docx'],
            key="transcript_uploader",
        )

        if st.button("Process Transcript", key="process_transcript_btn"):
            if uploaded_transcript is not None:
                with st.spinner("Extracting text..."):
                    text = extract_text_from_upload(uploaded_transcript)
                if not text.strip():
                    st.error("Couldn't extract any readable text from this transcript.")
                else:
                    with st.spinner("Extracting decisions, owners, and actions..."):
                        result = process_meeting(text)
                    if result:
                        st.session_state["meeting_result"] = result
            else:
                st.warning("Please upload a transcript to process.")

        result = st.session_state.get("meeting_result")
        if result:
            st.success("Meeting summary generated.")
            st.markdown("### 📄 Executive Summary")
            st.info(result.get("summary", ""))

            decisions = result.get("decisions", [])
            if decisions:
                st.markdown("### 🧭 Key Decisions")
                for d in decisions:
                    st.write(f"- {d}")

            st.markdown("### ✅ Action Items Extracted")
            items = result.get("action_items", [])
            if items:
                action_df = pd.DataFrame(items)
                st.dataframe(action_df, use_container_width=True)
                st.download_button(
                    "⬇️ Download Action Items (.csv)",
                    action_df.to_csv(index=False),
                    file_name="meeting_action_items.csv",
                    mime="text/csv",
                )
            else:
                st.caption("No explicit action items were detected in this transcript.")

    # --- Tab 5: BA Dashboard ---
    with tab5:
        st.subheader("5. BA Dashboard")
        st.markdown("Summary view of activity in this session.")

        col1, col2, col3 = st.columns(3)
        col1.metric("User Stories Drafted (this session)", st.session_state.get("stories_drafted", 0))
        col2.metric("Documents Drafted (this session)", st.session_state.get("documents_drafted", 0))

        gap_result = st.session_state.get("gap_analysis")
        open_gaps = len(gap_result.get("open_questions", [])) if gap_result else 0
        col3.metric("Open Gaps (latest analysis)", open_gaps)

        st.caption(
            "These metrics reflect activity in your current browser session only. Tracking activity "
            "across sessions/users would require a persistent database backend."
        )


def pm_module():
    st.header("🗓️ Project Managers: Predictive Risk & Health (Placeholder)")
    st.markdown("View predictive metrics, resource optimization, and automated status reports.")
    st.selectbox("Select Project to View", PROJECTS)
    st.info("PM features (Project Health Forecaster, Constraint Solver) haven't been built yet — this module is still a placeholder.")


def pgm_module():
    st.header("🗺️ Program Managers: Portfolio Optimization (Placeholder)")
    st.markdown("Analyze cross-project dependencies, resource contention, and benefit realization.")
    st.warning("PgM features (Interdependency Mapper, Benefit Realization Tracker) haven't been built yet — this module is still a placeholder.")


# --- Main App Navigation ---

st.sidebar.title("SynergyAI Modules")
role = st.sidebar.radio("Select Your Role", ["Business Analyst (BA)", "Project Manager (PM)", "Program Manager (PgM)"])

st.sidebar.markdown("---")
st.sidebar.selectbox(
    "AI Model",
    [DEFAULT_MODEL, FAST_MODEL],
    index=0,
    key="model",
    help="Sonnet = best quality for analysis/drafting. Haiku = faster and cheaper, good for quick checks.",
)
if not get_api_key():
    st.sidebar.error("No ANTHROPIC_API_KEY found in Secrets.")
else:
    st.sidebar.success("API key loaded.")

st.sidebar.markdown("---")

# --- Display Selected Module ---
if role == "Business Analyst (BA)":
    ba_module()
elif role == "Project Manager (PM)":
    pm_module()
elif role == "Program Manager (PgM)":
    pgm_module()

st.divider()
st.subheader("🤖 SynergyBot (AI Assistant)")

if "chat_history" not in st.session_state:
    st.session_state["chat_history"] = []

for msg in st.session_state["chat_history"]:
    st.chat_message(msg["role"]).write(msg["content"])

user_query = st.chat_input("Ask SynergyBot a question about requirements, JIRA sync, or best practices...")

if user_query:
    st.session_state["chat_history"].append({"role": "user", "content": user_query})
    st.chat_message("user").write(user_query)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            reply = chat_with_bot(st.session_state["chat_history"])
        if reply:
            st.write(reply)
        else:
            reply = "Sorry, I couldn't process that — please try again."
            st.write(reply)

    st.session_state["chat_history"].append({"role": "assistant", "content": reply})
