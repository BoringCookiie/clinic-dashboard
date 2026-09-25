"""Médecins page: doctor cards with activity, workload and performance."""

import streamlit as st

from dashboard.views.common import flat_html, q, money, section, kpi_row, bar, line, LAST_FULL_MONTH_FILTER

DOCTOR_STATS_SQL = """
    SELECT d.doctor_id,
           'Dr ' || d.first_name || ' ' || d.last_name AS medecin,
           d.specialty AS specialite, dep.name AS departement, d.hire_date AS embauche,
           d.phone AS telephone, d.email,
           COUNT(a.appointment_id) AS rendez_vous,
           SUM(a.status = 'completed') AS termines,
           ROUND(100.0 * SUM(a.status = 'no-show') / NULLIF(COUNT(a.appointment_id), 0), 1) AS taux_absence,
           COUNT(DISTINCT a.patient_id) AS patients,
           (SELECT ROUND(SUM(b.amount), 2) FROM billing b JOIN visits v ON b.visit_id = v.visit_id
             WHERE v.doctor_id = d.doctor_id) AS chiffre_affaires
    FROM doctors d
    JOIN departments dep ON d.department_id = dep.department_id
    LEFT JOIN appointments a ON a.doctor_id = d.doctor_id
    GROUP BY d.doctor_id
    ORDER BY dep.name, d.last_name
"""


def _card(r) -> str:
    return f"""
    <div class="profile-card">
        <div class="profile-name">{r.medecin}</div>
        <div class="profile-sub">{r.specialite} · {r.departement}</div>
        <div class="profile-row"><span>Patients suivis</span><span>{int(r.patients)}</span></div>
        <div class="profile-row"><span>Consultations terminées</span><span>{int(r.termines or 0)}</span></div>
        <div class="profile-row"><span>Taux d'absence</span><span>{r.taux_absence}%</span></div>
        <div class="profile-row"><span>Chiffre d'affaires</span><span>{money(r.chiffre_affaires)}</span></div>
        <div class="profile-row"><span>En poste depuis</span><span>{r.embauche}</span></div>
    </div>
    """


def render():
    stats = q(DOCTOR_STATS_SQL)

    c1, c2 = st.columns([1, 1])
    with c1:
        dep = st.selectbox("Département", ["Tous"] + sorted(stats["departement"].unique().tolist()))
    with c2:
        sort = st.selectbox("Trier par", ["Département", "Consultations", "Chiffre d'affaires", "Taux d'absence"])

    df = stats if dep == "Tous" else stats[stats["departement"] == dep]
    sort_col = {"Consultations": "termines", "Chiffre d'affaires": "chiffre_affaires",
                "Taux d'absence": "taux_absence"}.get(sort)
    if sort_col:
        df = df.sort_values(sort_col, ascending=False)

    kpi_row([
        ("Médecins", str(len(df)), dep if dep != "Tous" else "Tous départements"),
        ("Consultations", f"{int(df['termines'].sum()):,}", "Terminées"),
        ("Taux d'absence moyen", f"{df['taux_absence'].mean():.1f}%", "Moyenne des médecins"),
        ("Chiffre d'affaires", money(df["chiffre_affaires"].sum()), "Facturé"),
    ])

    section("L'équipe")
    cols = st.columns(3)
    for i, r in enumerate(df.itertuples()):
        with cols[i % 3]:
            st.markdown(flat_html(_card(r)), unsafe_allow_html=True)

    c3, c4 = st.columns(2)
    with c3:
        section("Charge de travail (consultations terminées)")
        bar(df, "medecin", "termines", labels={"medecin": "", "termines": "Consultations"},
            horizontal=True, key="doc_load", height=max(300, 32 * len(df)))
    with c4:
        section("Taux d'absence par médecin (%)")
        bar(df, "medecin", "taux_absence", labels={"medecin": "", "taux_absence": "% absences"},
            horizontal=True, key="doc_noshow", height=max(300, 32 * len(df)))

    section("Activité mensuelle")
    choice = st.selectbox("Médecin", df["medecin"].tolist(), key="doc_month_select")
    doctor_id = int(df.loc[df["medecin"] == choice, "doctor_id"].iloc[0])
    monthly = q(f"""
        SELECT strftime('%Y-%m', appointment_date) AS mois, COUNT(*) AS rendez_vous
        FROM appointments WHERE doctor_id = :id AND {LAST_FULL_MONTH_FILTER}
        GROUP BY mois ORDER BY mois
    """, {"id": doctor_id})
    line(monthly, "mois", "rendez_vous", labels={"mois": "Mois", "rendez_vous": "Rendez-vous"},
         key="doc_monthly", height=300)

    with st.expander("Coordonnées des médecins"):
        st.dataframe(df[["medecin", "specialite", "departement", "telephone", "email"]],
                     use_container_width=True, hide_index=True)
