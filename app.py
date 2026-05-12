from __future__ import annotations

import streamlit as st

from src.config import LOOKBACK_DAYS
from src.nse_client import build_analysis_context, docs_to_dataframe, fetch_documents
from src.summarizer import summarize_documents
from src.ui import documents_chart, download_summary_markdown, render_documents_table, render_metric_row, render_summary


st.set_page_config(
    page_title="Stock Filing Analyst Pro",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("Stock Filing Analyst Pro")
st.caption("Official NSE and NSE archive links only. No company investor-relations pages.")

with st.sidebar:
    st.header("Search")
    symbol = st.text_input("NSE ticker", value="SBIN").strip().upper()
    st.write(f"Look-back window: {LOOKBACK_DAYS} days")
    build = st.button("Build report", type="primary")
    st.divider()
    st.write("Built for official NSE corporate filings, financial results, presentations, and transcripts.")

if build:
    if not symbol:
        st.error("Please type a ticker.")
        st.stop()

    with st.spinner("Fetching NSE filings..."):
        try:
            docs = fetch_documents(symbol)
        except Exception as exc:
            st.error(f"Could not fetch filings for {symbol}.")
            st.exception(exc)
            st.stop()

    if not docs:
        st.warning("No relevant documents found in the last four months.")
        st.stop()

    render_metric_row(docs)

    chart_left, chart_right = st.columns(2)
    bar_chart, cat_chart = documents_chart(docs)
    with chart_left:
        st.altair_chart(bar_chart, use_container_width=True)
    with chart_right:
        st.altair_chart(cat_chart, use_container_width=True)

    top_tabs = st.tabs(["Summary", "Documents", "Timeline", "Raw data"])

    with top_tabs[0]:
        st.subheader("Original NSE download links")
        for idx, doc in enumerate(docs[:8], start=1):
            with st.expander(f"{idx}. {doc.title}"):
                st.markdown(f"**Date:** {doc.date.strftime('%d %b %Y') if doc.date else 'Not clearly available'}")
                st.markdown(f"**Category:** {doc.category}")
                st.markdown(f"**Source page:** {doc.source_page}")
                st.markdown(f"[Download original file]({doc.url})")
                if doc.snippet:
                    st.caption(doc.snippet)

        with st.spinner("Preparing AI summary..."):
            ctx = build_analysis_context(docs)
            try:
                summary = summarize_documents(symbol, ctx)
                render_summary(summary)

                md = download_summary_markdown(summary)
                st.download_button(
                    "Download summary as Markdown",
                    data=md.encode("utf-8"),
                    file_name=f"{symbol}_NSE_research_summary.md",
                    mime="text/markdown",
                )
            except Exception as exc:
                st.error("AI summary could not be generated.")
                st.exception(exc)

    with top_tabs[1]:
        render_documents_table(docs)

    with top_tabs[2]:
        timeline_df = docs_to_dataframe(docs)
        timeline_df = timeline_df[timeline_df["date"].notna()].copy()
        if timeline_df.empty:
            st.info("No dated items available for a timeline.")
        else:
            timeline_df = timeline_df.sort_values("date", ascending=False)
            st.dataframe(timeline_df[["date", "category", "title", "url"]], use_container_width=True, hide_index=True)

    with top_tabs[3]:
        st.json(
            [
                {
                    "title": d.title,
                    "date": d.date.isoformat() if d.date else None,
                    "category": d.category,
                    "url": d.url,
                    "source_page": d.source_page,
                }
                for d in docs[:8]
            ]
        )
