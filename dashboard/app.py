"""
Smart Clinic Dashboard - Main Streamlit Application.
Provides interactive clinic analytics overview and natural language query assistant interface.
"""

import os
import sys
from pathlib import Path
import streamlit as st
import pandas as pd
import plotly.express as px

# Ensure project root is in sys.path for clean imports
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# ==============================================================================
# SINGLE CONFIGURABLE CHATBOT IMPORT
# Powered by Hugging Face AI Text-to-SQL Model engine
# ==============================================================================
from chatbot.hf_chatbot import get_answer
# ==============================================================================

from database.db_utils import run_raw_query
from dashboard.components.kpi_cards import render_kpi_grid
from dashboard.components.charts import render_bar_chart, render_line_chart, render_pie_chart, render_table, render_chart_response
from chatbot.interface import ChatbotResponse

# Streamlit Page Configuration
st.set_page_config(
    page_title="Smart Clinic Dashboard",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Load Custom CSS Styling
CSS_PATH = ROOT_DIR / "dashboard" / "static" / "style.css"
if CSS_PATH.exists():
    with open(CSS_PATH, "r", encoding="utf-8") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


SAMPLE_QUESTIONS = [
    "How many patients are registered?",
    "Show appointments by month",
    "What are the top diagnoses?",
    "What is our revenue status?",
    "Top prescribed medications",
    "Show doctor workload",
    "Show pending invoices"
]


def load_overview_metrics():
    """Fetches high-level clinic metrics from SQLite DB."""
    try:
        patients_count = run_raw_query("SELECT COUNT(*) as c FROM patients").iloc[0]['c']
        appts_count = run_raw_query("SELECT COUNT(*) as c FROM appointments WHERE status='completed'").iloc[0]['c']
        rev_val = run_raw_query("SELECT SUM(amount_paid) as r FROM payments").iloc[0]['r'] or 0.0
        pending_val = run_raw_query("SELECT SUM(amount) as p FROM billing WHERE payment_status='pending'").iloc[0]['p'] or 0.0
        doctors_count = run_raw_query("SELECT COUNT(*) as c FROM doctors").iloc[0]['c']

        return [
            {"title": "Total Patients", "value": f"{patients_count:,}", "subtitle": "Registered in Database"},
            {"title": "Completed Visits", "value": f"{appts_count:,}", "subtitle": "Outpatient Encounters"},
            {"title": "Collected Revenue", "value": f"${rev_val:,.2f}", "subtitle": "Processed Payments"},
            {"title": "Pending Invoices", "value": f"${pending_val:,.2f}", "subtitle": "Awaiting Payment"},
            {"title": "Active Doctors", "value": str(doctors_count), "subtitle": "Across 6 Departments"}
        ]
    except Exception as e:
        st.error(f"Could not connect to database or database not yet generated: {e}")
        return []


def main():
    # Session state initialization
    if "chat_history" not in st.session_state:
        st.session_state["chat_history"] = []
    if "active_response" not in st.session_state:
        st.session_state["active_response"] = None
    if "last_executed_query" not in st.session_state:
        st.session_state["last_executed_query"] = None

    # Sidebar Navigation & Information
    with st.sidebar:
        st.markdown("## 🏥 Smart Clinic Admin")
        st.markdown("---")
        
        st.markdown("### 📊 Live Database Stats")
        metrics = load_overview_metrics()
        if metrics:
            st.metric("Total Patients", metrics[0]["value"])
            st.metric("Completed Encounters", metrics[1]["value"])
            st.metric("Collected Revenue", metrics[2]["value"])

        st.markdown("---")
        st.markdown("### 🤖 Hugging Face AI Chatbot")
        st.info(
            "**Active Model:** `cssupport/t5-small-awesome-text-to-sql`\n\n"
            "Converts natural language questions into SQLite queries and returns visual answers!"
        )
        st.markdown("---")
        st.caption("Smart Clinic Management System v1.0.0")

    # App Main Header
    st.markdown('<div class="section-header">🏥 Smart Clinic Interactive Dashboard</div>', unsafe_allow_html=True)
    st.markdown("Ask natural language questions to dynamically update dashboard visualizations & query clinic analytics.")

    # --------------------------------------------------------------------------
    # PROMINENT NATURAL LANGUAGE QUESTION INPUT SECTION (TOP OF DASHBOARD)
    # --------------------------------------------------------------------------
    st.markdown("### 💬 Ask a Question to Filter & Change Dashboard Results")

    # Sample Question Quick Chips
    st.markdown("**💡 Quick Question Shortcuts (Click to update dashboard):**")
    chip_cols = st.columns(len(SAMPLE_QUESTIONS))
    clicked_question = None

    for idx, sample_q in enumerate(SAMPLE_QUESTIONS):
        with chip_cols[idx % len(chip_cols)]:
            if st.button(sample_q, key=f"chip_btn_{idx}", use_container_width=True):
                clicked_question = sample_q

    # Text Input & Submit Button
    col_input, col_btn = st.columns([5, 1])
    with col_input:
        user_query = st.text_input(
            "Type any question about patients, appointments, diagnoses, revenue, or doctors:",
            placeholder="e.g. What are the top diagnoses? OR Show appointments by month",
            key="user_query_input_text"
        )
    with col_btn:
        st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
        ask_btn_clicked = st.button("Ask Question 🚀", key="ask_btn_trigger", use_container_width=True)

    # Determine candidate question
    candidate_query = None
    if clicked_question:
        candidate_query = clicked_question
    elif ask_btn_clicked and user_query and user_query.strip():
        candidate_query = user_query.strip()

    # Process query if it's new or requested
    if candidate_query and candidate_query != st.session_state.get("last_executed_query"):
        with st.spinner(f"AI Model Querying clinic database for: '{candidate_query}'..."):
            response: ChatbotResponse = get_answer(candidate_query)
            st.session_state["active_response"] = {
                "question": candidate_query,
                "response": response
            }
            st.session_state["last_executed_query"] = candidate_query
            st.session_state["chat_history"].insert(0, st.session_state["active_response"])

    # --------------------------------------------------------------------------
    # DYNAMIC QUERY RESULT BANNER & VISUALIZATION (CHANGES BASED ON QUESTION)
    # --------------------------------------------------------------------------
    if st.session_state.get("active_response"):
        active_item = st.session_state["active_response"]
        q_text = active_item["question"]
        resp: ChatbotResponse = active_item["response"]

        st.markdown("<hr style='border-color: rgba(56, 189, 248, 0.4); margin: 25px 0;'>", unsafe_allow_html=True)
        st.markdown(
            f"""
            <div class="qa-card" style="border: 2px solid #38bdf8;">
                <div class="qa-question-header" style="color: #38bdf8; font-size: 1.2rem;">
                    🎯 Active Query Result: "{q_text}"
                </div>
                <div class="qa-answer-text" style="font-size: 1.1rem; font-weight: 500;">
                    {resp['answer_text']}
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

        if resp.get("error"):
            st.error(f"Error: {resp['error']}")

        # Render Dynamic Chart/Table right here based on question
        if resp.get("chart_type") and resp["chart_type"] != "none":
            render_chart_response(
                chart_type=resp["chart_type"],
                data=resp.get("data", []),
                columns=resp.get("columns")
            )

        # Show SQL query collapsible
        if resp.get("sql_query"):
            with st.expander("🔍 How I got this answer (Generated SQL Query)", expanded=True):
                st.code(resp["sql_query"], language="sql")

        st.markdown("<hr style='border-color: rgba(255, 255, 255, 0.1); margin: 25px 0;'>", unsafe_allow_html=True)

    # --------------------------------------------------------------------------
    # DASHBOARD OVERVIEW & HISTORY TABS
    # --------------------------------------------------------------------------
    tab_overview, tab_history = st.tabs(["📊 Clinic Overview Dashboard", "📜 Past Questions History"])

    with tab_overview:
        st.markdown("### Executive Overview & Aggregate Analytics")
        if metrics:
            render_kpi_grid(metrics)

        st.markdown("<br>", unsafe_allow_html=True)

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("#### 📈 Monthly Appointment Trends")
            df_monthly = run_raw_query("""
                SELECT strftime('%Y-%m', appointment_date) AS month, COUNT(*) AS total_appointments
                FROM appointments
                GROUP BY month ORDER BY month ASC;
            """)
            render_line_chart(df_monthly, columns=["month", "total_appointments"])

        with col2:
            st.markdown("#### 🩺 Top Diagnoses Prevalence")
            df_diag = run_raw_query("""
                SELECT diagnosis_name, COUNT(*) AS patient_count
                FROM diagnoses
                GROUP BY diagnosis_name
                ORDER BY patient_count DESC LIMIT 7;
            """)
            render_bar_chart(df_diag, columns=["diagnosis_name", "patient_count"])

        col3, col4 = st.columns(2)
        with col3:
            st.markdown("#### 💳 Billing & Payment Breakdown")
            df_bill = run_raw_query("""
                SELECT payment_status, ROUND(SUM(amount), 2) AS total_amount
                FROM billing GROUP BY payment_status;
            """)
            render_pie_chart(df_bill, columns=["payment_status", "total_amount"])

        with col4:
            st.markdown("#### 👨‍⚕️ Doctors per Department")
            df_doc = run_raw_query("""
                SELECT d.name AS department_name, COUNT(doc.doctor_id) AS doctor_count
                FROM departments d
                LEFT JOIN doctors doc ON d.department_id = doc.department_id
                GROUP BY d.name;
            """)
            render_pie_chart(df_doc, columns=["department_name", "doctor_count"])

        st.markdown("#### 📋 Recent Patient Visits")
        df_recent = run_raw_query("""
            SELECT v.visit_id, p.first_name || ' ' || p.last_name AS patient_name,
                   d.first_name || ' ' || d.last_name AS doctor_name,
                   v.visit_date, diag.diagnosis_name
            FROM visits v
            JOIN patients p ON v.patient_id = p.patient_id
            JOIN doctors d ON v.doctor_id = d.doctor_id
            LEFT JOIN diagnoses diag ON v.visit_id = diag.visit_id
            ORDER BY v.visit_date DESC LIMIT 10;
        """)
        render_table(df_recent)

    with tab_history:
        if st.session_state["chat_history"]:
            c1, c2 = st.columns([4, 1])
            with c1:
                st.markdown(f"### Question & Answer History ({len(st.session_state['chat_history'])})")
            with c2:
                if st.button("Clear History 🗑️", key="clear_chat_hist"):
                    st.session_state["chat_history"] = []
                    st.session_state["active_response"] = None
                    st.session_state["last_executed_query"] = None
                    st.rerun()

            for item in st.session_state["chat_history"]:
                q_hist = item["question"]
                resp_hist: ChatbotResponse = item["response"]

                with st.container():
                    st.markdown(
                        f"""
                        <div class="qa-card">
                            <div class="qa-question-header">❓ {q_hist}</div>
                            <div class="qa-answer-text">{resp_hist['answer_text']}</div>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )

                    if resp_hist.get("chart_type") and resp_hist["chart_type"] != "none":
                        render_chart_response(
                            chart_type=resp_hist["chart_type"],
                            data=resp_hist.get("data", []),
                            columns=resp_hist.get("columns")
                        )

                    if resp_hist.get("sql_query"):
                        with st.expander("🔍 SQL Query Executed", expanded=False):
                            st.code(resp_hist["sql_query"], language="sql")

                    st.markdown("<br>", unsafe_allow_html=True)
        else:
            st.info("No past questions asked yet. Ask a question above to see your query history here!")


if __name__ == "__main__":
    main()
