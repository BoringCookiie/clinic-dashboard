"""Analyses & Rapports: monthly report with comparison, AI-written summary and Excel export."""

from io import BytesIO

import pandas as pd
import streamlit as st

from chatbot.ollama_chatbot import ask_model
from dashboard.views.common import flat_html, q, money, section, kpi_row, bar, donut, translate_values

MONTHS_FR = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet",
             "août", "septembre", "octobre", "novembre", "décembre"]


def _month_label(m: str) -> str:
    year, month = m.split("-")
    return f"{MONTHS_FR[int(month) - 1].capitalize()} {year}"


def _month_metrics(month: str) -> dict:
    p = {"m": month}
    a = q("""
        SELECT COUNT(*) AS total, SUM(status = 'completed') AS done,
               SUM(status = 'no-show') AS no_show, SUM(status = 'cancelled') AS cancelled,
               COUNT(DISTINCT patient_id) AS patients
        FROM appointments WHERE strftime('%Y-%m', appointment_date) = :m
    """, p).iloc[0]
    b = q("""
        SELECT COALESCE(SUM(amount), 0) AS billed,
               COALESCE(SUM(CASE WHEN payment_status != 'paid' THEN amount END), 0) AS unpaid
        FROM billing WHERE strftime('%Y-%m', invoice_date) = :m
    """, p).iloc[0]
    paid = q("SELECT COALESCE(SUM(amount_paid), 0) AS v FROM payments WHERE strftime('%Y-%m', payment_date) = :m",
             p).iloc[0]["v"]
    new_patients = q("SELECT COUNT(*) AS v FROM patients WHERE strftime('%Y-%m', registration_date) = :m",
                     p).iloc[0]["v"]
    total = int(a.total or 0)
    return {
        "rendez_vous": total,
        "consultations": int(a.done or 0),
        "taux_absence": round(100 * (a.no_show or 0) / total, 1) if total else 0.0,
        "annulations": int(a.cancelled or 0),
        "patients_vus": int(a.patients or 0),
        "nouveaux_patients": int(new_patients),
        "facture": round(float(b.billed), 2),
        "encaisse": round(float(paid), 2),
        "impayes": round(float(b.unpaid), 2),
    }


def _delta(cur, prev, pct=False) -> str:
    if prev in (None, 0):
        return "—"
    if pct:
        diff = cur - prev
        return f"{'+' if diff >= 0 else ''}{diff:.1f} pts vs mois précédent"
    change = 100 * (cur - prev) / prev
    return f"{'+' if change >= 0 else ''}{change:.1f}% vs mois précédent"


def _details(month: str) -> dict[str, pd.DataFrame]:
    p = {"m": month}
    return {
        "Par département": q("""
            SELECT dep.name AS departement, COUNT(*) AS rendez_vous,
                   SUM(a.status = 'completed') AS consultations,
                   ROUND(100.0 * SUM(a.status = 'no-show') / COUNT(*), 1) AS taux_absence
            FROM appointments a JOIN doctors d ON a.doctor_id = d.doctor_id
            JOIN departments dep ON d.department_id = dep.department_id
            WHERE strftime('%Y-%m', a.appointment_date) = :m
            GROUP BY dep.name ORDER BY rendez_vous DESC
        """, p),
        "Diagnostics": q("""
            SELECT diag.diagnosis_name AS diagnostic, COUNT(*) AS cas
            FROM diagnoses diag JOIN visits v ON diag.visit_id = v.visit_id
            WHERE strftime('%Y-%m', v.visit_date) = :m
            GROUP BY diag.diagnosis_name ORDER BY cas DESC
        """, p),
        "Médicaments": q("""
            SELECT m.name AS medicament, COUNT(*) AS prescriptions
            FROM prescriptions pr JOIN visits v ON pr.visit_id = v.visit_id
            JOIN medications m ON pr.medication_id = m.medication_id
            WHERE strftime('%Y-%m', v.visit_date) = :m
            GROUP BY m.name ORDER BY prescriptions DESC
        """, p),
        "Médecins": q("""
            SELECT 'Dr ' || d.first_name || ' ' || d.last_name AS medecin,
                   SUM(a.status = 'completed') AS consultations, SUM(a.status = 'no-show') AS absences
            FROM appointments a JOIN doctors d ON a.doctor_id = d.doctor_id
            WHERE strftime('%Y-%m', a.appointment_date) = :m
            GROUP BY d.doctor_id ORDER BY consultations DESC
        """, p),
        "Paiements": translate_values(q("""
            SELECT payment_method AS moyen, COUNT(*) AS paiements, ROUND(SUM(amount_paid), 2) AS montant
            FROM payments WHERE strftime('%Y-%m', payment_date) = :m GROUP BY moyen
        """, p), ["moyen"]),
    }


