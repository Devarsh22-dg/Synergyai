import os
import io
import re
import requests
from bs4 import BeautifulSoup
import streamlit as st
import pandas as pd
import anthropic
import pypdf
from docx import Document
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from datetime import datetime

# --- Configuration & Setup ---
st.set_page_config(layout="wide", page_title="ScopeForge: Consulting Accelerator")

DEFAULT_MODEL = "claude-sonnet-4-6"
FAST_MODEL = "claude-haiku-4-5-20251001"

STARTER_PROJECTS = ["Alpha-FinTech Migration", "Beta-Supply Chain Optimization", "Gamma-HR Platform Rollout"]
PROJECT_STATUSES = ["Planning", "In Progress", "On Hold", "Complete"]

DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

# --- Access Control (placeholder — intentionally a no-op) ---
# Per Devarsh's instruction: keep the app fully open until going live. This flag and
# function are the hook point for that future work — once email-based login specs are
# provided, implement the real check inside check_access() and flip AUTH_ENABLED to True.
# Until then this always returns True and changes no behavior.
AUTH_ENABLED = False


def check_access():
    """Gate for future email-based login. Currently always allows access."""
    if not AUTH_ENABLED:
        return True
    # TODO: implement real email-based login here once specs are provided.
    return True

CHATBOT_SYSTEM_PROMPT = (
    "You are ScopeBot, an AI assistant embedded in a tool used by business analysts, "
    "project managers, and program managers. Answer questions about requirements engineering, "
    "BRD/FRD best practices, Agile story writing, stakeholder management, and JIRA/Azure DevOps "
    "workflows. Keep answers practical and concise (a few short paragraphs or a brief list). "
    "If a question doesn't relate to those domains, answer briefly and steer back to how "
    "ScopeForge's modules (Elicitation Analysis, Documentation Generator, Story Creator, "
    "Meeting Actionizer) might help."
)

DOC_TYPE_CODES = {
    "BRD (Business Requirements Document)": "BRD",
    "FRD (Functional Requirements Document)": "FRD",
    "Data Dictionary": "Data_Dictionary",
    "Use Cases": "Use_Cases",
    "As-Is / To-Be Process Document": "AsIs_ToBe",
}
TABULAR_DOC_TYPES = {"Data Dictionary", "As-Is / To-Be Process Document"}

# --- Visual Theme ---
# "Forge" palette: dark steel base, ember-orange accent, distinct hues per section.
SECTION_COLORS = {
    "project": "#2E86AB",      # steel blue
    "meeting": "#8E5DB3",      # violet
    "elicitation": "#D9622B",  # ember orange
    "docgen": "#2F9E5B",       # forge green
    "story": "#4D6BAF",        # indigo blue
    "dashboard": "#C1485C",    # rose
    "pm": "#5C7A99",           # muted slate blue
    "pgm": "#8C6A4A",          # muted bronze
    "chat": "#33384A",         # neutral dark
}
SIDEBAR_BG = "#1F2333"
SIDEBAR_TEXT = "#EDEFF5"
SIDEBAR_MUTED = "#B8BCC8"
ACCENT = "#FF8C42"


def inject_theme():
    st.markdown(
        f"""
        <style>
        /* Collapse Streamlit's default top whitespace and color the header strip so
           the top of the page reads as designed rather than empty. */
        [data-testid="stHeader"] {{
            background-color: {SIDEBAR_BG};
            color: {SIDEBAR_TEXT};
        }}
        [data-testid="stAppViewContainer"] .main .block-container {{
            padding-top: 1.2rem !important;
        }}
        [data-testid="stSidebar"] {{
            background-color: {SIDEBAR_BG};
        }}
        [data-testid="stSidebar"] label,
        [data-testid="stSidebar"] p,
        [data-testid="stSidebar"] span,
        [data-testid="stSidebar"] div {{
            color: {SIDEBAR_TEXT} !important;
        }}
        [data-testid="stSidebar"] .stSelectbox div[data-baseweb="select"] > div,
        [data-testid="stSidebar"] .stRadio div[role="radiogroup"] {{
            background-color: #2A2F45;
        }}
        [data-testid="stSidebar"] hr {{
            border-color: #3A3F58;
        }}
        [data-testid="stTabs"] button[role="tab"] {{
            background-color: #F1F2F6;
            color: #4B4F58;
            border-radius: 8px 8px 0 0;
            padding: 0.55rem 1.1rem;
            font-weight: 600;
            margin-right: 4px;
        }}
        [data-testid="stTabs"] button[role="tab"] p {{
            color: inherit !important;
            font-weight: 600;
        }}
        [data-testid="stTabs"] button[aria-selected="true"] {{
            background-color: {SIDEBAR_BG};
            border-bottom: 3px solid {ACCENT};
        }}
        [data-testid="stTabs"] button[aria-selected="true"] p {{
            color: {ACCENT} !important;
        }}
        div[role="radiogroup"] {{
            gap: 0.4rem;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_masthead():
    """A branded top banner so the space at the top of the page reads as a
    deliberate header instead of dead whitespace."""
    st.markdown(
        f"""
        <div style="background-color: {SIDEBAR_BG}; padding: 0.9rem 1.5rem; border-radius: 10px;
                    margin-bottom: 1.3rem; display: flex; align-items: baseline; gap: 0.7rem;">
            <span style="font-size: 1.6rem; font-weight: 800; color: {ACCENT}; letter-spacing: 0.5px;">ScopeForge</span>
            <span style="font-size: 0.9rem; color: {SIDEBAR_MUTED};">Consulting Accelerator for Business Analysts</span>
        </div>
        """,
        unsafe_allow_html=True,
    )




def section_header(title, subtitle, color):
    st.markdown(
        f"""
        <div style="border-left: 6px solid {color}; padding: 0.35rem 0 0.35rem 0.9rem; margin-bottom: 0.8rem;">
            <div style="font-size: 1.3rem; font-weight: 700; color: {color}; line-height: 1.2;">{title}</div>
            <div style="font-size: 0.9rem; color: #5A5A5A; margin-top: 2px;">{subtitle}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


GAP_ANALYSIS_SCHEMA = {
    "type": "object",
    "properties": {
        "risk_score": {
            "type": "integer",
            "minimum": 0,
            "maximum": 100,
            "description": "Overall requirements risk score, 0 (low risk) to 100 (high risk).",
        },
        "risk_level": {"type": "string", "enum": ["Low", "Medium", "High", "Critical"]},
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
                            "Ambiguity", "Missing NFR", "Conflict",
                            "Missing Stakeholder Input", "Scope Risk", "Other",
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
        "decisions": {"type": "array", "items": {"type": "string"}, "description": "Key decisions made."},
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

DATA_DICT_SCHEMA = {
    "type": "object",
    "properties": {
        "fields": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "field_name": {"type": "string"},
                    "data_type": {"type": "string"},
                    "description": {"type": "string"},
                    "source_system": {"type": "string", "description": "Use 'Not specified' if unknown."},
                    "validation_rules": {"type": "string", "description": "Use 'None specified' if unknown."},
                },
                "required": ["field_name", "data_type", "description", "source_system", "validation_rules"],
            },
        }
    },
    "required": ["fields"],
}

