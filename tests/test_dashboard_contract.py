"""
Generic Dashboard Contract Validation Tests.
Validates that any get_answer(question) implementation returns a valid ChatbotResponse
matching all structural and type requirements expected by the Streamlit dashboard.

Teammates can import validate_chatbot_response or run this test module against their implementation.
"""

import pytest
from typing import Callable, Any
from chatbot.mock_chatbot import get_answer as mock_get_answer

ALLOWED_CHART_TYPES = {"kpi", "bar", "line", "pie", "table", "none"}


def validate_chatbot_response(response: dict[str, Any]) -> None:
    """
    Generic helper function asserting that a response dictionary adheres strictly
    to the ChatbotResponse TypedDict contract.
    """
    assert isinstance(response, dict), "Response must be a dictionary."

    # Check Required Keys
    required_keys = {"answer_text", "chart_type", "data", "columns", "sql_query", "error"}
    assert required_keys.issubset(response.keys()), f"Missing required keys in ChatbotResponse. Required: {required_keys}"

    # Check answer_text
    assert isinstance(response["answer_text"], str), "'answer_text' must be a string."
    assert len(response["answer_text"].strip()) > 0, "'answer_text' cannot be empty."

    # Check chart_type
    chart_type = response["chart_type"]
    assert chart_type in ALLOWED_CHART_TYPES, f"'chart_type' must be one of {ALLOWED_CHART_TYPES}, got '{chart_type}'."

    # Check data
    data = response["data"]
    assert isinstance(data, list), "'data' must be a list of dictionaries."
    for idx, item in enumerate(data):
        assert isinstance(item, dict), f"Element at data[{idx}] must be a dictionary."

    # Check columns
    columns = response["columns"]
    assert columns is None or isinstance(columns, list), "'columns' must be a list of strings or None."
    if isinstance(columns, list):
        for col in columns:
            assert isinstance(col, str), f"Column name '{col}' in columns must be a string."

    # Check sql_query
    sql_query = response["sql_query"]
    assert sql_query is None or isinstance(sql_query, str), "'sql_query' must be a string or None."

    # Check error
    error = response["error"]
    assert error is None or isinstance(error, str), "'error' must be a string or None."


# List of sample questions to test
SAMPLE_TEST_QUESTIONS = [
    "How many patients are registered in the clinic?",
    "Show appointments by month",
    "What are the top diagnoses?",
    "What is our revenue status?",
    "Show doctors by department",
    "Show pending invoices",
    "What is the average flight speed of an unladen swallow?"  # Fallback case
]


@pytest.mark.parametrize("question", SAMPLE_TEST_QUESTIONS)
def test_mock_chatbot_contract(question: str):
    """Tests mock_chatbot implementation against contract validator."""
    response = mock_get_answer(question)
    validate_chatbot_response(response)


def test_custom_chatbot_implementation_contract(custom_get_answer_fn: Callable[[str], dict] = None):
    """
    Helper test allowing teammates to test their custom chatbot function.
    Usage: Call this function passing custom_get_answer_fn, or run pytest directly.
    """
    fn_to_test = custom_get_answer_fn or mock_get_answer
    for q in SAMPLE_TEST_QUESTIONS:
        resp = fn_to_test(q)
        validate_chatbot_response(resp)
