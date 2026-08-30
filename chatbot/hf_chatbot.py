"""
Hugging Face AI Powered Chatbot Module.
Translates natural language user questions into executable SQLite queries
for the Smart Clinic database, auto-classifies chart visual types,
and returns structured ChatbotResponse dicts.

Includes anti-hallucination domain guardrails: when a question cannot be answered
from the clinic database, it cleanly informs the user rather than hallucinating.
"""

import re
import logging
from typing import Any, Optional
import pandas as pd
import torch
from chatbot.interface import ChatbotResponse
from database.db_utils import run_raw_query

logger = logging.getLogger(__name__)

# Hugging Face Model Identifier
HF_MODEL_NAME = "cssupport/t5-small-awesome-text-to-sql"
_hf_tokenizer = None
_hf_model = None
_hf_init_attempted = False


def _init_hf_model():
    """Initializes Hugging Face tokenizer and Seq2Seq model cleanly."""
    global _hf_tokenizer, _hf_model, _hf_init_attempted
    if not _hf_init_attempted:
        _hf_init_attempted = True
        try:
            from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
            logger.info(f"Loading Hugging Face model '{HF_MODEL_NAME}'...")
            _hf_tokenizer = AutoTokenizer.from_pretrained(HF_MODEL_NAME)
            _hf_model = AutoModelForSeq2SeqLM.from_pretrained(HF_MODEL_NAME)
            if _hf_model:
                _hf_model.eval()  # Put model in evaluation mode
        except Exception as e:
            logger.warning(f"Hugging Face model initialization fallback: {e}")
            _hf_tokenizer = None
            _hf_model = None


def generate_sql_from_hf(question: str) -> Optional[str]:
    """
    Generates SQL query using Hugging Face Transformers model inside torch.no_grad().
    Returns None if the question is out-of-domain or cannot be answered from the clinic database.
    """
    _init_hf_model()
    generated_sql = None

    if _hf_tokenizer is not None and _hf_model is not None:
        try:
            input_text = f"tables: patients, appointments, visits, diagnoses, doctors, departments, billing | question: {question}"
            inputs = _hf_tokenizer(input_text, return_tensors="pt", max_length=256, truncation=True)
            
            with torch.no_grad():
                outputs = _hf_model.generate(**inputs, max_new_tokens=100)
            
            raw_text = _hf_tokenizer.decode(outputs[0], skip_special_tokens=True)
            generated_sql = _clean_sql_string(raw_text)
        except Exception as e:
            logger.warning(f"HF model inference error: {e}")

    if generated_sql and _is_valid_sql_syntax(generated_sql):
        return generated_sql

    return _schema_aware_sql_generator(question)


def _clean_sql_string(raw_sql: str) -> str:
    """Cleans markdown tags, extra spaces, and newlines from generated SQL text."""
    sql = raw_sql.strip()
    sql = re.sub(r"^```sql", "", sql, flags=re.IGNORECASE)
    sql = re.sub(r"^```", "", sql)
    sql = re.sub(r"```$", "", sql)
    sql = sql.strip()
    if not sql.endswith(";"):
        sql += ";"
    return sql


def _is_valid_sql_syntax(sql: str) -> bool:
    """Basic check to ensure text starts with SELECT and contains FROM."""
    cleaned = sql.strip().upper()
    return cleaned.startswith("SELECT") and "FROM" in cleaned


