"""Patients page: searchable patient list and a complete patient file."""

import pandas as pd
import streamlit as st

from dashboard.views.common import (
    flat_html,
    q, money, section, kpi_row, bar, donut, translate_values, status_style, STATUS_FR,
)

PATIENT_LIST_SQL = """
    SELECT p.patient_id AS id,
           p.last_name || ' ' || p.first_name AS nom,
           p.gender AS sexe,
           CAST((julianday((SELECT MAX(appointment_date) FROM appointments)) - julianday(p.date_of_birth)) / 365.25 AS INTEGER) AS age,
           p.blood_type AS groupe_sanguin,
           p.insurance_provider AS assurance,
           p.phone AS telephone,
           COUNT(v.visit_id) AS visites,
           MAX(v.visit_date) AS derniere_visite
    FROM patients p
    LEFT JOIN visits v ON v.patient_id = p.patient_id
    GROUP BY p.patient_id
    ORDER BY nom
"""


def _demographics(df: pd.DataFrame):
    c1, c2, c3 = st.columns(3)
    with c1:
        section("Répartition par âge")
        bins = [0, 18, 30, 45, 60, 75, 200]
        labels = ["0-17", "18-29", "30-44", "45-59", "60-74", "75+"]
        ages = pd.cut(df["age"], bins=bins, labels=labels, right=False).value_counts().reindex(labels)
        bar(pd.DataFrame({"tranche": labels, "patients": ages.fillna(0).astype(int).values}),
            "tranche", "patients", labels={"tranche": "Âge", "patients": "Patients"}, key="pat_age", height=300)
    with c2:
        section("Sexe")
        g = df["sexe"].map(lambda v: STATUS_FR.get(v, v)).value_counts().reset_index()
        g.columns = ["sexe", "patients"]
        donut(g, "sexe", "patients", key="pat_gender", height=300)
    with c3:
        section("Assurance")
        a = df["assurance"].fillna("Sans assurance").value_counts().reset_index()
        a.columns = ["assurance", "patients"]
        donut(a, "assurance", "patients", key="pat_ins", height=300)


