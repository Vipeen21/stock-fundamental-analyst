from __future__ import annotations

from datetime import datetime

import altair as alt
import pandas as pd
import streamlit as st

from .config import LOOKBACK_DAYS
from .models import DocItem, ResearchSummary


def fmt_date(dt: datetime | None) -> str:
    return dt.strftime("%d %b %Y") if dt else "Date not clearly available"


def render_metric_row(docs: list[DocItem]) -> None:
    total = len(docs)
    financial = sum(1 for d in docs if d.category == "financial_results")
    presentation = sum(1 for d in docs if d.category == "investor_presentation")
    transcript = sum(1 for d in docs if d.category == "transcript")
    updates = sum(1 for d in docs if d.category in {"business_update", "corporate_action"})
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Documents", total)
    c2.metric("Results", financial)
    c3.metric("Presentations / transcripts", presentation + transcript)
    c4.metric("Corporate updates", updates)


def documents_chart(docs: list[DocItem]) -> tuple[alt.Chart, alt.Chart]:
    df = pd.DataFrame(
        [
            {"date": d.date, "category": d.category}
            for d in docs
            if d.date is not None
        ]
    )

    if df.empty:
        empty = alt.Chart(pd.DataFrame({"x": [], "y": []})).mark_bar()
        return empty, empty

    df["month"] = pd.to_datetime(df["date"]).dt.to_period("M").astype(str)

    monthly = df.groupby("month").size().reset_index(name="count")
    cats = df.groupby("category").size().reset_index(name="count")

    bar = (
        alt.Chart(monthly)
        .mark_bar()
        .encode(
            x=alt.X("month:N", title="Month"),
            y=alt.Y("count:Q", title="Documents"),
            tooltip=["month", "count"],
        )
        .properties(height=280, title="Documents by month")
    )

    pie = (
        alt.Chart(cats)
        .mark_arc(innerRadius=40)
        .encode(
            theta=alt.Theta("count:Q"),
            color=alt.Color("category:N", title="Category"),
            tooltip=["category", "count"],
        )
        .properties(height=280, title="Documents by category")
    )

    return bar, pie


def render_documents_table(docs: list[DocItem]) -> None:
    rows = []
    for d in docs:
        rows.append(
            {
                "Date": fmt_date(d.date),
                "Category": d.category,
                "Title": d.title,
                "Source": d.source_page,
                "Download link": d.url,
            }
        )
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def render_summary(summary: ResearchSummary) -> None:
    st.subheader("AI Research Summary")
    st.markdown(f"**Company:** {summary.company}")
    st.markdown(f"**Period covered:** {summary.period_covered}")

    tabs = st.tabs(
        [
            "Executive summary",
            "Financial snapshot",
            "Management / strategy",
            "Corporate updates",
            "Positives",
            "Risks",
            "Watchlist",
            "Source map",
        ]
    )

    with tabs[0]:
        st.write(summary.executive_summary)

    with tabs[1]:
        for item in summary.financial_snapshot:
            st.markdown(f"- {item}")

    with tabs[2]:
        for item in summary.management_and_strategy:
            st.markdown(f"- {item}")

    with tabs[3]:
        for item in summary.corporate_actions_and_updates:
            st.markdown(f"- {item}")

    with tabs[4]:
        for item in summary.positives:
            st.markdown(f"- {item}")

    with tabs[5]:
        for item in summary.risks:
            st.markdown(f"- {item}")

    with tabs[6]:
        for item in summary.watchlist_next_90_days:
            st.markdown(f"- {item}")

    with tabs[7]:
        for item in summary.source_map:
            st.markdown(f"- **{item.doc_id}** — {item.takeaway}")


def download_summary_markdown(summary: ResearchSummary) -> str:
    lines = [
        f"# {summary.company}",
        "",
        f"**Period covered:** {summary.period_covered}",
        "",
        "## Executive summary",
        summary.executive_summary,
        "",
    ]
    sections = [
        ("Financial snapshot", summary.financial_snapshot),
        ("Management / strategy", summary.management_and_strategy),
        ("Corporate updates", summary.corporate_actions_and_updates),
        ("Positives", summary.positives),
        ("Risks", summary.risks),
        ("Watchlist", summary.watchlist_next_90_days),
    ]
    for title, items in sections:
        lines.append(f"## {title}")
        lines.extend([f"- {item}" for item in items])
        lines.append("")
    return "\n".join(lines)
