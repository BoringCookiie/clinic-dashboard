"""
Shared layout pieces and helpers used by every page:
navigation header, hero / page banner, cached queries, chart styling, KPI rows.
"""

import base64
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from database.db_utils import run_raw_query
from dashboard.components.kpi_cards import render_kpi_card

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
STATIC_DIR = ROOT_DIR / "dashboard" / "static"

COLOR_PALETTE = ["#3f51b5", "#38bdf8", "#34d399", "#fbbf24", "#f43f5e", "#a78bfa", "#f472b6", "#818cf8"]
STATUS_COLORS = {
    "completed": "#34d399", "no-show": "#f43f5e", "cancelled": "#fbbf24", "scheduled": "#38bdf8",
    "paid": "#34d399", "pending": "#fbbf24", "overdue": "#f43f5e",
}
STATUS_FR = {
    "completed": "Terminé", "no-show": "Absent", "cancelled": "Annulé", "scheduled": "Planifié",
    "paid": "Payée", "pending": "En attente", "overdue": "En retard",
    "card": "Carte", "cash": "Espèces", "insurance": "Assurance",
    "Male": "Homme", "Female": "Femme",
}

# page key -> (menu label, banner title, banner description)
PAGES = {
    "accueil": ("Tableau de Bord", None, None),
    "patients": ("Patients", "Gestion des Patients",
                 "Recherchez un patient et consultez son dossier médical complet."),
    "planning": ("Planning", "Planning des Consultations",
                 "Rendez-vous par jour ou par semaine, par médecin et par département."),
    "medecins": ("Médecins", "Équipe Médicale",
                 "Activité, charge de travail et performance de chaque médecin."),
    "facturation": ("Facturation", "Facturation & Paiements",
                    "Suivi du chiffre d'affaires, des encaissements et des impayés."),
    "analyses": ("Analyses", "Analyses & Rapports",
                 "Rapport mensuel complet, résumé par l'IA et export Excel."),
    "administration": ("Administration", "Administration",
                       "Départements, personnel, fournisseurs, médicaments et état du système."),
}
MENU_PAGES = ["accueil", "patients", "planning", "medecins", "facturation"]


# ------------------------------------------------------------------------------
# Data helpers
# ------------------------------------------------------------------------------
@st.cache_data(ttl=600, show_spinner=False)
def q(sql: str, params: dict | None = None) -> pd.DataFrame:
    """Runs a read query with caching (results refresh every 10 minutes)."""
    return run_raw_query(sql, params)


def money(value) -> str:
    try:
        return f"${float(value or 0):,.2f}"
    except (TypeError, ValueError):
        return "$0.00"