def _patient_file(patient_id: int):
    info = q("SELECT * FROM patients WHERE patient_id = :id", {"id": patient_id}).iloc[0]
    totals = q("""
        SELECT COUNT(DISTINCT v.visit_id) AS visites,
               COALESCE(SUM(b.amount), 0) AS facture,
               COALESCE(SUM(CASE WHEN b.payment_status != 'paid' THEN b.amount END), 0) AS impaye,
               (SELECT COUNT(*) FROM appointments a WHERE a.patient_id = :id AND a.status = 'no-show') AS absences
        FROM visits v LEFT JOIN billing b ON b.visit_id = v.visit_id
        WHERE v.patient_id = :id
    """, {"id": patient_id}).iloc[0]

    c_info, c_kpi = st.columns([1, 2])
    with c_info:
        gender = STATUS_FR.get(info.gender, info.gender)
        st.markdown(flat_html(f"""
        <div class="profile-card">
            <div class="profile-name">{info.first_name} {info.last_name}</div>
            <div class="profile-sub">Dossier n° {info.patient_id} · Inscrit le {info.registration_date}</div>
            <div class="profile-row"><span>Sexe</span><span>{gender}</span></div>
            <div class="profile-row"><span>Date de naissance</span><span>{info.date_of_birth}</span></div>
            <div class="profile-row"><span>Groupe sanguin</span><span>{info.blood_type or '—'}</span></div>
            <div class="profile-row"><span>Assurance</span><span>{info.insurance_provider or '—'}</span></div>
            <div class="profile-row"><span>N° assurance</span><span>{info.insurance_number or '—'}</span></div>
            <div class="profile-row"><span>Téléphone</span><span>{info.phone or '—'}</span></div>
            <div class="profile-row"><span>Email</span><span>{info.email or '—'}</span></div>
            <div class="profile-row"><span>Adresse</span><span>{info.address or '—'}</span></div>
        </div>
        """), unsafe_allow_html=True)
    with c_kpi:
        kpi_row([
            ("Visites", str(int(totals.visites)), "Consultations effectuées"),
            ("Total facturé", money(totals.facture), "Toutes visites"),
            ("Reste à payer", money(totals.impaye), "En attente ou en retard"),
            ("Absences", str(int(totals.absences)), "Rendez-vous non honorés"),
        ])

        diag = q("""
            SELECT diag.diagnosis_name AS diagnostic, COUNT(*) AS fois
            FROM diagnoses diag JOIN visits v ON v.visit_id = diag.visit_id
            WHERE v.patient_id = :id GROUP BY diag.diagnosis_name ORDER BY fois DESC
        """, {"id": patient_id})
        if not diag.empty:
            badges = "".join(f'<span class="badge">{r.diagnostic} ({r.fois})</span>' for r in diag.itertuples())
            st.markdown(f"**Antécédents :** {badges}", unsafe_allow_html=True)

    t_visits, t_rx, t_lab, t_bill, t_appt = st.tabs(
        ["Visites & diagnostics", "Prescriptions", "Analyses de laboratoire", "Factures", "Rendez-vous"]
    )
    params = {"id": patient_id}
    with t_visits:
        df = q("""
            SELECT v.visit_date AS date, 'Dr ' || d.first_name || ' ' || d.last_name AS medecin,
                   dep.name AS departement, diag.diagnosis_code AS code_cim10,
                   diag.diagnosis_name AS diagnostic, diag.severity AS gravite,
                   v.symptoms AS symptomes, v.notes AS notes
            FROM visits v
            JOIN doctors d ON v.doctor_id = d.doctor_id
            JOIN departments dep ON d.department_id = dep.department_id
            LEFT JOIN diagnoses diag ON diag.visit_id = v.visit_id
            WHERE v.patient_id = :id ORDER BY v.visit_date DESC
        """, params)
        st.dataframe(df, use_container_width=True, hide_index=True)
    with t_rx:
        df = q("""
            SELECT v.visit_date AS date, m.name AS medicament, m.category AS categorie,
                   pr.dosage, pr.duration_days AS duree_jours, pr.instructions
            FROM prescriptions pr
            JOIN visits v ON pr.visit_id = v.visit_id
            JOIN medications m ON pr.medication_id = m.medication_id
            WHERE v.patient_id = :id ORDER BY v.visit_date DESC
        """, params)
        st.dataframe(df, use_container_width=True, hide_index=True)
    with t_lab:
        df = q("""
            SELECT l.test_date AS date, l.test_type AS analyse, l.result AS resultat, l.status AS statut
            FROM lab_tests l JOIN visits v ON l.visit_id = v.visit_id
            WHERE v.patient_id = :id ORDER BY l.test_date DESC
        """, params)
        df["statut"] = df["statut"].map({"pending": "En attente", "completed": "Terminé"}).fillna(df["statut"])
        st.dataframe(df, use_container_width=True, hide_index=True)
    with t_bill:
        df = q("""
            SELECT invoice_id AS facture, invoice_date AS date, amount AS montant,
                   insurance_covered_amount AS pris_en_charge, patient_paid_amount AS paye_patient,
                   payment_status AS statut
            FROM billing WHERE patient_id = :id ORDER BY invoice_date DESC
        """, params)
        df = translate_values(df, ["statut"])
        st.dataframe(status_style(df, "statut") if not df.empty else df, use_container_width=True, hide_index=True)
    with t_appt:
        df = q("""
            SELECT a.appointment_date AS date, substr(a.appointment_time, 1, 5) AS heure,
                   'Dr ' || d.first_name || ' ' || d.last_name AS medecin,
                   a.reason_for_visit AS motif, a.status AS statut
            FROM appointments a JOIN doctors d ON a.doctor_id = d.doctor_id
            WHERE a.patient_id = :id ORDER BY a.appointment_date DESC
        """, params)
        df = translate_values(df, ["statut"])
        st.dataframe(status_style(df, "statut") if not df.empty else df, use_container_width=True, hide_index=True)


def render():
    patients = q(PATIENT_LIST_SQL)

    section("Rechercher un patient")
    c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
    with c1:
        search = st.text_input("Nom ou numéro de dossier", placeholder="ex. : Martin ou 42")
    with c2:
        gender = st.selectbox("Sexe", ["Tous", "Homme", "Femme"])
    with c3:
        insurers = ["Toutes"] + sorted(patients["assurance"].dropna().unique().tolist())
        insurer = st.selectbox("Assurance", insurers)
    with c4:
        bloods = ["Tous"] + sorted(patients["groupe_sanguin"].dropna().unique().tolist())
        blood = st.selectbox("Groupe sanguin", bloods)

    df = patients.copy()
    if search.strip():
        s = search.strip().lower()
        df = df[df["nom"].str.lower().str.contains(s, regex=False) | (df["id"].astype(str) == s)]
    if gender != "Tous":
        df = df[df["sexe"] == {"Homme": "Male", "Femme": "Female"}[gender]]
    if insurer != "Toutes":
        df = df[df["assurance"] == insurer]
    if blood != "Tous":
        df = df[df["groupe_sanguin"] == blood]

    st.caption(f"{len(df)} patient(s) trouvé(s) sur {len(patients)}")
    st.dataframe(translate_values(df, ["sexe"]), use_container_width=True, hide_index=True, height=320)

    section("Dossier patient")
    if df.empty:
        st.info("Aucun patient ne correspond aux filtres.")
    else:
        options = {f"{r.nom} (n° {r.id})": int(r.id) for r in df.itertuples()}
        choice = st.selectbox("Sélectionnez un patient", list(options.keys()))
        _patient_file(options[choice])

    with st.expander("Statistiques démographiques", expanded=False):
        _demographics(patients)
