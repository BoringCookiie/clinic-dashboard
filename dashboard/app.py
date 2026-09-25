"""
Clinique La Vallée - Main Streamlit Application.

Routing: each link in the header points to ?page=<name>. This file reads that
parameter and renders the matching page from dashboard/views/.
"""

import sys
from pathlib import Path

import streamlit as st

# Ensure project root is in sys.path for clean imports
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

st.set_page_config(page_title="Clinique La Vallée", layout="wide", initial_sidebar_state="collapsed")

from dashboard.views import home, patients, planning, doctors, billing, reports, admin  # noqa: E402
from dashboard.views.common import render_header  # noqa: E402

ROUTES = {
    "accueil": home.render,
    "patients": patients.render,
    "planning": planning.render,
    "medecins": doctors.render,
    "facturation": billing.render,
    "analyses": reports.render,
    "administration": admin.render,
}

# Load custom CSS
CSS_PATH = ROOT_DIR / "dashboard" / "static" / "style.css"
if CSS_PATH.exists():
    st.markdown(f"<style>{CSS_PATH.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)


def main():
    for key, default in [("chat_history", []), ("active_response", None), ("last_executed_query", None)]:
        st.session_state.setdefault(key, default)

    page = st.query_params.get("page", "accueil")
    if page not in ROUTES:
        page = "accueil"

    render_header(page)
    try:
        ROUTES[page]()
    except Exception as e:
        st.error(f"Impossible d'afficher cette page : {e}")
        st.info("Vérifiez que la base a été générée : python -m database.generate_data")


if __name__ == "__main__":
    main()
