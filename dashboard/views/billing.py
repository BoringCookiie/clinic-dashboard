"""Facturation page: revenue, payments, insurance coverage and overdue invoices."""

import pandas as pd
import streamlit as st

from dashboard.views.common import (
    q, money, section, kpi_row, bar, line, donut, translate_values, status_style,
    STATUS_COLORS, STATUS_FR,
)

STATUS_MAP = {STATUS_FR[k]: v for k, v in STATUS_COLORS.items() if k in STATUS_FR}


def render():
    k = q("""
        SELECT SUM(amount) AS billed,
               SUM(insurance_covered_amount) AS insurance,
               (SELECT SUM(amount_paid) FROM payments) AS collected,
               SUM(CASE WHEN payment_status = 'pending' THEN amount END) AS pending,
               SUM(CASE WHEN payment_status = 'overdue' THEN amount END) AS overdue,
               SUM(payment_status = 'overdue') AS overdue_count
        FROM billing
    """).iloc[0]
    coverage = 100 * (k.insurance or 0) / k.billed if k.billed else 0
    kpi_row([
        ("Total facturé", money(k.billed), "Toutes factures"),
        ("Encaissé", money(k.collected), "Paiements reçus"),
        ("En attente", money(k.pending), "Factures non échues"),
        ("En retard", money(k.overdue), f"{int(k.overdue_count or 0)} factures"),
        ("Part assurance", f"{coverage:.1f}%", "Du montant facturé"),
    ])

    section("Facturé vs encaissé par mois")
    monthly = q("""
        WITH last_month AS (SELECT strftime('%Y-%m', MAX(invoice_date)) AS m FROM billing),
        billed AS (SELECT strftime('%Y-%m', invoice_date) AS mois, SUM(amount) AS montant
                   FROM billing GROUP BY mois),
        paid AS (SELECT strftime('%Y-%m', payment_date) AS mois, SUM(amount_paid) AS montant
                 FROM payments GROUP BY mois)
        SELECT mois, 'Facturé' AS type, ROUND(montant, 2) AS montant FROM billed
        WHERE mois < (SELECT m FROM last_month)
        UNION ALL
        SELECT mois, 'Encaissé', ROUND(montant, 2) FROM paid
        WHERE mois < (SELECT m FROM last_month)
        ORDER BY mois
    """)
    line(monthly, "mois", "montant", color="type",
         labels={"mois": "Mois", "montant": "Montant ($)", "type": ""}, key="bill_monthly")

    c1, c2, c3 = st.columns(3)
    with c1:
        section("Statut des factures")
        df = q("SELECT payment_status AS statut, COUNT(*) AS factures FROM billing GROUP BY statut")
        donut(translate_values(df, ["statut"]), "statut", "factures", key="bill_status",
              height=300, color_map=STATUS_MAP)
    with c2:
        section("Moyens de paiement")
        df = q("SELECT payment_method AS moyen, ROUND(SUM(amount_paid), 2) AS montant FROM payments GROUP BY moyen")
        donut(translate_values(df, ["moyen"]), "moyen", "montant", key="bill_methods", height=300)
    with c3:
        section("Ancienneté des impayés")
        aging = q("""
            SELECT CAST(julianday((SELECT MAX(invoice_date) FROM billing)) - julianday(invoice_date) AS INTEGER) AS jours,
                   amount FROM billing WHERE payment_status IN ('pending', 'overdue')
        """)
        if not aging.empty:
            labels = ["0-30 j", "31-60 j", "61-90 j", "90+ j"]
            aging["tranche"] = pd.cut(aging["jours"], [-1, 30, 60, 90, 100000], labels=labels)
            buckets = aging.groupby("tranche", observed=False)["amount"].sum().reindex(labels).fillna(0)
            bar(pd.DataFrame({"tranche": labels, "montant": buckets.round(2).values}),
                "tranche", "montant", labels={"tranche": "", "montant": "Montant ($)"},
                key="bill_aging", height=300)

    section("Couverture par assurance")
    ins = q("""
        SELECT COALESCE(p.insurance_provider, 'Sans assurance') AS assurance,
               ROUND(SUM(b.insurance_covered_amount), 2) AS pris_en_charge,
               ROUND(SUM(b.amount - b.insurance_covered_amount), 2) AS part_patient
        FROM billing b JOIN patients p ON b.patient_id = p.patient_id
        GROUP BY assurance ORDER BY pris_en_charge DESC
    """)
    long = ins.melt(id_vars="assurance", var_name="part", value_name="montant")
    long["part"] = long["part"].map({"pris_en_charge": "Pris en charge", "part_patient": "Part patient"})
    bar(long, "assurance", "montant", color="part",
        labels={"assurance": "", "montant": "Montant ($)", "part": ""}, key="bill_insurance")

    section("Factures en retard")
    overdue = q("""
        SELECT b.invoice_id AS facture, b.invoice_date AS date,
               p.last_name || ' ' || p.first_name AS patient, p.phone AS telephone,
               COALESCE(p.insurance_provider, '—') AS assurance,
               b.amount AS montant, b.payment_status AS statut,
               CAST(julianday((SELECT MAX(invoice_date) FROM billing)) - julianday(b.invoice_date) AS INTEGER) AS jours
        FROM billing b JOIN patients p ON b.patient_id = p.patient_id
        WHERE b.payment_status = 'overdue'
        ORDER BY jours DESC
    """)
    st.caption(f"{len(overdue)} facture(s) en retard, les plus anciennes en premier.")
    display = translate_values(overdue, ["statut"])
    st.dataframe(status_style(display, "statut") if not display.empty else display,
                 use_container_width=True, hide_index=True, height=360)
