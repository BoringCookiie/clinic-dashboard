"""Planning page: appointments by day or week, filters, and no-show patterns."""

from datetime import date, timedelta

import pandas as pd
import plotly.express as px
import streamlit as st

from dashboard.views.common import (
    q, section, kpi_row, bar, translate_values, status_style, style_fig,
    STATUS_COLORS, STATUS_FR,
)

WEEKDAYS_FR = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]


def _no_show_heatmap():
    df = q("""
        SELECT CAST(strftime('%w', appointment_date) AS INTEGER) AS dow,
               CAST(substr(appointment_time, 1, 2) AS INTEGER) AS heure,
               ROUND(100.0 * SUM(status = 'no-show') / COUNT(*), 1) AS taux
        FROM appointments GROUP BY dow, heure
    """)
    if df.empty:
        return
    # SQLite: 0 = Sunday. Convert to Monday-first French labels.
    df["jour"] = df["dow"].map(lambda d: WEEKDAYS_FR[(d - 1) % 7])
    pivot = df.pivot(index="jour", columns="heure", values="taux")
    pivot = pivot.reindex([d for d in WEEKDAYS_FR if d in pivot.index])
    pivot.columns = [f"{h}h" for h in pivot.columns]
    fig = px.imshow(pivot, text_auto=".1f", aspect="auto", color_continuous_scale="YlOrRd",
                    labels=dict(x="Heure", y="", color="% absences"))
    st.plotly_chart(style_fig(fig, 330, legend=False), use_container_width=True, key="plan_heat")


def render():
    bounds = q("SELECT MIN(appointment_date) AS first, MAX(appointment_date) AS last FROM appointments").iloc[0]
    first, last = date.fromisoformat(bounds["first"]), date.fromisoformat(bounds["last"])

    departments = q("SELECT department_id, name FROM departments ORDER BY name")
    doctors = q("""
        SELECT d.doctor_id, 'Dr ' || d.first_name || ' ' || d.last_name AS name, dep.name AS department
        FROM doctors d JOIN departments dep ON d.department_id = dep.department_id ORDER BY d.last_name
    """)

    section("Filtres")
    c1, c2, c3, c4 = st.columns([1, 1, 1, 1])
    with c1:
        view = st.radio("Vue", ["Semaine", "Jour"], horizontal=True)
    with c2:
        default_day = last - timedelta(days=7) if view == "Semaine" else last
        chosen = st.date_input("Date", value=max(first, default_day), min_value=first, max_value=last,
                               format="DD/MM/YYYY")
    with c3:
        dep = st.selectbox("Département", ["Tous"] + departments["name"].tolist())
    with c4:
        doc_options = doctors if dep == "Tous" else doctors[doctors["department"] == dep]
        doc = st.selectbox("Médecin", ["Tous"] + doc_options["name"].tolist())

    if view == "Semaine":
        start = chosen - timedelta(days=chosen.weekday())
        end = start + timedelta(days=6)
        st.caption(f"Semaine du {start.strftime('%d/%m/%Y')} au {end.strftime('%d/%m/%Y')}")
    else:
        start = end = chosen
        st.caption(f"{WEEKDAYS_FR[chosen.weekday()]} {chosen.strftime('%d/%m/%Y')}")

    df = q("""
        SELECT a.appointment_date AS date, substr(a.appointment_time, 1, 5) AS heure,
               p.last_name || ' ' || p.first_name AS patient,
               'Dr ' || d.first_name || ' ' || d.last_name AS medecin,
               dep.name AS departement, a.reason_for_visit AS motif, a.status AS statut
        FROM appointments a
        JOIN patients p ON a.patient_id = p.patient_id
        JOIN doctors d ON a.doctor_id = d.doctor_id
        JOIN departments dep ON d.department_id = dep.department_id
        WHERE a.appointment_date BETWEEN :start AND :end
        ORDER BY a.appointment_date, a.appointment_time
    """, {"start": start.isoformat(), "end": end.isoformat()})
    if dep != "Tous":
        df = df[df["departement"] == dep]
    if doc != "Tous":
        df = df[df["medecin"] == doc]

    counts = df["statut"].value_counts()
    kpi_row([
        ("Rendez-vous", str(len(df)), "Sur la période"),
        ("Terminés", str(int(counts.get("completed", 0))), "Patients reçus"),
        ("Absences", str(int(counts.get("no-show", 0))), "Non honorés"),
        ("Annulés", str(int(counts.get("cancelled", 0))), "Annulations"),
    ])

    section("Rendez-vous")
    if df.empty:
        st.info("Aucun rendez-vous pour cette sélection. Les données vont jusqu'au "
                f"{last.strftime('%d/%m/%Y')}.")
    else:
        display = translate_values(df, ["statut"])
        st.dataframe(status_style(display, "statut"), use_container_width=True, hide_index=True, height=380)

        if view == "Semaine":
            per_day = df.groupby(["date", "statut"]).size().reset_index(name="rendez_vous")
            per_day["jour"] = per_day["date"].map(
                lambda d: f"{WEEKDAYS_FR[date.fromisoformat(d).weekday()][:3]} {d[8:10]}/{d[5:7]}")
            per_day = translate_values(per_day, ["statut"])
            bar(per_day, "jour", "rendez_vous", color="statut",
                labels={"jour": "", "rendez_vous": "Rendez-vous", "statut": ""},
                color_map={STATUS_FR[k]: v for k, v in STATUS_COLORS.items() if k in STATUS_FR},
                key="plan_week", height=320)

    section("Quand les patients manquent-ils leurs rendez-vous ?")
    st.caption("Taux d'absence (%) par jour de la semaine et par heure, sur toute la période.")
    _no_show_heatmap()