ASIS_TOBE_SCHEMA = {
    "type": "object",
    "properties": {
        "steps": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "step_id": {"type": "string", "description": "Sequential plain-number ID with no leading zeros, e.g. '1', '2', '3' (not '010')."},
                    "process_step": {"type": "string", "description": "Short name of this process step."},
                    "as_is_description": {"type": "string"},
                    "to_be_description": {"type": "string"},
                    "gap_or_change": {"type": "string", "description": "What needs to change to get from As-Is to To-Be."},
                    "shape_type": {"type": "string", "enum": ["Start", "Process", "Decision", "End"]},
                    "next_step_id": {
                        "type": "string",
                        "description": "Comma-separated step_id(s) this flows into next, no spaces, no leading zeros (e.g. '2' or '2,3'). Blank for the End step.",
                    },
                },
                "required": ["step_id", "process_step", "as_is_description", "to_be_description", "gap_or_change", "shape_type", "next_step_id"],
            },
        }
    },
    "required": ["steps"],
}


# --- Project State Management ---

def default_project():
    return {
        "description": "",
        "client": "",
        "status": "Planning",
        "documents": [],          # list of {"name","text","ext","added_at","char_count"}
        "extracted_text": "",     # last combined text analyzed in Elicitation tab
        "last_notes": "",         # last notes used in Elicitation tab
        "gap_analysis": None,
        "stories": [],
        "stories_drafted": 0,
        "documents_drafted": 0,
        "last_doc_draft": None,   # {"kind": "markdown"|"data_dictionary"|"asis_tobe", ...}
        "last_doc_type": None,
        "meeting_result": None,
    }


def init_projects():
    if "projects" not in st.session_state:
        st.session_state["projects"] = {name: default_project() for name in STARTER_PROJECTS}
    if "current_project" not in st.session_state:
        st.session_state["current_project"] = STARTER_PROJECTS[0]


def get_current_project_name():
    return st.session_state.get("current_project")


def get_project():
    name = get_current_project_name()
    if name not in st.session_state["projects"]:
        st.session_state["projects"][name] = default_project()
    return st.session_state["projects"][name]


def add_doc_to_repo(proj, name, text, ext):
    existing_names = {d["name"] for d in proj["documents"]}
    if name in existing_names:
        proj["documents"] = [d for d in proj["documents"] if d["name"] != name]
    proj["documents"].append({
        "name": name,
        "text": text,
        "ext": ext,
        "added_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "char_count": len(text),
    })


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
            "No Anthropic API key found. Add `ANTHROPIC_API_KEY` to this app's "
            "Secrets (on Streamlit Community Cloud: Settings → Secrets), or set it as an "
            "environment variable if running locally."
        )
        st.stop()
    return anthropic.Anthropic(api_key=api_key)


def current_model():
    return st.session_state.get("model", DEFAULT_MODEL)


def call_text(system, user_prompt, max_tokens=1500, model=None):
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
    client = get_client()
    try:
        resp = client.messages.create(
            model=model or current_model(),
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user_prompt}],
            tools=[{"name": tool_name, "description": tool_description, "input_schema": schema}],
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


# --- File Parsing (reading uploads) ---

MAX_CHARS = 15000


def extract_docx_with_formatting(uploaded_file):
    """Reads a .docx with formatting awareness instead of flattening to plain text.
    Bold runs are wrapped **like this**, struck-through runs ~~like this~~, and italic
    runs *like this* — markdown conventions the AI already understands, so emphasis and
    deprecated/removed content carry through as real signal. Inline comments (Word's
    actual comment feature, not Track Changes) are appended as a labeled section.

    Known limitation: Word's Track Changes redline deletions/insertions (the dotted
    underline / strikethrough you see when "Show Markup" is on) are a different XML
    mechanism that python-docx doesn't expose at a usable level — only explicit
    strikethrough *formatting* applied to a run is captured here, not tracked changes.
    """
    doc = Document(uploaded_file)
    lines = []
    for para in doc.paragraphs:
        if not para.runs:
            if para.text.strip():
                lines.append(para.text)
            continue
        rendered = []
        for run in para.runs:
            t = run.text
            if not t:
                continue
            if run.font.strike:
                t = f"~~{t}~~"
            if run.bold:
                t = f"**{t}**"
            if run.italic:
                t = f"*{t}*"
            rendered.append(t)
        line = "".join(rendered)
        if line.strip():
            lines.append(line)
    body_text = "\n".join(lines)

    try:
        comments = list(doc.comments)
    except Exception:
        comments = []
    if comments:
        comment_lines = [f"- {c.author or 'Unknown reviewer'}: {c.text}" for c in comments if c.text and c.text.strip()]
        if comment_lines:
            body_text += "\n\n--- Reviewer Comments (from Word comments) ---\n" + "\n".join(comment_lines)

    return body_text


