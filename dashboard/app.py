"""
Smart Clinic Dashboard - Main Streamlit Application.
Provides interactive clinic analytics overview and natural language query assistant interface.
"""

import os
import sys
import base64
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
    page_title="Clinique La Vallée",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Load Custom CSS Styling
CSS_PATH = ROOT_DIR / "dashboard" / "static" / "style.css"
if CSS_PATH.exists():
    with open(CSS_PATH, "r", encoding="utf-8") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# Inject Background Image via Base64 CSS
def get_base64_of_bin_file(bin_file):
    with open(bin_file, 'rb') as f:
        data = f.read()
    return base64.b64encode(data).decode()

def render_custom_header():
    bg_path = ROOT_DIR / "dashboard" / "static" / "background.jpg"
    logo_path = ROOT_DIR / "dashboard" / "static" / "logo.png"
    
    bg_url = f"data:image/jpeg;base64,{get_base64_of_bin_file(bg_path)}" if bg_path.exists() else ""
    logo_img = f'<img src="data:image/png;base64,{get_base64_of_bin_file(logo_path)}" alt="Clinique La Vallée">' if logo_path.exists() else "Clinique La Vallée"
    
    header_html = f"""
    <div class="custom-nav-container">
        <div class="logo-overlay">
            {logo_img}
        </div>
        <div class="custom-nav">
            <div class="nav-links">
                <span>Tableau de Bord</span>
                <span>Patients</span>
                <span>Planning</span>
                <span>Médecins</span>
                <span>Facturation</span>
                <button class="nav-btn">DÉCONNEXION</button>
            </div>
        </div>
    </div>
    <div class="hero-section" style="background-image: url('{bg_url}');">
        <div class="hero-overlay"></div>
        <div class="hero-content">
            <div class="hero-subtitle">Portail du Personnel</div>
            <div class="hero-title">Système de Gestion</div>
            <div class="hero-desc">Accédez aux dossiers médicaux, gérez le planning des consultations, et suivez les indicateurs clés de performance de la clinique en temps réel.</div>
            <div class="hero-avail"><strong>Statut du système :</strong> En ligne</div>
            <button class="hero-btn">AFFICHER LES STATISTIQUES</button>
        </div>
    </div>
    <div class="info-bar">
        <div class="info-item">Gestion des Patients</div>
        <div class="info-item">Analyses & Rapports</div>
        <div class="info-item">Administration</div>
    </div>
    """
    st.markdown(header_html, unsafe_allow_html=True)


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

    render_custom_header()

    st.markdown('<div class="content-wrapper">', unsafe_allow_html=True)

    # --------------------------------------------------------------------------
    # SEARCH / QUERY INPUT SECTION
    # --------------------------------------------------------------------------
    st.markdown("### Assistant de Recherche")

    # Sample Question Quick Chips
    st.markdown("**Questions Fréquentes (Cliquez pour lancer la recherche) :**")
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
        ask_btn_clicked = st.button("Rechercher", key="ask_btn_trigger", use_container_width=True, type="primary")

    # Determine candidate question
    candidate_query = None
    if clicked_question:
        candidate_query = clicked_question
    elif ask_btn_clicked and user_query and user_query.strip():
        candidate_query = user_query.strip()

    # Process query if it's new or requested
    if candidate_query and candidate_query != st.session_state.get("last_executed_query"):
        with st.spinner(f"Analyse en cours : '{candidate_query}'..."):
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

        st.markdown("<hr style='border-color: rgba(76, 175, 80, 0.4); margin: 25px 0;'>", unsafe_allow_html=True)
        st.markdown(
            f"""
            <div class="qa-card">
                <div class="qa-question-header">
                    Résultat : "{q_text}"
                </div>
                <div class="qa-answer-text">
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
                columns=resp.get("columns"),
                key="chart_active_response"
            )

        # Show SQL query collapsible
        if resp.get("sql_query"):
            with st.expander("Voir la requête SQL générée", expanded=True):
                st.code(resp["sql_query"], language="sql")

        st.markdown("<hr style='border-color: rgba(76, 175, 80, 0.2); margin: 25px 0;'>", unsafe_allow_html=True)

    # --------------------------------------------------------------------------
    # DASHBOARD OVERVIEW & HISTORY TABS
    # --------------------------------------------------------------------------
    tab_overview, tab_history = st.tabs(["Tableau de Bord", "Historique de Recherche"])

    with tab_overview:
        st.markdown("### Aperçu Exécutif & Analytique Globale")
        metrics = load_overview_metrics()
        if metrics:
            render_kpi_grid(metrics)

        st.markdown("<br>", unsafe_allow_html=True)

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("#### Tendances Mensuelles des Rendez-vous")
            df_monthly = run_raw_query("""
                SELECT strftime('%Y-%m', appointment_date) AS month, COUNT(*) AS total_appointments
                FROM appointments
                GROUP BY month ORDER BY month ASC;
            """)
            render_line_chart(df_monthly, columns=["month", "total_appointments"], key="overview_monthly_trend")

        with col2:
            st.markdown("#### Prévalence des Diagnostics Principaux")
            df_diag = run_raw_query("""
                SELECT diagnosis_name, COUNT(*) AS patient_count
                FROM diagnoses
                GROUP BY diagnosis_name
                ORDER BY patient_count DESC LIMIT 7;
            """)
            render_bar_chart(df_diag, columns=["diagnosis_name", "patient_count"], key="overview_top_diagnoses")

        col3, col4 = st.columns(2)
        with col3:
            st.markdown("#### Répartition de la Facturation et des Paiements")
            df_bill = run_raw_query("""
                SELECT payment_status, ROUND(SUM(amount), 2) AS total_amount
                FROM billing GROUP BY payment_status;
            """)
            render_pie_chart(df_bill, columns=["payment_status", "total_amount"], key="overview_billing_breakdown")

        with col4:
            st.markdown("#### Médecins par Département")
            df_doc = run_raw_query("""
                SELECT d.name AS department_name, COUNT(doc.doctor_id) AS doctor_count
                FROM departments d
                LEFT JOIN doctors doc ON d.department_id = doc.department_id
                GROUP BY d.name;
            """)
            render_pie_chart(df_doc, columns=["department_name", "doctor_count"], key="overview_doctors_per_department")

        st.markdown("#### Visites Récentes des Patients")
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

        st.markdown("#### 🚚 Prescriptions Filled per Supplier")
        df_supplier_volume = run_raw_query("""
            SELECT s.name AS supplier_name, COUNT(p.prescription_id) AS prescriptions_filled
            FROM suppliers s
            JOIN medications m ON m.supplier_id = s.supplier_id
            LEFT JOIN prescriptions p ON p.medication_id = m.medication_id
            GROUP BY s.name
            ORDER BY prescriptions_filled DESC;
        """)
        render_bar_chart(df_supplier_volume, columns=["supplier_name", "prescriptions_filled"], key="overview_supplier_volume")

        st.markdown("#### 🏭 Supplier Directory")
        df_supplier_list = run_raw_query("""
            SELECT name AS supplier_name, category, contact_person, phone, email
            FROM suppliers
            ORDER BY name ASC;
        """)
        render_table(df_supplier_list)

    with tab_history:
        if st.session_state["chat_history"]:
            c1, c2 = st.columns([4, 1])
            with c1:
                st.markdown(f"### Historique des Questions ({len(st.session_state['chat_history'])})")
            with c2:
                if st.button("Effacer l'Historique", key="clear_chat_hist"):
                    st.session_state["chat_history"] = []
                    st.session_state["active_response"] = None
                    st.session_state["last_executed_query"] = None
                    st.rerun()

            for hist_idx, item in enumerate(st.session_state["chat_history"]):
                q_hist = item["question"]
                resp_hist: ChatbotResponse = item["response"]

                with st.container():
                    st.markdown(
                        f"""
                        <div class="qa-card">
                            <div class="qa-question-header">Question : {q_hist}</div>
                            <div class="qa-answer-text">{resp_hist['answer_text']}</div>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )

                    if resp_hist.get("chart_type") and resp_hist["chart_type"] != "none":
                        render_chart_response(
                            chart_type=resp_hist["chart_type"],
                            data=resp_hist.get("data", []),
                            columns=resp_hist.get("columns"),
                            key=f"chart_history_{hist_idx}"
                        )

                    if resp_hist.get("sql_query"):
                        with st.expander("Requête SQL Exécutée", expanded=False):
                            st.code(resp_hist["sql_query"], language="sql")

                    st.markdown("<br>", unsafe_allow_html=True)
        else:
            st.info("Aucune question posée pour le moment. Posez une question ci-dessus pour voir votre historique ici.")

    st.markdown('</div>', unsafe_allow_html=True)


if __name__ == "__main__":
    main()