import streamlit as st
import pandas as pd
import random
import time

# --- Configuration & Setup ---
st.set_page_config(layout="wide", page_title="SynergyAI: Consulting Accelerator")

# Dummy data for demonstration
PROJECTS = ["Alpha-FinTech Migration", "Beta-Supply Chain Optimization", "Gamma-HR Platform Rollout"]
USERS = ["Alice (BA)", "Bob (PM)", "Charlie (PgM)"]


# --- Role-Specific Functions (Placeholder for AI Logic) ---

def ba_module():
    st.header("💼 Business Analysts: Requirements & Insights")

    # Requirements Accelerator
    st.subheader("1. Requirements Accelerator (Insight Synthesizer)")
    uploaded_file = st.file_uploader("Upload Interview Transcripts (.txt or .pdf):", type=['txt', 'pdf'])

    if st.button("Analyze & Draft User Stories"):
        if uploaded_file is not None:
            # Placeholder for GenAI API call (e.g., Gemini/OpenAI)
            with st.spinner('Analyzing complexity and drafting stories...'):
                time.sleep(2) # Simulate AI processing time

            st.success("Analysis Complete!")
            st.metric(label="Requirements Risk Score", value=f"{random.randint(55, 95)}/100 (Moderate)", delta="-5% from last week")

            stories = [
                "As a user, I want to filter transaction data by date range so I can easily reconcile daily totals.",
                "As a manager, I need to receive an alert when a transaction exceeds $50k, to monitor high-value activity.",
                "As a system admin, I need the database connection to be encrypted, to meet compliance standards."
            ]

            st.markdown("### 📝 Auto-Drafted User Stories (Editable)")
            df = pd.DataFrame({'User Story': stories, 'Priority': ['High', 'High', 'Medium'], 'Status': ['Draft', 'Draft', 'Draft']})
            st.data_editor(df, num_rows="dynamic")
        else:
            st.warning("Please upload a file to analyze.")


def pm_module():
    st.header("🗓️ Project Managers: Predictive Risk & Health")

    selected_project = st.selectbox("Select Project to View", PROJECTS)

    # Predictive Risk & Health
    st.subheader("1. Project Health Forecaster")

    col1, col2, col3 = st.columns(3)

    # Placeholder for AI-driven metrics
    with col1:
        st.metric(label="Predicted Completion Date", value="2026-03-15", delta="-10 Days")
    with col2:
        st.metric(label="Predicted Budget Variance", value="$15k Over", delta="+$5k (Worse)")
    with col3:
        st.metric(label="Resource Sentiment Score", value="78/100", delta="+3 (Better)")

    st.warning("⚠️ **Alert:** Task 'Security Review' has a 75% probability of a 3-day delay.")

    # Communication Automation
    st.subheader("2. Stakeholder Communication")
    st.caption("Auto-generate a draft status update based on the AI health report.")

    if st.button("Generate Weekly Status Report"):
        report_draft = (
            f"**Project Status Update: {selected_project} (Week Ending: {pd.to_datetime('today').strftime('%Y-%m-%d')})**\n\n"
            "Overall project health is **Yellow**. While the team is performing well (Sentiment: 78/100), "
            "we have identified a high-risk dependency. The **Security Review** task has a 75% chance "
            "of being delayed by 3 days, potentially impacting the final go-live date. "
            "Mitigation: The team is engaging an external contractor for parallel review.\n\n"
            "**Key Metrics:**\n"
            "* Budget: $15k Over Budget (Forecast)\n"
            "* Timeline: Predicted 10-day slip from baseline."
        )
        st.text_area("Report Draft", report_draft, height=300)

def pgm_module():
    st.header("🗺️ Program Managers: Portfolio Optimization")

    st.subheader("1. Interdependency Mapper (Graph Visualization Placeholder)")
    st.markdown("This section would show a network graph identifying critical path dependencies and shared resource contention across multiple projects in the portfolio.")
    st.warning("❗️ **Resource Contention Alert:** Project Alpha and Project Gamma are competing for Senior Architect resources in Q1. The AI recommends shifting 50% of Alpha's early-stage scoping to a Mid-Level BA.")

    st.subheader("2. Benefit Realization Tracker")
    st.progress(75, text="Target Benefit 1: Reduce OpEx by 20% (75% on track)")
    st.progress(40, text="Target Benefit 2: Improve Customer NPS by 5 points (40% on track - Needs attention)")

# --- Main App Navigation ---

st.sidebar.title("SynergyAI Modules")
role = st.sidebar.radio("Select Your Role", ["Business Analyst (BA)", "Project Manager (PM)", "Program Manager (PgM)"])

st.sidebar.markdown("---")
# SynergyBot Chat in the Sidebar/Footer
st.sidebar.subheader("🤖 SynergyBot (AI Assistant)")
user_query = st.sidebar.chat_input("Ask SynergyBot a question...")

if user_query:
    st.sidebar.markdown(f"**You:** {user_query}")
    # Placeholder for GenAI response
    response = "I see you asked about this. I can help you with that! (Placeholder for actual GenAI response)"
    st.sidebar.info(f"**SynergyBot:** {response}")

# --- Display Selected Module ---
if role == "Business Analyst (BA)":
    ba_module()
elif role == "Project Manager (PM)":
    pm_module()
elif role == "Program Manager (PgM)":
    pgm_module()