def _schema_aware_sql_generator(question: str) -> Optional[str]:
    """
    Schema-aware text-to-SQL engine handling natural language questions against clinic.db tables.
    Returns None if question is out-of-domain (anti-hallucination guardrail).
    """
    q_clean = question.strip().lower()

    # 1. Specific Entity Count Queries
    if any(k in q_clean for k in ["how many doctors", "doctor count", "total doctors", "number of doctors", "physician count", "how many physicians"]):
        return "SELECT COUNT(*) AS total_doctors FROM doctors;"

    elif any(k in q_clean for k in ["how many patients", "patient count", "total patients", "number of patients", "registered patients"]):
        return "SELECT COUNT(*) AS total_patients FROM patients;"

    elif any(k in q_clean for k in ["how many staff", "staff count", "total staff", "number of staff", "employee count"]):
        return "SELECT COUNT(*) AS total_staff FROM staff;"

    elif any(k in q_clean for k in ["how many departments", "department count", "total departments"]):
        return "SELECT COUNT(*) AS total_departments FROM departments;"

    elif any(k in q_clean for k in ["how many appointments", "appointment count", "total appointments", "number of appointments"]):
        return "SELECT COUNT(*) AS total_appointments FROM appointments;"

    elif any(k in q_clean for k in ["how many visits", "visit count", "total visits", "encounter count"]):
        return "SELECT COUNT(*) AS total_visits FROM visits;"

    elif any(k in q_clean for k in ["how many prescriptions", "prescription count", "total prescriptions"]):
        return "SELECT COUNT(*) AS total_prescriptions FROM prescriptions;"

    elif any(k in q_clean for k in ["how many medications", "medication count", "total medications", "how many drugs"]):
        return "SELECT COUNT(*) AS total_medications FROM medications;"

    elif any(k in q_clean for k in ["how many lab tests", "lab test count", "total lab tests"]):
        return "SELECT COUNT(*) AS total_lab_tests FROM lab_tests;"

    elif any(k in q_clean for k in ["how many invoices", "invoice count", "total invoices", "billing count"]):
        return "SELECT COUNT(*) AS total_invoices FROM billing;"

    elif any(k in q_clean for k in ["how many suppliers", "supplier count", "total suppliers", "number of suppliers", "how many vendors", "vendor count"]):
        return "SELECT COUNT(*) AS total_suppliers FROM suppliers;"

    # 2. Disease / Diagnosis Queries
    elif any(disease in q_clean for disease in ["diabetes", "hypertension", "asthma", "bronchitis", "osteoarthritis", "gerd", "acne", "infection"]):
        match = next((d for d in ["diabetes", "hypertension", "asthma", "bronchitis", "osteoarthritis", "gerd", "acne", "infection"] if d in q_clean), "condition")
        return f"SELECT diagnosis_name, severity, COUNT(*) AS count FROM diagnoses WHERE LOWER(diagnosis_name) LIKE '%{match}%' GROUP BY diagnosis_name, severity ORDER BY count DESC;"

    # 3. Monthly Trends
    elif any(k in q_clean for k in ["appointments by month", "monthly appointments", "appointment trend", "appointments per month", "monthly volume"]):
        return "SELECT strftime('%Y-%m', appointment_date) AS month, COUNT(*) AS total_appointments FROM appointments GROUP BY month ORDER BY month ASC;"

    # 4. Status Breakdown
    elif any(k in q_clean for k in ["appointment status", "no show", "no-show", "cancellation", "cancelled", "scheduled"]):
        return "SELECT status, COUNT(*) AS count FROM appointments GROUP BY status ORDER BY count DESC;"

    # 5. Top Diagnoses
    elif any(k in q_clean for k in ["top diagnoses", "most common diagnoses", "diagnoses", "common diseases", "frequent illnesses"]):
        return "SELECT diagnosis_name, COUNT(*) AS patient_count FROM diagnoses GROUP BY diagnosis_name ORDER BY patient_count DESC LIMIT 8;"

    # 6. Revenue & Financials
    elif any(k in q_clean for k in ["revenue", "financial", "billing status", "income", "total billing", "payments summary"]):
        return "SELECT payment_status, ROUND(SUM(amount), 2) AS total_amount, COUNT(*) AS invoice_count FROM billing GROUP BY payment_status;"

    elif any(k in q_clean for k in ["payment method", "payment methods", "card", "cash", "how patients pay"]):
        return "SELECT payment_method, ROUND(SUM(amount_paid), 2) AS total_paid, COUNT(*) AS transaction_count FROM payments GROUP BY payment_method;"

    # 7. Medications
    elif any(k in q_clean for k in ["medications", "drugs", "top prescribed", "prescriptions", "most common drugs"]):
        return "SELECT m.name AS medication_name, m.category, COUNT(p.prescription_id) AS prescription_count FROM prescriptions p JOIN medications m ON p.medication_id = m.medication_id GROUP BY m.name, m.category ORDER BY prescription_count DESC LIMIT 10;"

    # 7b. Suppliers / Vendors
    elif any(k in q_clean for k in ["supplier", "suppliers", "vendor", "vendors", "fournisseur", "fournisseurs"]):
        return "SELECT s.name AS supplier_name, COUNT(p.prescription_id) AS prescriptions_filled FROM suppliers s JOIN medications m ON m.supplier_id = s.supplier_id LEFT JOIN prescriptions p ON p.medication_id = m.medication_id GROUP BY s.name ORDER BY prescriptions_filled DESC;"

    # 8. Doctors & Staffing
    elif any(k in q_clean for k in ["doctor workload", "busiest doctors", "appointments per doctor", "doctor visits"]):
        return "SELECT d.first_name || ' ' || d.last_name AS doctor_name, dep.name AS department, COUNT(a.appointment_id) AS total_appointments FROM doctors d JOIN departments dep ON d.department_id = dep.department_id LEFT JOIN appointments a ON d.doctor_id = a.doctor_id GROUP BY doctor_name, dep.name ORDER BY total_appointments DESC LIMIT 8;"

    elif any(k in q_clean for k in ["doctors by department", "department", "specialty", "departments", "doctors list", "doctor"]):
        return "SELECT d.name AS department_name, COUNT(doc.doctor_id) AS doctor_count FROM departments d LEFT JOIN doctors doc ON d.department_id = doc.department_id GROUP BY d.name ORDER BY doctor_count DESC;"

    # 9. Demographics & Insurance
    elif any(k in q_clean for k in ["gender", "male vs female", "demographics"]):
        return "SELECT gender, COUNT(*) AS count FROM patients GROUP BY gender;"

    elif any(k in q_clean for k in ["insurance", "insurance providers"]):
        return "SELECT COALESCE(insurance_provider, 'Self-Pay / None') AS provider, COUNT(*) AS patient_count FROM patients GROUP BY provider ORDER BY patient_count DESC;"

    # 10. Billing Tables
    elif any(k in q_clean for k in ["pending invoices", "overdue", "unpaid bills", "unpaid invoices", "billing table", "invoice"]):
        return "SELECT b.invoice_id, p.first_name || ' ' || p.last_name AS patient_name, b.amount, b.payment_status, b.invoice_date FROM billing b JOIN patients p ON b.patient_id = p.patient_id WHERE b.payment_status IN ('pending', 'overdue') ORDER BY b.invoice_date DESC LIMIT 10;"

    # General domain keywords
    elif any(k in q_clean for k in ["patient", "visit", "encounter", "clinic"]):
        return "SELECT COUNT(*) AS total_patients FROM patients;"

    # Out of domain query -> Return None to prevent hallucination
    return None


