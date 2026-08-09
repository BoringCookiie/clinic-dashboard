# Chatbot Integration Guide & Teammate Onboarding

Welcome! This folder contains the contract and mock implementation for the Natural Language Chatbot component of the Smart Clinic Dashboard.

---

## 🤝 The Contract: `get_answer()`

The dashboard and chatbot communicate through a single function contract defined in [`interface.py`](file:///c:/Users/aicha/Documents/01_Studies/projects/stage/clinic-project/chatbot/interface.py):

```python
def get_answer(question: str) -> ChatbotResponse:
```

### Input
- `question` (`str`): The natural language query entered by the user in the dashboard text input (e.g., `"How many diabetes patients visited last month?"`).

### Output Structure (`ChatbotResponse`)
Your implementation MUST return a dictionary adhering strictly to the `ChatbotResponse` shape:

```python
class ChatbotResponse(TypedDict):
    answer_text: str                 # Short natural-language answer, e.g. "You had 214 diabetes patients this month."
    chart_type: Literal["kpi", "bar", "line", "pie", "table", "none"]
    data: list[dict[str, Any]]       # Structured data to visualize, e.g. [{"month": "Jan", "count": 34}]
    columns: list[str] | None        # Optional: column names for table/chart axes
    sql_query: str | None            # Optional: the exact SQL query generated/executed (for transparency)
    error: str | None                # Optional: error message if question couldn't be processed
```

#### Supported `chart_type` Options:
- **`"kpi"`**: Displays a single large metric card. Expects `data=[{"label": "...", "value": "..."}]`.
- **`"bar"`**: Displays a Plotly bar chart. Uses `columns` or first 2 dictionary keys as `(x, y)`.
- **`"line"`**: Displays a Plotly line chart over time (e.g., monthly trend).
- **`"pie"`**: Displays a Plotly pie chart (e.g., breakdown by category/department).
- **`"table"`**: Displays an interactive pandas data table.
- **`"none"`**: Displays only `answer_text` (and `error` / `sql_query` if present).

---

## ⚠️ Important Rules

1. **DO NOT MODIFY [`interface.py`](file:///c:/Users/aicha/Documents/01_Studies/projects/stage/clinic-project/chatbot/interface.py)**. The dashboard depends on this exact function signature and dictionary structure.
2. **Create your own implementation file** (e.g. `chatbot/nl_to_sql_chatbot.py`) inside the `chatbot/` folder. Feel free to add supporting modules, LLM prompts, parser utilities, or vector indices in this directory.

---

## 🚀 Step-by-Step Handover Workflow

### Step 1: Create your real implementation
Create `chatbot/nl_to_sql_chatbot.py` and implement `get_answer(question: str) -> ChatbotResponse`:

```python
# chatbot/nl_to_sql_chatbot.py
from chatbot.interface import ChatbotResponse

def get_answer(question: str) -> ChatbotResponse:
    # 1. Convert question to SQL using your LLM / NL-to-SQL logic
    # 2. Execute SQL against data/clinic.db (use database.db_utils.run_raw_query)
    # 3. Format response as ChatbotResponse
    return ChatbotResponse(...)
```

### Step 2: Validate against the contract test suite
Run the generic test suite to ensure your function returns valid data shapes without breaking the dashboard:

```bash
pytest tests/test_dashboard_contract.py
```

*Note: You can pass your custom module into the test suite or swap the import as shown in Step 3.*

### Step 3: Connect your chatbot to the Dashboard
Open [`dashboard/app.py`](file:///c:/Users/aicha/Documents/01_Studies/projects/stage/clinic-project/dashboard/app.py) and update the single import line at the top:

```python
# BEFORE (Mock Implementation):
from chatbot.mock_chatbot import get_answer

# AFTER (Your Real Implementation):
from chatbot.nl_to_sql_chatbot import get_answer
```

Launch Streamlit to test your live chatbot in the UI:

```bash
streamlit run dashboard/app.py
```

---

## 💡 Database Schema Reference

The database is SQLite located at `data/clinic.db`. You can query tables using `database.db_utils.run_raw_query(sql_str)`.
The available tables are:
- `patients`
- `departments`
- `doctors`
- `staff`
- `appointments`
- `visits`
- `diagnoses`
- `medications`
- `prescriptions`
- `lab_tests`
- `billing`
- `payments`

Refer to [`database/schema.py`](file:///c:/Users/aicha/Documents/01_Studies/projects/stage/clinic-project/database/schema.py) for full column definitions and foreign key relationships.
