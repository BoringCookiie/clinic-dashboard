"""Home page (Tableau de Bord): KPIs, AI search assistant, overview charts."""

import streamlit as st

from chatbot.ollama_chatbot import get_answer
from chatbot.interface import ChatbotResponse
from dashboard.components.charts import render_chart_response
from dashboard.views.common import (
    flat_html,
    q, money, section, kpi_row, bar, line, donut, translate_values,
    STATUS_COLORS, STATUS_FR, LAST_FULL_MONTH_FILTER,
)

SAMPLE_QUESTIONS = [
    "Combien de patients sont inscrits ?",
    "Rendez-vous par mois",
    "Quels sont les 5 diagnostics les plus fréquents ?",
    "Chiffre d'affaires par département",
    "Médicaments les plus prescrits",
    "Taux d'absence par médecin",
    "Factures en retard par assurance",
]


def _kpis():
    k = q("""
        SELECT
          (SELECT COUNT(*) FROM patients) AS patients,
          (SELECT COUNT(*) FROM appointments WHERE status = 'completed') AS completed,
          (SELECT ROUND(100.0 * SUM(status = 'no-show') / COUNT(*), 1) FROM appointments) AS no_show_rate,
          (SELECT SUM(amount_paid) FROM payments) AS collected,
          (SELECT SUM(amount) FROM billing WHERE payment_status IN ('pending', 'overdue')) AS unpaid,
          (SELECT COUNT(*) FROM doctors) AS doctors,
          (SELECT COUNT(*) FROM departments) AS departments
    """).iloc[0]
    kpi_row([
        ("Patients", f"{int(k.patients):,}", "Inscrits dans la base"),
        ("Consultations", f"{int(k.completed):,}", "Rendez-vous terminés"),
        ("Taux d'absence", f"{k.no_show_rate}%", "Rendez-vous non honorés"),
        ("Encaissé", money(k.collected), "Paiements reçus"),
        ("Impayés", money(k.unpaid), "En attente ou en retard"),
        ("Médecins", str(int(k.doctors)), f"Répartis sur {int(k.departments)} départements"),
    ])


def _assistant():
    section("Assistant de Recherche IA")
    st.markdown("**Questions fréquentes (cliquez pour lancer la recherche) :**")

    clicked = None
    cols = st.columns(4)
    for i, sample in enumerate(SAMPLE_QUESTIONS):
        with cols[i % 4]:
            if st.button(sample, key=f"chip_{i}", use_container_width=True):
                clicked = sample

    c_input, c_btn = st.columns([5, 1])
    with c_input:
        typed = st.text_input(
            "Posez une question sur les patients, rendez-vous, diagnostics, factures ou médecins :",
            placeholder="ex. : Quel département a le plus de rendez-vous en 2025 ?",
            key="user_query_input_text",
        )
    with c_btn:
        st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
        submitted = st.button("Rechercher", key="ask_btn", use_container_width=True, type="primary")

    question = clicked or (typed.strip() if submitted and typed and typed.strip() else None)
    if question and question != st.session_state.get("last_executed_query"):
        with st.spinner(f"Analyse en cours : « {question} »..."):
            response: ChatbotResponse = get_answer(question)
        item = {"question": question, "response": response}
        st.session_state["active_response"] = item
        st.session_state["last_executed_query"] = question
        st.session_state["chat_history"].insert(0, item)

    item = st.session_state.get("active_response")
    if item:
        _render_answer(item, key="active")


def _render_answer(item, key: str, expanded_sql: bool = True):
    resp: ChatbotResponse = item["response"]
    st.markdown(flat_html(
        f"""
        <div class="qa-card">
            <div class="qa-question-header">Question : « {item['question']} »</div>
            <div class="qa-answer-text">{resp['answer_text']}</div>
        </div>
        """),
        unsafe_allow_html=True,
    )
    if resp.get("error"):
        st.warning(resp["error"])
    if resp.get("chart_type") and resp["chart_type"] != "none":
        render_chart_response(resp["chart_type"], resp.get("data", []), resp.get("columns"), key=f"chart_{key}")
    if resp.get("sql_query"):
        with st.expander("Voir la requête SQL générée", expanded=expanded_sql):
            st.code(resp["sql_query"], language="sql")