def translate_values(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """Translates status / method / gender values to French for display."""
    df = df.copy()
    for col in columns:
        if col in df.columns:
            df[col] = df[col].map(lambda v: STATUS_FR.get(v, v))
    return df


# ------------------------------------------------------------------------------
# Layout
# ------------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def _b64(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()


def _link(page: str, label: str, css_class: str = "") -> str:
    return f'<a href="?page={page}" target="_self" class="{css_class}">{label}</a>'


def render_header(current: str) -> None:
    """Top navigation bar, then the full hero (home) or a compact banner (other pages)."""
    bg_path, logo_path = STATIC_DIR / "background.jpg", STATIC_DIR / "logo.png"
    bg_url = f"data:image/jpeg;base64,{_b64(str(bg_path))}" if bg_path.exists() else ""
    logo = (f'<img src="data:image/png;base64,{_b64(str(logo_path))}" alt="Clinique La Vallée">'
            if logo_path.exists() else "Clinique La Vallée")

    links = "".join(
        _link(key, PAGES[key][0], "active" if key == current else "") for key in MENU_PAGES
    )
    nav = f"""
    <div class="custom-nav-container">
        <a class="logo-overlay" href="?page=accueil" target="_self">{logo}</a>
        <div class="custom-nav">
            <div class="nav-links">
                {links}
                {_link("administration", "ADMINISTRATION", "nav-btn")}
            </div>
        </div>
    </div>
    """

    if current == "accueil":
        top = f"""
        <div class="hero-section" style="background-image: url('{bg_url}');">
            <div class="hero-overlay"></div>
            <div class="hero-content">
                <div class="hero-subtitle">Portail du Personnel</div>
                <div class="hero-title">Système de Gestion</div>
                <div class="hero-desc">Accédez aux dossiers médicaux, gérez le planning des consultations, et suivez les indicateurs clés de performance de la clinique en temps réel.</div>
                <div class="hero-avail"><strong>Statut du système :</strong> En ligne</div>
                {_link("analyses", "AFFICHER LES STATISTIQUES", "hero-btn")}
            </div>
        </div>
        <div class="info-bar">
            {_link("patients", "Gestion des Patients", "info-item")}
            {_link("analyses", "Analyses &amp; Rapports", "info-item")}
            {_link("administration", "Administration", "info-item")}
        </div>
        """
    else:
        _, title, desc = PAGES[current]
        top = f"""
        <div class="page-banner" style="background-image: url('{bg_url}');">
            <div class="hero-overlay"></div>
            <div class="page-banner-content">
                <div class="hero-subtitle">Clinique La Vallée</div>
                <div class="page-banner-title">{title}</div>
                <div class="page-banner-desc">{desc}</div>
            </div>
        </div>
        """
    st.markdown(flat_html(nav + top), unsafe_allow_html=True)


def flat_html(html: str) -> str:
    """Removes indentation and blank lines so Markdown never treats HTML as a code block."""
    return "\n".join(line.strip() for line in html.splitlines() if line.strip())


def section(title: str) -> None:
    st.markdown(f'<div class="section-title">{title}</div>', unsafe_allow_html=True)


def kpi_row(metrics: list[tuple[str, str, str]]) -> None:
    """metrics = [(title, value, subtitle), ...]"""
    cols = st.columns(len(metrics))
    for col, (title, value, subtitle) in zip(cols, metrics):
        with col:
            render_kpi_card(title, value, subtitle)


# ------------------------------------------------------------------------------
# Charts
# ------------------------------------------------------------------------------
def style_fig(fig, height: int = 360, legend: bool = True):
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, sans-serif", color="#333333"),
        margin=dict(l=10, r=10, t=30, b=10),
        height=height,
        showlegend=legend,
        legend_title_text="",
    )
    return fig


def bar(df, x, y, labels=None, key=None, color=None, horizontal=False, height=360, color_map=None):
    if df.empty:
        st.info("Aucune donnée pour cette sélection.")
        return
    kwargs = dict(x=y, y=x, orientation="h") if horizontal else dict(x=x, y=y)
    fig = px.bar(df, **kwargs, color=color, labels=labels or {}, text_auto=True,
                 color_discrete_sequence=COLOR_PALETTE, color_discrete_map=color_map or {},
                 template="plotly_white")
    if horizontal:
        fig.update_yaxes(categoryorder="total ascending")
    st.plotly_chart(style_fig(fig, height, legend=color is not None), use_container_width=True, key=key)


def line(df, x, y, labels=None, key=None, color=None, height=360):
    if df.empty:
        st.info("Aucune donnée pour cette sélection.")
        return
    fig = px.line(df, x=x, y=y, color=color, markers=True, labels=labels or {},
                  color_discrete_sequence=COLOR_PALETTE, template="plotly_white")
    fig.update_traces(line=dict(width=3), marker=dict(size=7))
    st.plotly_chart(style_fig(fig, height, legend=color is not None), use_container_width=True, key=key)


def donut(df, names, values, key=None, height=360, color_map=None):
    if df.empty:
        st.info("Aucune donnée pour cette sélection.")
        return
    fig = px.pie(df, names=names, values=values, hole=0.45,
                 color=names if color_map else None, color_discrete_map=color_map or {},
                 color_discrete_sequence=COLOR_PALETTE, template="plotly_white")
    st.plotly_chart(style_fig(fig, height), use_container_width=True, key=key)


def status_style(df: pd.DataFrame, column: str):
    """Colors a status column in a dataframe (works on French or English values)."""
    reverse = {v: k for k, v in STATUS_FR.items()}

    def color(value):
        c = STATUS_COLORS.get(reverse.get(value, value))
        return f"background-color: {c}33; color: #222; font-weight: 600" if c else ""

    styler = df.style
    apply = getattr(styler, "map", None) or styler.applymap  # pandas < 2.1 uses applymap
    return apply(color, subset=[column])


# Last complete month in the data: the final month is partial, so charts stop before it
LAST_FULL_MONTH_FILTER = (
    "appointment_date < date((SELECT MAX(appointment_date) FROM appointments), 'start of month')"
)
