"""
Local LLM Text-to-SQL Chatbot (Ollama).

Pipeline:
  1. Build a description of the database (tables, columns, foreign keys,
     example values) automatically from the SQLAlchemy models.
  2. Send the schema + the user's question to a local LLM running in Ollama,
     which writes one SQLite SELECT query.
  3. Safety layer: accept only a single read-only SELECT, and execute it on a
     read-only connection so the database can never be modified.
  4. Self-correction: if the query fails, the error is sent back to the model
     once so it can fix its own SQL.
  5. The model writes a one-sentence answer from the result rows.
  6. If Ollama is not running, fall back to the keyword-based generator.

No data leaves the machine: the model runs locally.
"""

import json
import logging
import os
import re
import sqlite3
import urllib.error
import urllib.request
from functools import lru_cache
from typing import Optional

import pandas as pd

from chatbot.interface import ChatbotResponse
from database.db_utils import DB_PATH
from database.schema import Base

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------------------
# Configuration (can be overridden with environment variables)
# ------------------------------------------------------------------------------
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5-coder:7b")
REQUEST_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "180"))  # CPU inference can be slow
MAX_ROWS = 500  # safety cap on rows returned to the dashboard
SUMMARIZE_WITH_LLM = os.getenv("OLLAMA_SUMMARIZE", "1") == "1"

OUT_OF_SCOPE_MSG = (
    "Je ne dispose pas des informations nécessaires dans la base de la clinique pour répondre. "
    "Posez une question sur les patients, médecins, rendez-vous, diagnostics, prescriptions, "
    "analyses de laboratoire, factures ou paiements."
)

FORBIDDEN_KEYWORDS = (
    "insert", "update", "delete", "drop", "alter", "create",
    "attach", "detach", "pragma", "vacuum", "reindex", "truncate",
)


# ------------------------------------------------------------------------------
# 1. Schema description (built automatically, so it never goes out of sync)
# ------------------------------------------------------------------------------
def _read_only_connection() -> sqlite3.Connection:
    """Opens clinic.db in read-only mode: writes are impossible at the SQLite level."""
    return sqlite3.connect(f"file:{DB_PATH.as_posix()}?mode=ro", uri=True)


@lru_cache(maxsize=1)
def build_schema_description() -> str:
    """
    Describes every table and column from the SQLAlchemy models, including
    foreign keys and example values for short text columns (e.g. status values),
    so the model uses the exact spellings stored in the database.
    """
    lines = []
    with _read_only_connection() as conn:
        for table in Base.metadata.sorted_tables:
            lines.append(f"TABLE {table.name}")
            for col in table.columns:
                desc = f"  - {col.name} ({col.type})"
                if col.primary_key:
                    desc += " PRIMARY KEY"
                for fk in col.foreign_keys:
                    desc += f" -> {fk.target_fullname}"
                # Add example values for low-cardinality text columns
                if str(col.type).startswith("VARCHAR") and not col.primary_key:
                    try:
                        values = conn.execute(
                            f'SELECT DISTINCT "{col.name}" FROM "{table.name}" '
                            f'WHERE "{col.name}" IS NOT NULL LIMIT 13'
                        ).fetchall()
                        if 0 < len(values) <= 12:
                            desc += " values: " + ", ".join(repr(v[0]) for v in values)
                    except sqlite3.Error:
                        pass
                lines.append(desc)
            lines.append("")

        # Tell the model which period the data covers
        try:
            first, last = conn.execute(
                "SELECT MIN(appointment_date), MAX(appointment_date) FROM appointments"
            ).fetchone()
            lines.append(f"Appointment data covers {first} to {last}.")
        except sqlite3.Error:
            pass

    return "\n".join(lines)