def _overview():
    c1, c2 = st.columns(2)
    with c1:
        section("Tendance mensuelle des rendez-vous")
        df = q(f"""
            SELECT strftime('%Y-%m', appointment_date) AS mois, COUNT(*) AS rendez_vous
            FROM appointments WHERE {LAST_FULL_MONTH_FILTER}
            GROUP BY mois ORDER BY mois
        """)
        line(df, "mois", "rendez_vous", labels={"mois": "Mois", "rendez_vous": "Rendez-vous"}, key="home_trend")
    with c2:
        section("Diagnostics les plus fréquents")
        df = q("""
            SELECT diagnosis_name AS diagnostic, COUNT(*) AS cas
            FROM diagnoses GROUP BY diagnosis_name ORDER BY cas DESC LIMIT 7
        """)
        bar(df, "diagnostic", "cas", labels={"diagnostic": "", "cas": "Nombre de cas"},
            horizontal=True, key="home_diag")

    c3, c4 = st.columns(2)
    with c3:
        section("Statut des factures")
        df = q("SELECT payment_status AS statut, ROUND(SUM(amount), 2) AS montant FROM billing GROUP BY statut")
        df = translate_values(df, ["statut"])
        donut(df, "statut", "montant", key="home_billing",
              color_map={STATUS_FR[k]: v for k, v in STATUS_COLORS.items() if k in STATUS_FR})
    with c4:
        section("Chiffre d'affaires par département")
        df = q("""
            SELECT dep.name AS departement, ROUND(SUM(b.amount), 2) AS chiffre_affaires
            FROM billing b
            JOIN visits v ON b.visit_id = v.visit_id
            JOIN doctors d ON v.doctor_id = d.doctor_id
            JOIN departments dep ON d.department_id = dep.department_id
            GROUP BY dep.name ORDER BY chiffre_affaires DESC
        """)
        bar(df, "departement", "chiffre_affaires",
            labels={"departement": "", "chiffre_affaires": "Montant facturé ($)"}, key="home_rev_dept")

    section("Visites récentes")
    df = q("""
        SELECT v.visit_date AS date, p.first_name || ' ' || p.last_name AS patient,
               'Dr ' || d.first_name || ' ' || d.last_name AS medecin,
               dep.name AS departement, diag.diagnosis_name AS diagnostic
        FROM visits v
        JOIN patients p ON v.patient_id = p.patient_id
        JOIN doctors d ON v.doctor_id = d.doctor_id
        JOIN departments dep ON d.department_id = dep.department_id
        LEFT JOIN diagnoses diag ON v.visit_id = diag.visit_id
        ORDER BY v.visit_date DESC LIMIT 10
    """)
    st.dataframe(df, use_container_width=True, hide_index=True)


def _history():
    history = st.session_state["chat_history"]
    if not history:
        st.info("Aucune question posée pour le moment.")
        return
    c1, c2 = st.columns([4, 1])
    with c1:
        st.markdown(f"**{len(history)} question(s) posée(s)**")
    with c2:
        if st.button("Effacer l'historique", key="clear_hist"):
            st.session_state["chat_history"] = []
            st.session_state["active_response"] = None
            st.session_state["last_executed_query"] = None
            st.rerun()
    for i, item in enumerate(history):
        _render_answer(item, key=f"hist_{i}", expanded_sql=False)


def render():
    _kpis()
    _assistant()
    st.markdown("<br>", unsafe_allow_html=True)
    tab_overview, tab_history = st.tabs(["Vue d'ensemble", "Historique des questions"])
    with tab_overview:
        _overview()
    with tab_history:
        _history()