def extract_pdf_with_annotations(uploaded_file):
    """Extracts PDF text plus any sticky-note/comment annotations. Bold/strikethrough
    detection isn't attempted for PDFs — pypdf's text extraction doesn't expose per-
    character font styling, and strikethrough in a PDF is often just a drawn line
    rather than a text attribute, so it can't be reliably detected generically."""
    reader = pypdf.PdfReader(uploaded_file)
    pages = [page.extract_text() or "" for page in reader.pages]
    text = "\n".join(pages)
    if not text.strip():
        st.warning("No extractable text found in this PDF — it may be a scanned/image-only document.")

    annotation_lines = []
    for page in reader.pages:
        if not page.annotations:
            continue
        for a in page.annotations:
            obj = a.get_object()
            contents = obj.get("/Contents")
            if contents and str(contents).strip():
                annotation_lines.append(f"- {obj.get('/T', 'Unknown reviewer')}: {contents}")
    if annotation_lines:
        text += "\n\n--- Reviewer Comments (from PDF annotations) ---\n" + "\n".join(annotation_lines)

    return text


def extract_text_from_upload(uploaded_file):
    name = uploaded_file.name
    ext = name.split(".")[-1].lower()
    uploaded_file.seek(0)
    try:
        if ext == "txt":
            return uploaded_file.read().decode("utf-8", errors="ignore")
        elif ext == "pdf":
            return extract_pdf_with_annotations(uploaded_file)
        elif ext == "docx":
            return extract_docx_with_formatting(uploaded_file)
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