def _excel(month: str, cur: dict, prev: dict, details: dict[str, pd.DataFrame], summary: str | None) -> bytes:
    labels = {
        "rendez_vous": "Rendez-vous", "consultations": "Consultations terminées",
        "taux_absence": "Taux d'absence (%)", "annulations": "Annulations",
        "patients_vus": "Patients vus", "nouveaux_patients": "Nouveaux patients",
        "facture": "Montant facturé ($)", "encaisse": "Montant encaissé ($)", "impayes": "Impayés ($)",
    }
    summary_df = pd.DataFrame({
        "Indicateur": [labels[k] for k in cur],
        _month_label(month): list(cur.values()),
        "Mois précédent": [prev.get(k) for k in cur] if prev else [None] * len(cur),
    })
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        summary_df.to_excel(writer, sheet_name="Synthèse", index=False)
        if summary:
            pd.DataFrame({"Résumé IA": [summary]}).to_excel(writer, sheet_name="Résumé IA", index=False)
        for name, df in details.items():
            df.to_excel(writer, sheet_name=name[:31], index=False)
        for sheet in writer.sheets.values():
            for column in sheet.columns:
                width = max(len(str(c.value or "")) for c in column)
                sheet.column_dimensions[column[0].column_letter].width = min(max(12, width + 2), 60)
    return buffer.getvalue()


def _ai_summary(month: str, cur: dict, prev: dict, details: dict[str, pd.DataFrame]) -> str:
    context = [f"Mois : {_month_label(month)}", f"Indicateurs du mois : {cur}"]
    if prev:
        context.append(f"Indicateurs du mois précédent : {prev}")
    for name in ["Par département", "Diagnostics", "Médecins"]:
        context.append(f"{name} :\n{details[name].head(6).to_string(index=False)}")
    return ask_model(
        system=(
            "Tu es l'analyste de la Clinique La Vallée. Rédige en français un résumé mensuel de "
            "5 à 7 phrases pour la direction : activité, absences, diagnostics principaux, finances, "
            "comparaison avec le mois précédent, et une recommandation concrète. "
            "Utilise uniquement les chiffres fournis. Pas de titres, pas de listes."
        ),
        user="\n\n".join(context),
    )


def render():
    months = q("""
        SELECT DISTINCT strftime('%Y-%m', appointment_date) AS m FROM appointments
        WHERE appointment_date < date((SELECT MAX(appointment_date) FROM appointments), 'start of month')
        ORDER BY m DESC
    """)["m"].tolist()
    if not months:
        st.info("Pas encore de données.")
        return

    c1, _ = st.columns([1, 2])
    with c1:
        month = st.selectbox("Mois du rapport", months, format_func=_month_label)
    idx = months.index(month)
    prev_month = months[idx + 1] if idx + 1 < len(months) else None

    cur = _month_metrics(month)
    prev = _month_metrics(prev_month) if prev_month else {}
    details = _details(month)

    section(f"Synthèse — {_month_label(month)}")
    kpi_row([
        ("Rendez-vous", str(cur["rendez_vous"]), _delta(cur["rendez_vous"], prev.get("rendez_vous"))),
        ("Consultations", str(cur["consultations"]), _delta(cur["consultations"], prev.get("consultations"))),
        ("Taux d'absence", f"{cur['taux_absence']}%", _delta(cur["taux_absence"], prev.get("taux_absence"), pct=True)),
        ("Nouveaux patients", str(cur["nouveaux_patients"]), _delta(cur["nouveaux_patients"], prev.get("nouveaux_patients"))),
        ("Facturé", money(cur["facture"]), _delta(cur["facture"], prev.get("facture"))),
        ("Encaissé", money(cur["encaisse"]), _delta(cur["encaisse"], prev.get("encaisse"))),
    ])

    section("Résumé rédigé par l'IA")
    summary_key = f"ai_summary_{month}"
    if st.button("Générer le résumé avec l'IA locale", type="primary", key=f"btn_{summary_key}"):
        with st.spinner("Rédaction du résumé par le modèle local..."):
            try:
                st.session_state[summary_key] = _ai_summary(month, cur, prev, details)
            except Exception:
                st.error("Le modèle local ne répond pas. Vérifiez qu'Ollama est lancé.")
    summary = st.session_state.get(summary_key)
    if summary:
        st.markdown(flat_html(f'<div class="ai-summary">{summary.replace(chr(10), "<br>")}</div>'), unsafe_allow_html=True)
    else:
        st.caption("Le modèle Qwen tourne sur cette machine : aucune donnée ne quitte la clinique.")

    c2, c3 = st.columns(2)
    with c2:
        section("Rendez-vous par département")
        bar(details["Par département"], "departement", "rendez_vous",
            labels={"departement": "", "rendez_vous": "Rendez-vous"}, key="rep_dep", height=320)
    with c3:
        section("Diagnostics du mois")
        bar(details["Diagnostics"].head(7), "diagnostic", "cas",
            labels={"diagnostic": "", "cas": "Cas"}, horizontal=True, key="rep_diag", height=320)

    c4, c5 = st.columns(2)
    with c4:
        section("Médicaments prescrits")
        st.dataframe(details["Médicaments"], use_container_width=True, hide_index=True, height=300)
    with c5:
        section("Encaissements par moyen de paiement")
        donut(details["Paiements"], "moyen", "montant", key="rep_pay", height=300)

    section("Export")
    st.download_button(
        "Télécharger le rapport Excel",
        data=_excel(month, cur, prev, details, summary),
        file_name=f"rapport_clinique_{month}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary",
    )
