"""
Mock Chatbot Implementation.
Demonstrates the get_answer interface contract by executing real SQL queries against clinic.db
for a wide array of natural language question patterns, returning structured ChatbotResponse dicts.
"""

import re
from typing import Any
from chatbot.interface import ChatbotResponse
from database.db_utils import run_raw_query


def get_answer(question: str) -> ChatbotResponse:
    """
    Mock implementation of get_answer for demo & testing.
    Matches keyword and regex patterns in natural language questions and executes corresponding SQL.
    """
    q_clean = question.strip().lower()

    # 1. Total Patients / Registered Patients
    if any(k in q_clean for k in ["how many patients", "patient count", "total patients", "number of patients", "registered patients"]):
        sql = "SELECT COUNT(*) AS total_patients FROM patients;"
        try:
            df = run_raw_query(sql)
            count = int(df.iloc[0]["total_patients"]) if not df.empty else 0
            return ChatbotResponse(
                answer_text=f"There are currently {count:,} patients registered in the clinic database.",
                chart_type="kpi",
                data=[{"label": "Total Patients", "value": f"{count:,}"}],
                columns=["label", "value"],
                sql_query=sql,
                error=None
            )
        except Exception as e:
            return _error_response(sql, str(e))

    # 2. Specific Diagnosis Query (e.g. "diabetes", "hypertension", "asthma", "bronchitis")
    elif any(disease in q_clean for disease in ["diabetes", "hypertension", "asthma", "bronchitis", "osteoarthritis", "gerd", "acne", "infection"]):
        disease_match = next((d for d in ["diabetes", "hypertension", "asthma", "bronchitis", "osteoarthritis", "gerd", "acne", "infection"] if d in q_clean), "condition")
        sql = f"""
        SELECT diagnosis_name, severity, COUNT(*) AS count
        FROM diagnoses
        WHERE LOWER(diagnosis_name) LIKE '%{disease_match}%'
        GROUP BY diagnosis_name, severity
        ORDER BY count DESC;
        """.strip()
        try:
            df = run_raw_query(sql)
            data = df.to_dict(orient="records")
            total_cases = sum(d["count"] for d in data) if data else 0
            return ChatbotResponse(
                answer_text=f"Found {total_cases} recorded diagnoses related to '{disease_match}'. Here is the severity breakdown.",
                chart_type="bar",
                data=data,
                columns=["severity", "count"],
                sql_query=sql,
                error=None
            )
        except Exception as e:
            return _error_response(sql, str(e))

    # 3. Appointments by Month / Monthly Trend
    elif any(k in q_clean for k in ["appointments by month", "monthly appointments", "appointment trend", "appointments per month", "monthly volume"]):
        sql = """
        SELECT strftime('%Y-%m', appointment_date) AS month, COUNT(*) AS total_appointments
        FROM appointments
        GROUP BY month
        ORDER BY month ASC;
        """.strip()
        try:
            df = run_raw_query(sql)
            data = df.to_dict(orient="records")
            return ChatbotResponse(
                answer_text=f"Here is the monthly appointment volume over time ({len(data)} months tracked).",
                chart_type="line",
                data=data,
                columns=["month", "total_appointments"],
                sql_query=sql,
                error=None
            )
        except Exception as e:
            return _error_response(sql, str(e))

    # 4. Appointment Status Breakdown (No-shows, cancelled, completed)
    elif any(k in q_clean for k in ["appointment status", "no show", "no-show", "cancellation", "cancelled", "scheduled"]):
        sql = """
        SELECT status, COUNT(*) AS count
        FROM appointments
        GROUP BY status
        ORDER BY count DESC;
        """.strip()
        try:
            df = run_raw_query(sql)
            data = df.to_dict(orient="records")
            return ChatbotResponse(
                answer_text="Here is the breakdown of appointments by status (completed, scheduled, no-show, cancelled).",
                chart_type="pie",
                data=data,
                columns=["status", "count"],
                sql_query=sql,
                error=None
            )
        except Exception as e:
            return _error_response(sql, str(e))

    # 5. Top Diagnoses / Common Diseases
    elif any(k in q_clean for k in ["top diagnoses", "most common diagnoses", "diagnoses", "common diseases", "frequent illnesses"]):
        sql = """
        SELECT diagnosis_name, COUNT(*) AS patient_count
        FROM diagnoses
        GROUP BY diagnosis_name
        ORDER BY patient_count DESC
        LIMIT 8;
        """.strip()
        try:
            df = run_raw_query(sql)
            data = df.to_dict(orient="records")
            top_diag = data[0]["diagnosis_name"] if data else "N/A"
            return ChatbotResponse(
                answer_text=f"The most frequent diagnosis is '{top_diag}'. Here are the top 8 diagnoses.",
                chart_type="bar",
                data=data,
                columns=["diagnosis_name", "patient_count"],
                sql_query=sql,
                error=None
            )
        except Exception as e:
            return _error_response(sql, str(e))

    # 6. Revenue & Financial Breakdown
    elif any(k in q_clean for k in ["revenue", "financial", "billing status", "income", "total billing", "payments summary"]):
        sql = """
        SELECT payment_status, ROUND(SUM(amount), 2) AS total_amount, COUNT(*) AS invoice_count
        FROM billing
        GROUP BY payment_status;
        """.strip()
        try:
            df = run_raw_query(sql)
            data = df.to_dict(orient="records")
            total_rev = sum(item["total_amount"] for item in data if item["payment_status"] == "paid")
            return ChatbotResponse(
                answer_text=f"Total collected revenue is ${total_rev:,.2f}. Here is the breakdown by invoice payment status.",
                chart_type="pie",
                data=data,
                columns=["payment_status", "total_amount"],
                sql_query=sql,
                error=None
            )
        except Exception as e:
            return _error_response(sql, str(e))

    # 7. Payment Methods Breakdown (Card, Cash, Insurance)
    elif any(k in q_clean for k in ["payment method", "payment methods", "card", "cash", "how patients pay"]):
        sql = """
        SELECT payment_method, ROUND(SUM(amount_paid), 2) AS total_paid, COUNT(*) AS transaction_count
        FROM payments
        GROUP BY payment_method;
        """.strip()
        try:
            df = run_raw_query(sql)
            data = df.to_dict(orient="records")
            return ChatbotResponse(
                answer_text="Here is the breakdown of processed payments by payment method.",
                chart_type="pie",
                data=data,
                columns=["payment_method", "total_paid"],
                sql_query=sql,
                error=None
            )
        except Exception as e:
            return _error_response(sql, str(e))

    # 8. Top Prescribed Medications
    elif any(k in q_clean for k in ["medications", "drugs", "top prescribed", "prescriptions", "most common drugs"]):
        sql = """
        SELECT m.name AS medication_name, m.category, COUNT(p.prescription_id) AS prescription_count
        FROM prescriptions p
        JOIN medications m ON p.medication_id = m.medication_id
        GROUP BY m.name, m.category
        ORDER BY prescription_count DESC
        LIMIT 10;
        """.strip()
        try:
            df = run_raw_query(sql)
            data = df.to_dict(orient="records")
            return ChatbotResponse(
                answer_text="Here are the top 10 most frequently prescribed medications.",
                chart_type="bar",
                data=data,
                columns=["medication_name", "prescription_count"],
                sql_query=sql,
                error=None
            )
        except Exception as e:
            return _error_response(sql, str(e))

    # 9. Doctor Workload / Appointments per Doctor
    elif any(k in q_clean for k in ["doctor workload", "busiest doctors", "appointments per doctor", "doctor visits"]):
        sql = """
        SELECT d.first_name || ' ' || d.last_name AS doctor_name, dep.name AS department, COUNT(a.appointment_id) AS total_appointments
        FROM doctors d
        JOIN departments dep ON d.department_id = dep.department_id
        LEFT JOIN appointments a ON d.doctor_id = a.doctor_id
        GROUP BY doctor_name, dep.name
        ORDER BY total_appointments DESC
        LIMIT 8;
        """.strip()
        try:
            df = run_raw_query(sql)
            data = df.to_dict(orient="records")
            return ChatbotResponse(
                answer_text="Here are the top busiest doctors by total appointment volume.",
                chart_type="bar",
                data=data,
                columns=["doctor_name", "total_appointments"],
                sql_query=sql,
                error=None
            )
        except Exception as e:
            return _error_response(sql, str(e))

    # 10. Doctors by Department / Department Breakdown
    elif any(k in q_clean for k in ["doctors by department", "department", "specialty", "doctor count", "departments"]):
        sql = """
        SELECT d.name AS department_name, COUNT(doc.doctor_id) AS doctor_count
        FROM departments d
        LEFT JOIN doctors doc ON d.department_id = doc.department_id
        GROUP BY d.name
        ORDER BY doctor_count DESC;
        """.strip()
        try:
            df = run_raw_query(sql)
            data = df.to_dict(orient="records")
            return ChatbotResponse(
                answer_text="Here is the doctor distribution across clinical departments.",
                chart_type="pie",
                data=data,
                columns=["department_name", "doctor_count"],
                sql_query=sql,
                error=None
            )
        except Exception as e:
            return _error_response(sql, str(e))

    # 11. Patient Demographics (Gender / Blood Type / Insurance)
    elif any(k in q_clean for k in ["gender", "male vs female", "demographics", "sex"]):
        sql = "SELECT gender, COUNT(*) AS count FROM patients GROUP BY gender;"
        try:
            df = run_raw_query(sql)
            data = df.to_dict(orient="records")
            return ChatbotResponse(
                answer_text="Here is the gender distribution of registered clinic patients.",
                chart_type="pie",
                data=data,
                columns=["gender", "count"],
                sql_query=sql,
                error=None
            )
        except Exception as e:
            return _error_response(sql, str(e))

    elif any(k in q_clean for k in ["insurance", "insurance providers", "insurance coverage"]):
        sql = """
        SELECT COALESCE(insurance_provider, 'Self-Pay / None') AS provider, COUNT(*) AS patient_count
        FROM patients
        GROUP BY provider
        ORDER BY patient_count DESC;
        """.strip()
        try:
            df = run_raw_query(sql)
            data = df.to_dict(orient="records")
            return ChatbotResponse(
                answer_text="Here is the patient breakdown by insurance provider.",
                chart_type="pie",
                data=data,
                columns=["provider", "patient_count"],
                sql_query=sql,
                error=None
            )
        except Exception as e:
            return _error_response(sql, str(e))

    # 12. Pending & Overdue Invoices List
    elif any(k in q_clean for k in ["pending invoices", "overdue", "unpaid bills", "unpaid invoices", "billing table"]):
        sql = """
        SELECT b.invoice_id, p.first_name || ' ' || p.last_name AS patient_name,
               b.amount, b.payment_status, b.invoice_date
        FROM billing b
        JOIN patients p ON b.patient_id = p.patient_id
        WHERE b.payment_status IN ('pending', 'overdue')
        ORDER BY b.invoice_date DESC
        LIMIT 10;
        """.strip()
        try:
            df = run_raw_query(sql)
            data = df.to_dict(orient="records")
            return ChatbotResponse(
                answer_text=f"Found {len(data)} recent pending or overdue billing invoices.",
                chart_type="table",
                data=data,
                columns=["invoice_id", "patient_name", "amount", "payment_status", "invoice_date"],
                sql_query=sql,
                error=None
            )
        except Exception as e:
            return _error_response(sql, str(e))

    # Fallback response for unhandled natural language questions
    return ChatbotResponse(
        answer_text="I don't understand that specific question pattern yet. Try asking: 'How many patients?', 'Show appointments by month', 'What are the top diagnoses?', 'Show revenue status', 'Top prescribed medications', or 'Show pending invoices'.",
        chart_type="none",
        data=[],
        columns=None,
        sql_query=None,
        error=None
    )


def _error_response(sql: str, err_msg: str) -> ChatbotResponse:
    return ChatbotResponse(
        answer_text="An error occurred while executing the database query for your question.",
        chart_type="none",
        data=[],
        columns=None,
        sql_query=sql,
        error=err_msg
    )