def fetch_url_text(url, timeout=10):
    """Fetches a public webpage and returns its visible text plus a best-guess title.
    Only handles publicly-accessible pages — see the 'Pages that require a login' note
    in the Project & Documents tab for why authenticated fetching isn't implemented."""
    headers = {"User-Agent": "Mozilla/5.0 (compatible; ScopeForge-DocBot/1.0)"}
    resp = requests.get(url, headers=headers, timeout=timeout)
    resp.raise_for_status()

    content_type = resp.headers.get("Content-Type", "").lower()
    if "text/plain" in content_type:
        return resp.text, url

    soup = BeautifulSoup(resp.text, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    title = soup.title.string.strip() if (soup.title and soup.title.string) else url
    raw = soup.get_text(separator="\n")
    cleaned = "\n".join(line.strip() for line in raw.splitlines() if line.strip())
    return cleaned, title


def truncate(text, limit=MAX_CHARS):
    if len(text) > limit:
        return text[:limit], True
    return text, False


# --- File Building (generating downloads) ---

def build_xlsx_from_df(sheet_name, df):
    wb = Workbook()
    ws = wb.active
    ws.title = (sheet_name or "Sheet1")[:31]
    ws.append([str(c) for c in df.columns])
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill(start_color="1F2333", end_color="1F2333", fill_type="solid")
    for _, row in df.iterrows():
        ws.append(["" if pd.isna(v) else v for v in row.tolist()])
    for i in range(1, len(df.columns) + 1):
        ws.column_dimensions[ws.cell(row=1, column=i).column_letter].width = 28
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def build_docx_table_from_df(title, df):
    doc = Document()
    doc.add_heading(title, level=0)
    table = doc.add_table(rows=1, cols=len(df.columns))
    table.style = "Light Grid Accent 1"
    hdr_cells = table.rows[0].cells
    for i, col in enumerate(df.columns):
        hdr_cells[i].text = str(col)
    for _, row in df.iterrows():
        cells = table.add_row().cells
        for i, v in enumerate(row.tolist()):
            cells[i].text = "" if pd.isna(v) else str(v)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def build_docx_from_markdown(title, markdown_text):
    doc = Document()
    doc.add_heading(title, level=0)
    for raw_line in markdown_text.split("\n"):
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("#### "):
            doc.add_heading(line[5:], level=4)
        elif line.startswith("### "):
            doc.add_heading(line[4:], level=3)
        elif line.startswith("## "):
            doc.add_heading(line[3:], level=2)
        elif line.startswith("# "):
            doc.add_heading(line[2:], level=1)
        elif re.match(r"^[-*]\s+", line):
            doc.add_paragraph(re.sub(r"^[-*]\s+", "", line), style="List Bullet")
        elif re.match(r"^\d+\.\s+", line):
            doc.add_paragraph(re.sub(r"^\d+\.\s+", "", line), style="List Number")
        else:
            doc.add_paragraph(line.replace("**", "").replace("*", ""))
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


VISIO_COLUMNS = ["Process Step ID", "Process Step Description", "Next Step ID", "Connector Label", "Shape Type"]


def build_visio_dataviz_xlsx(rows):
    """Builds an Excel file in Microsoft's documented Data Visualizer 'Basic Flowchart'
    column format. Import this into Visio (Data > Create from Data / Data Visualizer
    template) to auto-generate an editable, real Visio diagram — this is the reliable,
    well-documented path; authoring a raw .vsdx binary from scratch isn't something that
    can be done robustly without Visio itself or a paid SDK."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Process Map"
    ws.append(VISIO_COLUMNS)
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill(start_color="1F2333", end_color="1F2333", fill_type="solid")
    for r in rows:
        ws.append([
            str(r.get("step_id", "")),
            r.get("process_step", ""),
            str(r.get("next_step_id", "")),
            "",
            r.get("shape_type", "Process"),
        ])
    # Force the ID columns to explicit text format — otherwise Excel may auto-interpret
    # values like "010" as the number 10, which would break step matching on import.
    for row in ws.iter_rows(min_row=2, min_col=1, max_col=1):
        row[0].number_format = "@"
    for row in ws.iter_rows(min_row=2, min_col=3, max_col=3):
        row[0].number_format = "@"
    for i in range(1, len(VISIO_COLUMNS) + 1):
        ws.column_dimensions[ws.cell(row=1, column=i).column_letter].width = 28
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# --- AI Task Functions ---

FORMATTING_GUIDANCE = (
    "\n\nSource content carried over from Word documents may include markdown-style "
    "formatting that reflects the original document's markup: **bold** text indicates "
    "emphasis or a critical/non-negotiable requirement; ~~struck-through~~ text indicates "
    "content that was removed, deprecated, or rejected — treat it as historical/As-Is "
    "context, not a current requirement, unless asked specifically about prior versions. "
    "A 'Reviewer Comments' section (from Word comments or PDF annotations) contains "
    "stakeholder/reviewer feedback — factor it into your analysis as you would any other "
    "stated constraint or concern."
)


def analyze_gaps(text, notes=None):
    truncated_text, was_truncated = truncate(text)
    if was_truncated:
        st.caption(f"Document content was long — analyzing the first {MAX_CHARS:,} characters.")
    system = (
        "You are a senior business analyst performing a requirements quality review. "
        "Carefully read the provided notes/documents and identify ambiguities, missing "
        "non-functional requirements (performance, security, availability, etc.), stakeholder "
        "conflicts, and scope risks. Be specific and ground every finding in something actually "
        "present (or notably absent) in the text — do not invent details. If the text is sparse, "
        "it's fine to return fewer findings and a lower risk score."
    ) + FORMATTING_GUIDANCE
    user_prompt = f"Analyze the following content:\n\n{truncated_text}"
    if notes and notes.strip():
        user_prompt += (
            "\n\n---\nThe business analyst has also provided the following additional notes/context. "
            "You MUST factor these into your analysis — they may resolve an apparent gap, introduce "
            "a new constraint or decision, or point you toward something specific to scrutinize:\n"
            f"{notes.strip()}"
        )
    return call_structured(
        system, user_prompt, "submit_gap_analysis",
        "Submit the structured requirements gap analysis.", GAP_ANALYSIS_SCHEMA,
    )


def generate_document(doc_type, context_text, user_suggestion):
    context_text, was_truncated = truncate(context_text)
    if was_truncated:
        st.caption(f"Source content was long — using the first {MAX_CHARS:,} characters.")
    system = (
        "You are a senior business analyst drafting professional project documentation. "
        "Write a well-structured, realistic first draft in Markdown. Use clear section headers. "
        "Where the source content doesn't cover something, write '[Needs stakeholder input]' "
        "rather than inventing specifics."
    ) + FORMATTING_GUIDANCE
    user_prompt = (
        f"Document type to draft: {doc_type}\n\n"
        f"Special instructions / focus areas from the analyst:\n{user_suggestion}\n\n"
        f"Source content / requirements notes to base this on:\n"
        f"{context_text if context_text.strip() else '(No source content provided — draft a generic template with clear placeholder sections.)'}"
    )
    return call_text(system, user_prompt, max_tokens=2500)


def generate_data_dictionary(context_text, user_suggestion):
    context_text, was_truncated = truncate(context_text)
    if was_truncated:
        st.caption(f"Source content was long — using the first {MAX_CHARS:,} characters.")
    system = (
        "You are a senior business analyst building a data dictionary. Identify every distinct "
        "data field/entity attribute implied by the source content and document it. Only include "
        "fields actually supported by the source content."
    ) + FORMATTING_GUIDANCE
    user_prompt = (
        f"Special instructions / focus areas:\n{user_suggestion}\n\n"
        f"Source content:\n{context_text if context_text.strip() else '(No source content provided.)'}"
    )
    result = call_structured(
        system, user_prompt, "submit_data_dictionary",
        "Submit the structured data dictionary.", DATA_DICT_SCHEMA, max_tokens=3000,
    )
    return result.get("fields", []) if result else []


def generate_asis_tobe(context_text, user_suggestion):
    context_text, was_truncated = truncate(context_text)
    if was_truncated:
        st.caption(f"Source content was long — using the first {MAX_CHARS:,} characters.")
    system = (
        "You are a senior business analyst mapping a business process for an As-Is / To-Be "
        "analysis. Break the process into sequential steps. For each step, describe the current "
        "(As-Is) state, the proposed future (To-Be) state, and the specific gap/change needed to "
        "get from one to the other. Assign a shape_type for flowchart purposes (Start/Process/"
        "Decision/End) and a next_step_id describing what step(s) follow (comma-separated, no "
        "spaces, blank for the End step). Only build steps actually supported by the source content. "
        "Pay close attention to struck-through text in the source — it usually marks a requirement "
        "or process step that was cut, so it belongs in the As-Is description (as something that "
        "existed/was proposed) but generally should NOT carry into the To-Be description unless the "
        "source clearly indicates it's being reinstated."
    ) + FORMATTING_GUIDANCE
    user_prompt = (
        f"Special instructions / focus areas:\n{user_suggestion}\n\n"
        f"Source content describing the process:\n{context_text if context_text.strip() else '(No source content provided.)'}"
    )
    result = call_structured(
        system, user_prompt, "submit_asis_tobe",
        "Submit the structured As-Is / To-Be process map.", ASIS_TOBE_SCHEMA, max_tokens=3000,
    )
    return result.get("steps", []) if result else []


def generate_stories(source_text):
    source_text, was_truncated = truncate(source_text)
    if was_truncated:
        st.caption(f"Source content was long — using the first {MAX_CHARS:,} characters.")
    system = (
        "You are a senior business analyst converting requirements into an Agile backlog. "
        "For each distinct requirement or need in the source text, write one user story in the "
        "format 'As a <role>, I want <capability>, so that <benefit>', plus Gherkin-style "
        "acceptance criteria (GIVEN/WHEN/THEN). Only create stories that are actually supported "
        "by the source text."
    ) + FORMATTING_GUIDANCE
    user_prompt = f"Source requirements/notes:\n\n{source_text}"
    result = call_structured(
        system, user_prompt, "submit_stories",
        "Submit the generated user stories and acceptance criteria.", STORY_SCHEMA, max_tokens=2500,
    )
    return result.get("stories", []) if result else []


def process_meeting(transcript_text):
    truncated_text, was_truncated = truncate(transcript_text)
    if was_truncated:
        st.caption(f"Transcript was long — analyzing the first {MAX_CHARS:,} characters.")
    system = (
        "You are an assistant that turns raw meeting transcripts into structured minutes. "
        "Extract a concise executive summary, key decisions, and action items with an owner "
        "and due date if stated. Use 'Unassigned' / 'Not specified' rather than guessing."
    ) + FORMATTING_GUIDANCE
    user_prompt = f"Meeting transcript:\n\n{truncated_text}"
    return call_structured(
        system, user_prompt, "submit_meeting_minutes",
        "Submit the structured meeting minutes.", MEETING_SCHEMA,
    )


def chat_with_bot(history):
    proj = get_project()
    proj_name = get_current_project_name()
    context_note = f"\n\nThe user is currently working in the '{proj_name}' project."
    if proj.get("description"):
        context_note += f" Project description: {proj['description'][:500]}"
    if proj.get("documents"):
        doc_names = ", ".join(d["name"] for d in proj["documents"][:10])
        context_note += f" Documents in this project's repository: {doc_names}."
    return call_chat(CHATBOT_SYSTEM_PROMPT + context_note, history, max_tokens=800)


# --- Role-Specific Functions ---

def render_dashboard(proj, cp):
    section_header("BA Dashboard", f"Summary view for {cp} in this session.", SECTION_COLORS["dashboard"])

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("User Stories Drafted", proj.get("stories_drafted", 0))
    col2.metric("Documents Drafted", proj.get("documents_drafted", 0))
    col3.metric("Repository Documents", len(proj.get("documents", [])))

    gap_result = proj.get("gap_analysis")
    open_gaps = len(gap_result.get("open_questions", [])) if gap_result else 0
    col4.metric("Open Gaps (latest analysis)", open_gaps)

    st.caption(
        "These metrics reflect activity for this project in your current browser session only. "
        "Tracking activity persistently across sessions/users would require a database backend."
    )


def ba_module():
    st.markdown(
        "<div style='font-size:1.7rem; font-weight:700;'>Strategic Requirements Hub</div>",
        unsafe_allow_html=True,
    )
    st.caption("AI-augmented tools for elicitation, documentation, and Agile workflow.")

    cp = get_current_project_name()
    proj = get_project()

    view = st.radio(
        "View", ["Workspace", "Dashboard"],
        horizontal=True, key=f"ba_view_{cp}", label_visibility="collapsed",
    )
    st.markdown("<hr style='margin-top:0.2rem;margin-bottom:1rem;'>", unsafe_allow_html=True)

    if view == "Dashboard":
        render_dashboard(proj, cp)
        return

    tab0, tab1, tab2, tab3, tab4 = st.tabs([
        "Project & Documents",
        "Meeting Intelligence & Actionizer",
        "Elicitation Analysis & Gap Detector",
        "Documentation Generator",
        "Agile Story & Backlog Creator",
    ])

    # --- Tab 0: Project & Documents ---
    with tab0:
        section_header("Project Information & Document Repository", f"Active project: {cp}", SECTION_COLORS["project"])

        col1, col2 = st.columns(2)
        with col1:
            proj["client"] = st.text_input("Client / Stakeholder", value=proj.get("client", ""), key=f"client_{cp}")
        with col2:
            proj["status"] = st.selectbox(
                "Status", PROJECT_STATUSES,
                index=PROJECT_STATUSES.index(proj.get("status", "Planning")),
                key=f"status_{cp}",
            )

        proj["description"] = st.text_area(
            "Project Description / Background", value=proj.get("description", ""), height=120, key=f"desc_{cp}",
        )

        st.markdown("---")
        st.markdown("#### Create a New Project")
        with st.form(key="new_project_form", clear_on_submit=True):
            new_name = st.text_input("New Project Name")
            new_desc = st.text_area("Description (optional)", height=80)
            submitted = st.form_submit_button("Create Project")
            if submitted:
                if not new_name.strip():
                    st.warning("Give the project a name.")
                elif new_name in st.session_state["projects"]:
                    st.warning("A project with this name already exists.")
                else:
                    new_proj = default_project()
                    new_proj["description"] = new_desc
                    st.session_state["projects"][new_name] = new_proj
                    st.session_state["pending_project_switch"] = new_name
                    st.success(f"Created project '{new_name}'.")
                    st.rerun()

        st.markdown("---")
        st.markdown("#### Document Repository")
        st.caption(
            "Documents added here are available as context to the Elicitation Analysis, "
            "Documentation Generator, and Story Creator tabs for this project. Word documents "
            "(.docx) are read with formatting awareness: **bold** text, ~~struck-through~~ text, "
            "and inline comments are preserved as signals for the AI — not flattened away. PDFs "
            "carry over sticky-note comments too. (Word's Track Changes redlines are a separate "
            "mechanism this can't see — only explicit strikethrough formatting and regular "
            "comments are captured.)"
        )

        repo_files = st.file_uploader(
            "Add documents to this project's repository",
            type=['txt', 'pdf', 'docx', 'xlsx', 'csv'],
            accept_multiple_files=True,
            key=f"repo_uploader_{cp}",
        )
        if st.button("Add to Repository", key=f"add_repo_btn_{cp}"):
            if not repo_files:
                st.warning("Choose at least one file first.")
            else:
                added = 0
                for f in repo_files:
                    text = extract_text_from_upload(f)
                    if text.strip():
                        add_doc_to_repo(proj, f.name, text, f.name.split(".")[-1].lower())
                        added += 1
                st.success(f"Added {added} document(s) to the repository.")
                st.rerun()

        if proj["documents"]:
            st.markdown(f"**{len(proj['documents'])} document(s) in repository:**")
            for i, doc in enumerate(proj["documents"]):
                c1, c2, c3, c4 = st.columns([4, 1, 2, 1])
                c1.write(doc["name"])
                c2.write(doc["ext"].upper())
                c3.write(f"{doc['char_count']:,} chars · added {doc['added_at']}")
                if c4.button("Remove", key=f"del_doc_{cp}_{i}"):
                    proj["documents"].pop(i)
                    st.rerun()
        else:
            st.info("No documents yet. Upload files above to build this project's repository.")

        st.markdown("---")
        st.markdown("#### Source URLs")
        st.caption(
            "Pull a public webpage's text straight into this project's repository, same as an "
            "uploaded file."
        )
        url_col1, url_col2 = st.columns([4, 1])
        with url_col1:
            url_input = st.text_input(
                "Public webpage URL", key=f"url_input_{cp}",
                placeholder="https://example.com/project-charter", label_visibility="collapsed",
            )
        with url_col2:
            fetch_clicked = st.button("Fetch URL", key=f"fetch_url_btn_{cp}", use_container_width=True)

        if fetch_clicked:
            if not url_input.strip():
                st.warning("Enter a URL first.")
            else:
                with st.spinner(f"Fetching {url_input.strip()}..."):
                    try:
                        text, title = fetch_url_text(url_input.strip())
                        if text.strip():
                            doc_name = f"[URL] {title or url_input.strip()}"
                            add_doc_to_repo(proj, doc_name, text, "url")
                            st.success(f"Added '{doc_name}' to the repository ({len(text):,} characters).")
                            st.rerun()
                        else:
                            st.warning("Fetched the page, but found no readable text on it.")
                    except requests.exceptions.HTTPError as e:
                        code = e.response.status_code if e.response is not None else None
                        if code in (401, 403):
                            st.error(
                                f"This page returned a {code} error — it likely requires you to be "
                                "logged in. See the note below."
                            )
                        else:
                            st.error(f"Couldn't fetch this URL ({code or 'HTTP error'}).")
                    except requests.exceptions.RequestException as e:
                        st.error(f"Couldn't reach this URL: {e}")

        with st.expander("Pages that require a login"):
            st.markdown(
                "This intentionally does **not** ask for a username/password to log into a site "
                "automatically. Two reasons:\n\n"
                "1. **Security** — handling another site's credentials inside this app means they "
                "pass through its server-side code. That's a real exposure surface for something "
                "that's supposed to be a lightweight internal tool, even if nothing is stored.\n"
                "2. **Reliability** — login flows vary enormously (SSO, MFA, CAPTCHAs, JavaScript-"
                "rendered forms). A generic auto-login would break on most real sites anyway, "
                "which isn't worth the security tradeoff above.\n\n"
                "The reliable workaround: open the page in your own browser while logged in, then "
                "either save it as a PDF/Word file or copy the text, and upload it using the "
                "Document Repository above. Same end result, no credentials ever touch this app."
            )

    # --- Tab 1: Meeting Intelligence ---
    with tab1:
        section_header(
            "Meeting Intelligence & Actionizer",
            "Transform raw meeting transcripts into structured minutes, decisions, and action items.",
            SECTION_COLORS["meeting"],
        )

        uploaded_transcript = st.file_uploader(
            "Upload Meeting Transcript (.txt or .docx):", type=['txt', 'docx'], key=f"transcript_uploader_{cp}",
        )

        if st.button("Process Transcript", key=f"process_transcript_btn_{cp}"):
            if uploaded_transcript is not None:
                with st.spinner("Extracting text..."):
                    text = extract_text_from_upload(uploaded_transcript)
                if not text.strip():
                    st.error("Couldn't extract any readable text from this transcript.")
                else:
                    with st.spinner("Extracting decisions, owners, and actions..."):
                        result = process_meeting(text)
                    if result:
                        proj["meeting_result"] = result
            else:
                st.warning("Please upload a transcript to process.")

        result = proj.get("meeting_result")
        if result:
            st.success("Meeting summary generated.")
            st.markdown("### Executive Summary")
            st.info(result.get("summary", ""))

            decisions = result.get("decisions", [])
            if decisions:
                st.markdown("### Key Decisions")
                for d in decisions:
                    st.write(f"- {d}")

            st.markdown("### Action Items Extracted")
            items = result.get("action_items", [])
            if items:
                action_df = pd.DataFrame(items)
                st.dataframe(action_df, use_container_width=True)
                dl1, dl2 = st.columns(2)
                with dl1:
                    st.download_button(
                        "Download as Excel (.xlsx)", build_xlsx_from_df("Action Items", action_df),
                        file_name="meeting_action_items.xlsx", mime=XLSX_MIME,
                    )
                with dl2:
                    st.download_button(
                        "Download as CSV (.csv)", action_df.to_csv(index=False),
                        file_name="meeting_action_items.csv", mime="text/csv",
                    )
            else:
                st.caption("No explicit action items were detected in this transcript.")

    # --- Tab 2: Elicitation Analysis ---
    with tab2:
        section_header(
            "Elicitation Analysis & Gap Detector",
            "Upload raw notes or transcripts. AI will structure needs and identify open questions.",
            SECTION_COLORS["elicitation"],
        )

        repo_doc_names = [d["name"] for d in proj["documents"]]
        selected_repo_docs = []
        if repo_doc_names:
            selected_repo_docs = st.multiselect(
                "Include documents already in this project's repository:",
                repo_doc_names, default=repo_doc_names, key=f"elicit_repo_select_{cp}",
            )

        uploaded_file = st.file_uploader(
            "Upload a new Notes/Transcript or Document for this analysis:",
            type=['txt', 'pdf', 'docx', 'xlsx', 'csv'], key=f"gap_uploader_{cp}",
        )
        st.info(
            "Note on file intake: for proprietary formats (e.g., Apple Pages/Numbers, Visio, or "
            "live Google Docs/Sheets), please export to a universal format like .docx, .pdf, or "
            ".txt before uploading."
        )

        save_to_repo = False
        if uploaded_file is not None:
            save_to_repo = st.checkbox(
                "Also add this file to the project's document repository", value=True, key=f"gap_save_to_repo_{cp}",
            )

        notes = st.text_area(
            "Additional Notes / Context (optional):",
            placeholder=(
                "e.g., Focus on the payments workflow. The budget ceiling of $1M was confirmed "
                "by the sponsor on 6/10 — flag anything that conflicts with it."
            ),
            key=f"elicit_notes_{cp}", height=100,
        )
        if notes and notes.strip():
            st.caption("These notes will be factored into the analysis.")

        if st.button("Analyze for Gaps", key=f"analyze_gaps_btn_{cp}"):
            combined_parts = []
            for name in selected_repo_docs:
                doc = next((d for d in proj["documents"] if d["name"] == name), None)
                if doc:
                    combined_parts.append(f"--- Repository Document: {name} ---\n{doc['text']}")

            if uploaded_file is not None:
                with st.spinner("Extracting text from uploaded document..."):
                    new_text = extract_text_from_upload(uploaded_file)
                if new_text.strip():
                    combined_parts.append(f"--- Uploaded Document: {uploaded_file.name} ---\n{new_text}")
                    if save_to_repo:
                        add_doc_to_repo(proj, uploaded_file.name, new_text, uploaded_file.name.split(".")[-1].lower())

            combined_text = "\n\n".join(combined_parts)

            if not combined_text.strip():
                st.warning("Upload a document or select at least one repository document to analyze.")
            else:
                proj["extracted_text"] = combined_text
                proj["last_notes"] = notes or ""
                with st.spinner("Cross-referencing against requirements quality standards..."):
                    result = analyze_gaps(combined_text, notes=notes)
                if result:
                    proj["gap_analysis"] = result

        result = proj.get("gap_analysis")
        if result:
            n_open = len(result.get("open_questions", []))
            st.success(f"Analysis complete. Found {n_open} open item(s) for stakeholder follow-up.")
            if proj.get("last_notes"):
                st.caption(f"Notes accounted for: \"{proj['last_notes'][:200]}\"")
            if result.get("summary"):
                st.caption(result["summary"])
            st.metric(
                label="Requirements Risk Score",
                value=f"{result.get('risk_score', 0)}/100 ({result.get('risk_level', 'Unknown')})",
            )

            st.markdown("### Open Questions for Stakeholders")
            if n_open == 0:
                st.info("No significant gaps detected in this content.")
            for q in result.get("open_questions", []):
                st.warning(f"**{q.get('type', 'Issue')}:** {q.get('issue', '')}\n\n*Why it matters:* {q.get('why_it_matters', '')}")

    # --- Tab 3: Documentation Generator ---
    with tab3:
        section_header(
            "Documentation Generator",
            "Generate a real first-draft document from your requirements notes, exportable to Word or Excel.",
            SECTION_COLORS["docgen"],
        )

        doc_type = st.selectbox("Select Document Type to Draft", list(DOC_TYPE_CODES.keys()), key=f"doc_type_select_{cp}")

        repo_doc_names = [d["name"] for d in proj["documents"]]
        selected_repo_docs = []
        if repo_doc_names:
            selected_repo_docs = st.multiselect(
                "Include documents from this project's repository:",
                repo_doc_names, default=repo_doc_names, key=f"doc_repo_select_{cp}",
            )

        repo_text_parts = []
        for name in selected_repo_docs:
            doc = next((d for d in proj["documents"] if d["name"] == name), None)
            if doc:
                repo_text_parts.append(f"--- {name} ---\n{doc['text']}")
        repo_combined = "\n\n".join(repo_text_parts)

        context_text = st.text_area(
            "Additional source content / notes (combined with the repository documents selected above):",
            value="" if repo_doc_names else proj.get("extracted_text", "")[:2000],
            height=120, key=f"doc_context_{cp}",
        )
        full_context = f"{repo_combined}\n\n{context_text}".strip() if repo_combined else context_text

        user_suggestion = st.text_area(
            "Provide specific instructions or focus areas:",
            "e.g., Ensure the regulatory compliance section is highly detailed.",
            key=f"doc_suggestion_{cp}",
        )

        if st.button(f"Generate Draft {doc_type}", key=f"generate_doc_btn_{cp}"):
            if doc_type == "Data Dictionary":
                with st.spinner("Drafting data dictionary..."):
                    rows = generate_data_dictionary(full_context, user_suggestion)
                if rows:
                    proj["documents_drafted"] = proj.get("documents_drafted", 0) + 1
                    proj["last_doc_draft"] = {"kind": "data_dictionary", "rows": rows}
                    proj["last_doc_type"] = doc_type
            elif doc_type == "As-Is / To-Be Process Document":
                with st.spinner("Mapping As-Is and To-Be process steps..."):
                    rows = generate_asis_tobe(full_context, user_suggestion)
                if rows:
                    proj["documents_drafted"] = proj.get("documents_drafted", 0) + 1
                    proj["last_doc_draft"] = {"kind": "asis_tobe", "rows": rows}
                    proj["last_doc_type"] = doc_type
            else:
                with st.spinner(f"Drafting {doc_type}..."):
                    draft = generate_document(doc_type, full_context, user_suggestion)
                if draft:
                    proj["documents_drafted"] = proj.get("documents_drafted", 0) + 1
                    proj["last_doc_draft"] = {"kind": "markdown", "text": draft}
                    proj["last_doc_type"] = doc_type

        saved = proj.get("last_doc_draft")
        if saved:
            shown_type = proj.get("last_doc_type", doc_type)
            code = DOC_TYPE_CODES.get(shown_type, "Document")
            st.success(f"Draft of {shown_type} generated.")

            if saved["kind"] == "markdown":
                st.markdown(saved["text"])
                dl1, dl2 = st.columns(2)
                with dl1:
                    st.download_button(
                        "Download as Word (.docx)", build_docx_from_markdown(shown_type, saved["text"]),
                        file_name=f"{code}.docx", mime=DOCX_MIME,
                    )
                with dl2:
                    st.download_button(
                        "Download as Markdown (.md)", saved["text"], file_name=f"{code}.md", mime="text/markdown",
                    )

            elif saved["kind"] == "data_dictionary":
                df = pd.DataFrame(saved["rows"])
                df = df.rename(columns={
                    "field_name": "Field Name", "data_type": "Data Type", "description": "Description",
                    "source_system": "Source System", "validation_rules": "Validation Rules",
                })
                df = df.reindex(columns=["Field Name", "Data Type", "Description", "Source System", "Validation Rules"], fill_value="")
                st.dataframe(df, use_container_width=True)
                dl1, dl2 = st.columns(2)
                with dl1:
                    st.download_button(
                        "Download as Excel (.xlsx)", build_xlsx_from_df("Data Dictionary", df),
                        file_name=f"{code}.xlsx", mime=XLSX_MIME,
                    )
                with dl2:
                    st.download_button(
                        "Download as Word (.docx)", build_docx_table_from_df("Data Dictionary", df),
                        file_name=f"{code}.docx", mime=DOCX_MIME,
                    )

            elif saved["kind"] == "asis_tobe":
                df = pd.DataFrame(saved["rows"])
                df = df.rename(columns={
                    "step_id": "Step ID", "process_step": "Process Step", "as_is_description": "As-Is",
                    "to_be_description": "To-Be", "gap_or_change": "Gap / Change Needed",
                    "shape_type": "Shape Type", "next_step_id": "Next Step ID",
                })
                col_order = ["Step ID", "Process Step", "As-Is", "To-Be", "Gap / Change Needed", "Shape Type", "Next Step ID"]
                df = df.reindex(columns=col_order, fill_value="")
                st.dataframe(df, use_container_width=True)

                dl1, dl2, dl3 = st.columns(3)
                with dl1:
                    st.download_button(
                        "Download as Excel (.xlsx)", build_xlsx_from_df("As-Is To-Be", df),
                        file_name=f"{code}.xlsx", mime=XLSX_MIME,
                    )
                with dl2:
                    st.download_button(
                        "Download as Word (.docx)", build_docx_table_from_df("As-Is / To-Be Process Document", df),
                        file_name=f"{code}.docx", mime=DOCX_MIME,
                    )
                with dl3:
                    st.download_button(
                        "Download Visio Process Map (.xlsx)", build_visio_dataviz_xlsx(saved["rows"]),
                        file_name=f"{code}_VisioDataVisualizer.xlsx", mime=XLSX_MIME,
                    )
                st.caption(
                    "The Visio Process Map file is formatted for Visio's built-in Data Visualizer "
                    "feature: in Visio, start a Data Visualizer Basic Flowchart template and import "
                    "this file to auto-generate an editable diagram. (Native .vsdx files can't be "
                    "reliably authored from scratch without Visio itself or a paid SDK — this Excel-based "
                    "import is the documented, reliable path to a real Visio diagram.)"
                )

    # --- Tab 4: Agile Story Creator ---
    with tab4:
        section_header(
            "Agile Story & Backlog Creator",
            "Convert validated requirements into ready-to-import User Stories and Gherkin Acceptance Criteria.",
            SECTION_COLORS["story"],
        )

        repo_doc_names = [d["name"] for d in proj["documents"]]
        selected_repo_docs = []
        if repo_doc_names:
            selected_repo_docs = st.multiselect(
                "Include documents from this project's repository:",
                repo_doc_names, default=repo_doc_names, key=f"story_repo_select_{cp}",
            )

        repo_text_parts = []
        for name in selected_repo_docs:
            doc = next((d for d in proj["documents"] if d["name"] == name), None)
            if doc:
                repo_text_parts.append(f"--- {name} ---\n{doc['text']}")
        repo_combined = "\n\n".join(repo_text_parts)

        notes_text = st.text_area(
            "Additional requirements / notes (combined with the repository documents selected above):",
            value="" if repo_doc_names else proj.get("extracted_text", "")[:2000],
            height=120, key=f"story_source_{cp}",
        )
        source_text = f"{repo_combined}\n\n{notes_text}".strip() if repo_combined else notes_text

        if st.button("Generate User Stories & Acceptance Criteria", key=f"generate_stories_btn_{cp}"):
            if not source_text.strip():
                st.warning("Add some requirements text, or select at least one repository document, first.")
            else:
                with st.spinner("Drafting user stories and acceptance criteria..."):
                    stories = generate_stories(source_text)
                if stories:
                    proj["stories"] = stories
                    proj["stories_drafted"] = proj.get("stories_drafted", 0) + len(stories)

        stories = proj.get("stories", [])
        if stories:
            st.markdown("### User Story Drafts")
            story_df = pd.DataFrame(stories)
            edited_df = st.data_editor(story_df, use_container_width=True, num_rows="dynamic", key=f"story_editor_{cp}")

            dl1, dl2 = st.columns(2)
            with dl1:
                st.download_button(
                    "Download as Excel (.xlsx)", build_xlsx_from_df("Backlog", edited_df),
                    file_name="backlog_stories.xlsx", mime=XLSX_MIME,
                )
            with dl2:
                st.download_button(
                    "Download as CSV — Jira/Azure DevOps import format (.csv)", edited_df.to_csv(index=False),
                    file_name="backlog_stories.csv", mime="text/csv",
                )
        else:
            st.info("Generate stories to see them here.")


def pm_module():
    section_header(
        "Project Managers: Predictive Risk & Health (Placeholder)",
        "View predictive metrics, resource optimization, and automated status reports.",
        SECTION_COLORS["pm"],
    )
    st.selectbox("Select Project to View", list(st.session_state["projects"].keys()))
    st.info("PM features (Project Health Forecaster, Constraint Solver) haven't been built yet — this module is still a placeholder.")


def pgm_module():
    section_header(
        "Program Managers: Portfolio Optimization (Placeholder)",
        "Analyze cross-project dependencies, resource contention, and benefit realization.",
        SECTION_COLORS["pgm"],
    )
    st.warning("PgM features (Interdependency Mapper, Benefit Realization Tracker) haven't been built yet — this module is still a placeholder.")


# --- Main App Navigation ---

if not check_access():
    st.stop()

inject_theme()
render_masthead()
init_projects()

# Apply any pending project switch (e.g. from creating a new project) BEFORE the
# sidebar selectbox below is instantiated — Streamlit won't allow setting a widget's
# session_state value after that widget has already rendered in the same run.
if "pending_project_switch" in st.session_state:
    _target = st.session_state.pop("pending_project_switch")
    if _target in st.session_state["projects"]:
        st.session_state["current_project"] = _target

st.sidebar.markdown(
    f"<div style='font-size:1.6rem; font-weight:800; color:{ACCENT}; letter-spacing:0.5px;'>ScopeForge</div>"
    f"<div style='font-size:0.8rem; color:{SIDEBAR_MUTED}; margin-bottom:0.8rem;'>Consulting Accelerator</div>",
    unsafe_allow_html=True,
)

st.sidebar.subheader("Active Project")
project_names = list(st.session_state["projects"].keys())
st.sidebar.selectbox("Select Project", project_names, key="current_project")

st.sidebar.markdown("---")
st.sidebar.subheader("Modules")
role = st.sidebar.radio("Select Your Role", ["Business Analyst (BA)", "Project Manager (PM)", "Program Manager (PgM)"])

st.sidebar.markdown("---")
st.sidebar.selectbox(
    "AI Model", [DEFAULT_MODEL, FAST_MODEL], index=0, key="model",
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
section_header("ScopeBot (AI Assistant)", "Ask about requirements, JIRA sync, or BA best practices.", SECTION_COLORS["chat"])

if "chat_history" not in st.session_state:
    st.session_state["chat_history"] = []

for msg in st.session_state["chat_history"]:
    st.chat_message(msg["role"]).write(msg["content"])

user_query = st.chat_input("Ask ScopeBot a question about requirements, JIRA sync, or best practices...")

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