def infer_chart_type(df: pd.DataFrame, columns: list[str]) -> str:
    """
    Automatically classifies optimal visualization chart_type based on query result shape.
    Returns one of: 'kpi', 'bar', 'line', 'pie', 'table', or 'none'.
    """
    if df.empty:
        return "none"

    rows, cols_count = df.shape

    if rows == 1 and cols_count == 1:
        return "kpi"
    if rows == 1 and cols_count == 2 and any(k in str(df.columns[0]).lower() for k in ["label", "metric", "title"]):
        return "kpi"

    first_col_name = str(df.columns[0]).lower()
    if any(date_k in first_col_name for date_k in ["date", "month", "year", "time", "day", "period"]):
        return "line"

    if cols_count == 2 or cols_count == 3:
        if rows <= 5 and any(p_k in str(df.columns[0]).lower() for p_k in ["status", "gender", "provider", "payment_method", "department"]):
            return "pie"
        if rows <= 15:
            return "bar"

    return "table"


def generate_natural_answer(question: str, df: pd.DataFrame, sql: str) -> str:
    """Generates professional, human-readable natural language summaries of query results."""
    if df.empty:
        return f"No clinic records were found matching your query: '{question}'."

    q_clean = question.strip().lower()
    rows, cols = df.shape

    # Single Metric / KPI Handling
    if rows == 1 and cols == 1:
        col_raw = df.columns[0].lower()
        val = df.iloc[0, 0]

        if col_raw == "total_doctors" or "doctor" in q_clean:
            return f"There are currently {val} active doctors practicing across the clinic."
        if col_raw == "total_patients" or "patient" in q_clean:
            return f"There are currently {val:,} registered patients in the Smart Clinic system."
        if col_raw == "total_staff" or "staff" in q_clean:
            return f"The clinic employs {val} administrative and nursing staff members."
        if col_raw == "total_departments" or "department" in q_clean:
            return f"The clinic operates {val} specialized medical departments."
        if col_raw == "total_appointments" or "appointment" in q_clean:
            return f"A total of {val:,} appointments have been scheduled in the clinic system."
        if col_raw == "total_visits" or "visit" in q_clean:
            return f"The clinic has conducted {val:,} completed patient clinical encounters."
        if col_raw == "total_prescriptions" or "prescription" in q_clean:
            return f"A total of {val:,} prescriptions have been issued to patients."
        if col_raw == "total_medications" or "medication" in q_clean:
            return f"The pharmacy inventory includes {val} registered medications."
        if col_raw == "total_lab_tests" or "lab" in q_clean:
            return f"A total of {val:,} diagnostic lab tests have been ordered."
        if col_raw == "total_invoices" or "invoice" in q_clean:
            return f"A total of {val:,} billing invoices have been generated."
        if col_raw == "total_suppliers" or "supplier" in q_clean or "vendor" in q_clean:
            return f"The clinic currently sources medications and supplies from {val} registered suppliers."

        col_name = df.columns[0].replace("_", " ").title()
        if isinstance(val, float):
            return f"The calculated {col_name.lower()} is ${val:,.2f}."
        if isinstance(val, int):
            return f"The total {col_name.lower()} is {val:,}."
        return f"The requested {col_name.lower()} is {val}."

    # Specific disease queries
    if any(d in q_clean for d in ["diabetes", "hypertension", "asthma", "bronchitis", "osteoarthritis", "gerd", "acne", "infection"]):
        disease = next((d for d in ["diabetes", "hypertension", "asthma", "bronchitis", "osteoarthritis", "gerd", "acne", "infection"] if d in q_clean), "condition")
        total = df["count"].sum() if "count" in df.columns else rows
        return f"Found {total:,} recorded patient encounters related to '{disease.title()}'. Below is the breakdown by clinical severity."

    # Monthly Trends
    if "month" in q_clean or "trend" in q_clean:
        total_appts = df["total_appointments"].sum() if "total_appointments" in df.columns else 0
        return f"Tracked {rows} months of appointment history totaling {total_appts:,} visits. Below is the monthly volume trend over time."

    # Top Diagnoses
    if "diagnoses" in q_clean or "disease" in q_clean or "illness" in q_clean:
        top_name = df.iloc[0]["diagnosis_name"] if "diagnosis_name" in df.columns else df.iloc[0, 0]
        return f"The most prevalent diagnosis is '{top_name}'. Below is the distribution of the top {rows} clinical diagnoses."

    # Revenue / Billing
    if "revenue" in q_clean or "billing" in q_clean or "financial" in q_clean or "income" in q_clean:
        if "total_amount" in df.columns:
            paid = df[df["payment_status"] == "paid"]["total_amount"].sum() if "payment_status" in df.columns else 0
            return f"Total collected clinic revenue is ${paid:,.2f}. Here is the financial breakdown by payment status."
        return "Here is the financial breakdown of clinic billing invoices."

    # Suppliers / Vendors
    if "supplier" in q_clean or "vendor" in q_clean:
        top_supplier = df.iloc[0]["supplier_name"] if "supplier_name" in df.columns else df.iloc[0, 0]
        return f"Your top supplier by prescription volume is '{top_supplier}'. Below is the breakdown across {rows} suppliers."

    # Medications / Prescriptions
    if "medication" in q_clean or "drug" in q_clean or "prescription" in q_clean:
        top_med = df.iloc[0]["medication_name"] if "medication_name" in df.columns else df.iloc[0, 0]
        return f"The most frequently prescribed medication is '{top_med}'. Below are the top {rows} prescribed pharmaceuticals."

    # Doctor Workload
    if "doctor" in q_clean or "workload" in q_clean or "busiest" in q_clean:
        top_doc = df.iloc[0]["doctor_name"] if "doctor_name" in df.columns else df.iloc[0, 0]
        return f"The physician with the highest encounter volume is {top_doc}. Below is the appointment load across doctors."

    # Department
    if "department" in q_clean:
        return f"Displaying doctor staffing and patient visit distribution across {rows} clinical departments."

    # Pending Invoices
    if "pending" in q_clean or "overdue" in q_clean or "unpaid" in q_clean:
        return f"Retrieved {rows} recent billing invoices marked as pending or overdue requiring administrative attention."

    # Demographics
    if "gender" in q_clean or "male" in q_clean or "female" in q_clean or "demographics" in q_clean:
        return f"Here is the demographic gender distribution of registered clinic patients."

    if "insurance" in q_clean:
        return f"Displaying patient distribution across {rows} insurance providers."

    # Generic Fallback
    first_col = df.columns[0].replace("_", " ").title()
    first_val = df.iloc[0, 0]
    return f"Query executed successfully. Retrieved {rows} record{'s' if rows > 1 else ''} ({first_col}: {first_val})."


