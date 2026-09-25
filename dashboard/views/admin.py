"""Administration page: departments, staff, suppliers & medications, system status."""

import pandas as pd
import streamlit as st

from chatbot.ollama_chatbot import ollama_status, OLLAMA_MODEL, OLLAMA_URL
from database.db_utils import DB_PATH
from database.schema import Base
from dashboard.views.common import q, money, section, kpi_row, bar, donut


def _departments():
    df = q("""
        SELECT dep.name AS departement, dep.location AS emplacement,
               (SELECT COUNT(*) FROM doctors d WHERE d.department_id = dep.department_id) AS medecins,
               (SELECT COUNT(*) FROM staff s WHERE s.department_id = dep.department_id) AS personnel,
               (SELECT COUNT(*) FROM appointments a JOIN doctors d ON a.doctor_id = d.doctor_id
                 WHERE d.department_id = dep.department_id) AS rendez_vous
        FROM departments dep ORDER BY dep.name
    """)
    st.dataframe(df, use_container_width=True, hide_index=True)
    bar(df.melt(id_vars="departement", value_vars=["medecins", "personnel"], var_name="type", value_name="effectif")
          .replace({"medecins": "Médecins", "personnel": "Personnel"}),
        "departement", "effectif", color="type",
        labels={"departement": "", "effectif": "Effectif", "type": ""}, key="adm_dep", height=320)


def _staff():
    df = q("""
        SELECT s.last_name || ' ' || s.first_name AS nom, s.role AS fonction,
               dep.name AS departement, s.hire_date AS embauche
        FROM staff s JOIN departments dep ON s.department_id = dep.department_id
        ORDER BY dep.name, s.last_name
    """)
    c1, c2 = st.columns(2)
    with c1:
        role = st.selectbox("Fonction", ["Toutes"] + sorted(df["fonction"].unique().tolist()))
    with c2:
        dep = st.selectbox("Département", ["Tous"] + sorted(df["departement"].unique().tolist()), key="adm_staff_dep")
    view = df
    if role != "Toutes":
        view = view[view["fonction"] == role]
    if dep != "Tous":
        view = view[view["departement"] == dep]
    st.dataframe(view, use_container_width=True, hide_index=True)
    counts = df["fonction"].value_counts().reset_index()
    counts.columns = ["fonction", "effectif"]
    donut(counts, "fonction", "effectif", key="adm_roles", height=300)


def _suppliers_medications():
    meds = q("""
        SELECT m.name AS medicament, m.category AS categorie, m.unit_price AS prix_unitaire,
               COALESCE(s.name, '—') AS fournisseur, COUNT(p.prescription_id) AS prescriptions,
               ROUND(COUNT(p.prescription_id) * m.unit_price, 2) AS valeur_prescrite
        FROM medications m
        LEFT JOIN suppliers s ON m.supplier_id = s.supplier_id
        LEFT JOIN prescriptions p ON p.medication_id = m.medication_id
        GROUP BY m.medication_id ORDER BY prescriptions DESC
    """)
    section("Médicaments")
    st.dataframe(meds, use_container_width=True, hide_index=True)

    c1, c2 = st.columns(2)
    with c1:
        section("Médicaments les plus prescrits")
        bar(meds.head(10), "medicament", "prescriptions",
            labels={"medicament": "", "prescriptions": "Prescriptions"}, horizontal=True, key="adm_meds")
    with c2:
        section("Volume par fournisseur")
        sup = meds.groupby("fournisseur", as_index=False)["prescriptions"].sum().sort_values("prescriptions", ascending=False)
        bar(sup, "fournisseur", "prescriptions",
            labels={"fournisseur": "", "prescriptions": "Prescriptions"}, horizontal=True, key="adm_sup")

    section("Annuaire des fournisseurs")
    st.dataframe(q("""
        SELECT name AS fournisseur, category AS categorie, contact_person AS contact,
               phone AS telephone, email, contract_start_date AS debut_contrat
        FROM suppliers ORDER BY name
    """), use_container_width=True, hide_index=True)


def _system():
    status = ollama_status()
    running = status["running"]
    model_ok = status["model_installed"]

    kpi_row([
        ("Serveur IA (Ollama)", "En ligne" if running else "Hors ligne", OLLAMA_URL),
        ("Modèle actif", OLLAMA_MODEL, "Installé" if model_ok else "Non installé"),
        ("Base de données", "SQLite", DB_PATH.name),
        ("Taille", f"{DB_PATH.stat().st_size / 1_048_576:.1f} Mo" if DB_PATH.exists() else "—", "Fichier clinic.db"),
    ])
    if not running:
        st.warning("Ollama ne répond pas : l'assistant fonctionne en mode hors ligne (règles par mots-clés). "
                   "Lancez l'application Ollama pour réactiver l'IA.")
    elif not model_ok:
        st.warning(f"Le modèle « {OLLAMA_MODEL} » n'est pas installé. Exécutez : ollama pull {OLLAMA_MODEL}")
    if status["models"]:
        st.caption("Modèles disponibles : " + ", ".join(status["models"]))

    section("Contenu de la base de données")
    counts = [(t.name, int(q(f'SELECT COUNT(*) AS n FROM "{t.name}"').iloc[0]["n"]))
              for t in Base.metadata.sorted_tables]
    df = pd.DataFrame(counts, columns=["table", "lignes"]).sort_values("lignes", ascending=False)
    bar(df, "table", "lignes", labels={"table": "", "lignes": "Lignes"}, horizontal=True, key="adm_tables", height=420)

    section("Sécurité de l'assistant IA")
    st.markdown("""
- Le modèle tourne **localement** : ni les questions ni les données patients ne quittent la machine.
- Les requêtes générées sont exécutées sur une connexion **en lecture seule** : l'IA ne peut ni modifier ni supprimer de données.
- Seules les requêtes `SELECT` sont acceptées ; en cas d'erreur, le modèle corrige lui-même sa requête une fois.
""")


def render():
    k = q("""
        SELECT (SELECT COUNT(*) FROM departments) AS deps, (SELECT COUNT(*) FROM doctors) AS docs,
               (SELECT COUNT(*) FROM staff) AS staff, (SELECT COUNT(*) FROM suppliers) AS sups,
               (SELECT COUNT(*) FROM medications) AS meds
    """).iloc[0]
    kpi_row([
        ("Départements", str(int(k.deps)), "Services cliniques"),
        ("Médecins", str(int(k.docs)), "Corps médical"),
        ("Personnel", str(int(k.staff)), "Soignants et administratifs"),
        ("Fournisseurs", str(int(k.sups)), "Sous contrat"),
        ("Médicaments", str(int(k.meds)), "Au catalogue"),
    ])
    t1, t2, t3, t4 = st.tabs(["Départements", "Personnel", "Fournisseurs & médicaments", "Système"])
    with t1:
        _departments()
    with t2:
        _staff()
    with t3:
        _suppliers_medications()
    with t4:
        _system()
