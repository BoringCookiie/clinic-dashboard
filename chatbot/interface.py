"""
Chatbot Contract Interface Module.
Defines the ChatbotResponse TypedDict and the get_answer function signature.
DO NOT MODIFY THIS SIGNATURE. Both the mock chatbot and the teammate's real implementation
must adhere to this contract.
"""

from typing import TypedDict, Literal, Any, Optional


class ChatbotResponse(TypedDict):
    answer_text: str                 # Short natural-language answer, e.g., "There are 401 patients registered."
    chart_type: Literal["kpi", "bar", "line", "pie", "table", "none"]
    data: list[dict[str, Any]]       # Structured dataset to visualize, e.g., [{"category": "Cardiology", "count": 12}, ...]
    columns: Optional[list[str]]     # Optional: column headers or axes mapping
    sql_query: Optional[str]         # Optional: SQL query executed (for transparency/debugging)
    error: Optional[str]             # Optional: Explanation if question could not be answered


def get_answer(question: str) -> ChatbotResponse:
    """
    Takes a natural language question about the clinic database and returns
    a structured response the dashboard can render.

    This is the function signature contract.
    Do not change this signature — the dashboard depends on it exactly as defined.
    """
    raise NotImplementedError("This is the abstract interface. Import from mock_chatbot or custom teammate module.")