def get_answer(question: str) -> ChatbotResponse:
    """
    Hugging Face powered implementation of get_answer contract interface.
    Converts natural language questions to SQL, executes against clinic.db,
    classifies visual chart types, and returns ChatbotResponse.
    Includes anti-hallucination guardrail if database does not contain enough information.
    """
    if not question or not question.strip():
        return ChatbotResponse(
            answer_text="Please provide a natural language question about the clinic database.",
            chart_type="none",
            data=[],
            columns=None,
            sql_query=None,
            error="Empty question provided."
        )

    try:
        sql_query = generate_sql_from_hf(question)

        # Anti-Hallucination Guardrail: Question outside database scope
        if not sql_query:
            return ChatbotResponse(
                answer_text="I don't have enough information in the clinic database to answer this question. Please ask about clinic patients, doctors, appointments, diagnoses, treatments, prescriptions, or billing statistics.",
                chart_type="none",
                data=[],
                columns=None,
                sql_query=None,
                error=None
            )

        try:
            df = run_raw_query(sql_query)
        except Exception as exec_err:
            # The AI-generated SQL was syntactically valid but failed to execute
            # (e.g. wrong table/column names). Retry with the reliable keyword-based
            # fallback before giving up, instead of jumping straight to the
            # "I don't have enough information" guardrail message.
            logger.warning(f"Generated SQL failed to execute ('{sql_query}'): {exec_err}. Retrying with fallback generator.")
            fallback_sql = _schema_aware_sql_generator(question)
            if not fallback_sql:
                return ChatbotResponse(
                    answer_text="I don't have enough information in the clinic database to answer this question. Please ask about clinic patients, doctors, appointments, diagnoses, treatments, prescriptions, or billing statistics.",
                    chart_type="none",
                    data=[],
                    columns=None,
                    sql_query=None,
                    error=None
                )
            sql_query = fallback_sql
            df = run_raw_query(sql_query)

        columns = list(df.columns)
        data = df.to_dict(orient="records")
        chart_type = infer_chart_type(df, columns)

        if chart_type == "kpi" and data:
            if len(columns) == 1:
                val = list(data[0].values())[0]
                label = columns[0].replace("_", " ").title()
                data = [{"label": label, "value": f"{val:,}" if isinstance(val, int) else f"{val}"}]
                columns = ["label", "value"]

        answer_text = generate_natural_answer(question, df, sql_query)

        return ChatbotResponse(
            answer_text=answer_text,
            chart_type=chart_type,
            data=data,
            columns=columns,
            sql_query=sql_query,
            error=None
        )

    except Exception as e:
        logger.error(f"Error processing question '{question}': {e}")
        return ChatbotResponse(
            answer_text="I don't have enough information in the clinic database to answer this question. Please ask about clinic patients, doctors, appointments, diagnoses, treatments, prescriptions, or billing statistics.",
            chart_type="none",
            data=[],
            columns=None,
            sql_query=None,
            error=None
        )