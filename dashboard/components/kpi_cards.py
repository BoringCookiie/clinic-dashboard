"""
KPI Card Component Renderer for Streamlit.
"""

import streamlit as st


def render_kpi_card(title: str, value: str, subtitle: str = "") -> None:
    """
    Renders a styled KPI card using HTML container.
    """
    st.markdown(
        f"""
        <div class="kpi-card">
            <div class="kpi-title">{title}</div>
            <div class="kpi-value">{value}</div>
            {f'<div class="kpi-subtitle">{subtitle}</div>' if subtitle else ''}
        </div>
        """,
        unsafe_allow_html=True
    )


def render_kpi_grid(metrics: list[dict[str, str]]) -> None:
    """
    Renders a responsive grid of KPI cards.
    metrics = [{"title": "...", "value": "...", "subtitle": "..."}, ...]
    """
    if not metrics:
        return
    
    cols = st.columns(len(metrics))
    for col, m in zip(cols, metrics):
        with col:
            render_kpi_card(
                title=m.get("title", ""),
                value=m.get("value", ""),
                subtitle=m.get("subtitle", "")
            )


def render_kpi_from_response(data: list[dict]) -> None:
    """
    Renders KPI card specifically from ChatbotResponse data structure.
    Expected data shape: [{"label": "...", "value": "..."}]
    """
    if not data:
        st.warning("No metric data provided for KPI card.")
        return
    
    for item in data:
        label = item.get("label", item.get("title", "Metric"))
        val = item.get("value", item.get("val", "N/A"))
        render_kpi_card(title=str(label), value=str(val))
