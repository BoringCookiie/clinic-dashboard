"""
Plotly Chart Rendering Module for Streamlit Dashboard.
Supports bar, line, pie, and tabular visual layouts.
"""

from typing import Any, Optional
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from dashboard.components.kpi_cards import render_kpi_from_response

# Custom color palette for dark-mode glassmorphism theme
COLOR_PALETTE = ["#38bdf8", "#818cf8", "#34d399", "#f43f5e", "#fbbf24", "#a78bfa", "#f472b6", "#382bf8"]


def render_chart_response(
    chart_type: str,
    data: list[dict[str, Any]],
    columns: Optional[list[str]] = None
) -> None:
    """
    Dispatcher function to render the appropriate chart component based on chart_type.
    """
    if chart_type == "none" or not data:
        return

    if chart_type == "kpi":
        render_kpi_from_response(data)
        return

    df = pd.DataFrame(data)
    if df.empty:
        st.info("No data available to display chart.")
        return

    if chart_type == "bar":
        render_bar_chart(df, columns)
    elif chart_type == "line":
        render_line_chart(df, columns)
    elif chart_type == "pie":
        render_pie_chart(df, columns)
    elif chart_type == "table":
        render_table(df, columns)
    else:
        st.warning(f"Unrecognized chart type: '{chart_type}'. Displaying table view.")
        render_table(df, columns)


def render_bar_chart(df: pd.DataFrame, columns: Optional[list[str]] = None) -> None:
    """
    Renders a Plotly Bar Chart.
    """
    cols = columns or list(df.columns)
    x_col = cols[0] if len(cols) > 0 else df.columns[0]
    y_col = cols[1] if len(cols) > 1 else df.columns[1]

    fig = px.bar(
        df,
        x=x_col,
        y=y_col,
        color_discrete_sequence=[COLOR_PALETTE[0]],
        text_auto=True,
        template="plotly_dark"
    )
    
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, sans-serif", color="#f8fafc"),
        margin=dict(l=20, r=20, t=30, b=20),
        xaxis_title=x_col.replace("_", " ").title(),
        yaxis_title=y_col.replace("_", " ").title(),
        height=380
    )
    st.plotly_chart(fig, use_container_width=True)


def render_line_chart(df: pd.DataFrame, columns: Optional[list[str]] = None) -> None:
    """
    Renders a Plotly Line Chart.
    """
    cols = columns or list(df.columns)
    x_col = cols[0] if len(cols) > 0 else df.columns[0]
    y_col = cols[1] if len(cols) > 1 else df.columns[1]

    fig = px.line(
        df,
        x=x_col,
        y=y_col,
        markers=True,
        line_shape="linear",
        color_discrete_sequence=[COLOR_PALETTE[1]],
        template="plotly_dark"
    )
    
    fig.update_traces(line=dict(width=3), marker=dict(size=8))
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, sans-serif", color="#f8fafc"),
        margin=dict(l=20, r=20, t=30, b=20),
        xaxis_title=x_col.replace("_", " ").title(),
        yaxis_title=y_col.replace("_", " ").title(),
        height=380
    )
    st.plotly_chart(fig, use_container_width=True)


def render_pie_chart(df: pd.DataFrame, columns: Optional[list[str]] = None) -> None:
    """
    Renders a Plotly Pie/Donut Chart.
    """
    cols = columns or list(df.columns)
    names_col = cols[0] if len(cols) > 0 else df.columns[0]
    values_col = cols[1] if len(cols) > 1 else df.columns[1]

    fig = px.pie(
        df,
        names=names_col,
        values=values_col,
        hole=0.4,
        color_discrete_sequence=COLOR_PALETTE,
        template="plotly_dark"
    )
    
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, sans-serif", color="#f8fafc"),
        margin=dict(l=20, r=20, t=30, b=20),
        height=380
    )
    st.plotly_chart(fig, use_container_width=True)


def render_table(df: pd.DataFrame, columns: Optional[list[str]] = None) -> None:
    """
    Renders an interactive DataFrame view in Streamlit.
    """
    if columns:
        valid_cols = [c for c in columns if c in df.columns]
        if valid_cols:
            df = df[valid_cols]
            
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True
    )
