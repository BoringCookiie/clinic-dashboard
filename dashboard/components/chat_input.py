"""
Chatbot Question Input and History UI Component.
"""

from typing import Callable
import streamlit as st
from chatbot.interface import ChatbotResponse
from dashboard.components.charts import render_chart_response


SAMPLE_QUESTIONS = [
    "How many patients are registered?",
    "Show appointments by month",
    "What are the top diagnoses?",
    "What is our revenue status?",
    "Show doctors by department",
    "Show pending invoices"
]


def render_chat_interface(get_answer_fn: Callable[[str], ChatbotResponse]) -> None:
    """
    Renders the natural language chatbot interface, handles question submissions,
    maintains chat history in session state, and displays dynamic answer cards.
    """
    # Initialize chat history in session state if not present
    if "chat_history" not in st.session_state:
        st.session_state["chat_history"] = []

    st.markdown('<div class="section-header">💬 Ask the Smart Clinic Assistant</div>', unsafe_allow_html=True)
    st.markdown("Ask natural language questions about patients, appointments, diagnoses, doctors, or clinic revenue.")

    # Render Sample Question Chips
    st.markdown("**💡 Sample Questions to Try:**")
    cols = st.columns(len(SAMPLE_QUESTIONS))
    chip_clicked_question = None

    for i, sample in enumerate(SAMPLE_QUESTIONS):
        with cols[i % len(cols)]:
            if st.button(sample, key=f"chip_{i}", use_container_width=True):
                chip_clicked_question = sample

    # Question Input Form
    with st.form(key="chat_form", clear_on_submit=True):
        user_input = st.text_input(
            "Enter your question:",
            placeholder="e.g. How many patients are registered in the clinic?",
            key="user_question_input"
        )
        submit_btn = st.form_submit_button("Ask Question 🚀", use_container_width=True)

    # Determine question to submit (from input form or chip click)
    question_to_process = chip_clicked_question or (user_input.strip() if submit_btn and user_input else None)

    if question_to_process:
        with st.spinner("Analyzing question & querying database..."):
            response: ChatbotResponse = get_answer_fn(question_to_process)
            # Add to history at top (prepend)
            st.session_state["chat_history"].insert(0, {
                "question": question_to_process,
                "response": response
            })

    # Render Chat History Cards
    if st.session_state["chat_history"]:
        st.markdown("<hr style='border-color: rgba(255,255,255,0.1); margin: 25px 0;'>", unsafe_allow_html=True)
        
        c1, c2 = st.columns([4, 1])
        with c1:
            st.markdown(f"### Question & Answer History ({len(st.session_state['chat_history'])})")
        with c2:
            if st.button("Clear History 🗑️", key="clear_chat"):
                st.session_state["chat_history"] = []
                st.rerun()

        for idx, item in enumerate(st.session_state["chat_history"]):
            q = item["question"]
            resp: ChatbotResponse = item["response"]

            with st.container():
                st.markdown(
                    f"""
                    <div class="qa-card">
                        <div class="qa-question-header">❓ {q}</div>
                        <div class="qa-answer-text">{resp['answer_text']}</div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

                # Render Error if present
                if resp.get("error"):
                    st.error(f"Error: {resp['error']}")

                # Render Chart / Visual Component
                if resp.get("chart_type") and resp["chart_type"] != "none":
                    render_chart_response(
                        chart_type=resp["chart_type"],
                        data=resp.get("data", []),
                        columns=resp.get("columns")
                    )

                # Render Collapsible SQL Query Section
                if resp.get("sql_query"):
                    with st.expander("🔍 How I got this answer (SQL Query)", expanded=False):
                        st.code(resp["sql_query"], language="sql")

                st.markdown("<br>", unsafe_allow_html=True)