# ------------------------------------------------------------------------------
# 2. Talking to the local model
# ------------------------------------------------------------------------------
def _ollama_chat(messages: list[dict]) -> str:
    """Sends a chat request to the local Ollama server and returns the reply text."""
    payload = json.dumps({
        "model": OLLAMA_MODEL,
        "messages": messages,
        "stream": False,
        "options": {"temperature": 0},  # deterministic output for SQL
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    # Bypass any system HTTP proxy: Ollama runs on this machine.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(req, timeout=REQUEST_TIMEOUT) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    return body["message"]["content"]


def ask_model(system: str, user: str) -> str:
    """Public helper: sends one system + user message to the local model (used for reports)."""
    return _ollama_chat([
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]).strip()


def ollama_status() -> dict:
    """Checks whether Ollama is running and whether the configured model is installed."""
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(f"{OLLAMA_URL}/api/tags", timeout=3) as resp:
            models = [m["name"] for m in json.loads(resp.read().decode("utf-8")).get("models", [])]
        installed = any(m == OLLAMA_MODEL or m.split(":")[0] == OLLAMA_MODEL for m in models)
        return {"running": True, "model_installed": installed, "models": models}
    except Exception:
        return {"running": False, "model_installed": False, "models": []}


def _system_prompt() -> str:
    return f"""You are an expert SQLite analyst for a medical clinic.
Write ONE SQLite SELECT query that answers the user's question using this database:

{build_schema_description()}

Rules:
- The question may be written in French or English.
- Return only the SQL query, with no explanation and no markdown.
- Use only the tables and columns listed above, with the exact text values shown.
- Only SELECT (or WITH ... SELECT). Never modify data.
- Use clear column aliases (e.g. department, total_appointments).
- For relative dates ("last month", "this year"), use the most recent date in the data
  as "today", not the real current date.
- Use strftime('%Y-%m', column) to group by month.
- If the question cannot be answered from this database, return exactly: NO_ANSWER"""


def _extract_sql(text: str) -> Optional[str]:
    """Pulls the SQL out of the model's reply (removes markdown fences, extra text)."""
    text = text.strip()
    if "NO_ANSWER" in text.upper():
        return None
    fenced = re.search(r"```(?:sql)?\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if fenced:
        text = fenced.group(1).strip()
    match = re.search(r"\b(WITH|SELECT)\b.*", text, re.DOTALL | re.IGNORECASE)
    if not match:
        return None
    sql = match.group(0).strip()
    # Keep only the first statement
    sql = sql.split(";")[0].strip()
    return sql + ";" if sql else None


# ------------------------------------------------------------------------------
# 3. Safety layer
# ------------------------------------------------------------------------------
def is_safe_select(sql: str) -> bool:
    """Accepts a single read-only SELECT / WITH query and nothing else."""
    body = sql.strip().rstrip(";").strip()
    if ";" in body:
        return False  # multiple statements
    lowered = body.lower()
    if not (lowered.startswith("select") or lowered.startswith("with")):
        return False
    words = set(re.findall(r"[a-z_]+", lowered))
    return not any(k in words for k in FORBIDDEN_KEYWORDS)


def run_read_only(sql: str) -> pd.DataFrame:
    """Executes the query on a read-only connection and caps the number of rows."""
    with _read_only_connection() as conn:
        df = pd.read_sql_query(sql, conn)
    return df.head(MAX_ROWS)


# ------------------------------------------------------------------------------
# 4. Presentation helpers
# ------------------------------------------------------------------------------
def infer_chart_type(df: pd.DataFrame) -> str:
    """Chooses how the dashboard should display the result based on its shape."""
    if df.empty:
        return "none"
    rows, cols = df.shape
    if rows == 1 and cols == 1:
        return "kpi"
    first_col = str(df.columns[0]).lower()
    numeric_second = cols >= 2 and pd.api.types.is_numeric_dtype(df.iloc[:, 1])
    if numeric_second and any(k in first_col for k in ["date", "month", "year", "week", "day", "period"]):
        return "line"
    if cols == 2 and numeric_second:
        if rows <= 6 and any(k in first_col for k in
                             ["status", "gender", "provider", "method", "severity", "blood", "department"]):
            return "pie"
        if rows <= 20:
            return "bar"
    return "table"


def _summarize(question: str, df: pd.DataFrame) -> str:
    """Asks the model for a one-sentence answer based on the actual result rows."""
    if df.empty:
        return "La requête a été exécutée mais aucun enregistrement ne correspond."
    fallback = f"{len(df)} résultat{'s' if len(df) != 1 else ''} trouvé{'s' if len(df) != 1 else ''}."
    if not SUMMARIZE_WITH_LLM:
        return fallback
    try:
        preview = df.head(20).to_string(index=False)
        reply = _ollama_chat([
            {"role": "system", "content": (
                "Tu réponds en français, en une ou deux phrases courtes, à des questions sur une "
                "clinique, en utilisant uniquement les chiffres du résultat. Ne mentionne pas le SQL."
            )},
            {"role": "user", "content": f"Question: {question}\n\nQuery result:\n{preview}"},
        ])
        return reply.strip() or fallback
    except Exception as e:
        logger.warning(f"Summary generation failed: {e}")
        return fallback


def _response(answer, chart="none", data=None, columns=None, sql=None, error=None) -> ChatbotResponse:
    return ChatbotResponse(
        answer_text=answer, chart_type=chart, data=data or [],
        columns=columns, sql_query=sql, error=error,
    )


def _build_result(question: str, sql: str, df: pd.DataFrame, answer: Optional[str] = None) -> ChatbotResponse:
    chart = infer_chart_type(df)
    columns = list(df.columns)
    data = df.to_dict(orient="records")
    if chart == "kpi":
        value = data[0][columns[0]]
        data = [{"label": columns[0].replace("_", " ").title(),
                 "value": f"{value:,}" if isinstance(value, int) else str(value)}]
        columns = ["label", "value"]
    return _response(answer or _summarize(question, df), chart, data, columns, sql)


def _keyword_fallback(question: str) -> ChatbotResponse:
    """Used only when Ollama is unreachable: reuses the original rule-based generator."""
    try:
        from chatbot.hf_chatbot import _schema_aware_sql_generator
        sql = _schema_aware_sql_generator(question)
        if sql and is_safe_select(sql):
            df = run_read_only(sql)
            return _build_result(question, sql, df,
                                 answer=f"(Mode hors ligne) {len(df)} résultat(s) trouvé(s).")
    except Exception as e:
        logger.warning(f"Keyword fallback failed: {e}")
    return _response(
        "Le modèle d'IA local n'est pas lancé. Démarrez Ollama puis réessayez.",
        error=f"Ollama injoignable à {OLLAMA_URL} (modèle « {OLLAMA_MODEL} »).",
    )


# ------------------------------------------------------------------------------
# 5. The contract function used by the dashboard
# ------------------------------------------------------------------------------
def get_answer(question: str) -> ChatbotResponse:
    if not question or not question.strip():
        return _response("Veuillez saisir une question sur la clinique.", error="Question vide.")

    messages = [
        {"role": "system", "content": _system_prompt()},
        {"role": "user", "content": question.strip()},
    ]

    try:
        reply = _ollama_chat(messages)
    except (urllib.error.URLError, ConnectionError, TimeoutError) as e:
        logger.warning(f"Ollama unreachable: {e}")
        return _keyword_fallback(question)
    except Exception as e:
        logger.error(f"Ollama error: {e}")
        return _keyword_fallback(question)

    sql = _extract_sql(reply)
    if sql is None:
        return _response(OUT_OF_SCOPE_MSG)
    if not is_safe_select(sql):
        return _response("Requête bloquée : seules les consultations en lecture sont autorisées.",
                         sql=sql, error="La requête générée n'était pas un SELECT en lecture seule.")

    # Execute, with one self-correction attempt if the SQL fails
    try:
        df = run_read_only(sql)
    except Exception as first_error:
        logger.info(f"SQL failed, asking the model to fix it: {first_error}")
        try:
            fixed_reply = _ollama_chat(messages + [
                {"role": "assistant", "content": sql},
                {"role": "user", "content": (
                    f"This query failed with the error: {first_error}\n"
                    "Return a corrected SQLite query only."
                )},
            ])
            fixed_sql = _extract_sql(fixed_reply)
            if not fixed_sql or not is_safe_select(fixed_sql):
                raise ValueError("No valid corrected query.")
            df = run_read_only(fixed_sql)
            sql = fixed_sql
        except Exception as second_error:
            return _response(
                "Désolé, je n'ai pas pu construire une requête valide. Essayez de reformuler la question.",
                sql=sql, error=str(second_error),
            )

    return _build_result(question, sql, df)
