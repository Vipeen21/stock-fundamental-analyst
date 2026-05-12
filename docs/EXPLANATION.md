# How this app works

This is the plain-English guide to the code.

## Big picture

The app has four jobs:

1. Ask for an NSE ticker.
2. Fetch only official NSE links for filings.
3. Read the linked PDFs / pages.
4. Ask Gemini to write a professional analyst summary.

## Folder structure

- `app.py` — the Streamlit app entry point.
- `src/config.py` — settings and constants.
- `src/models.py` — data shapes.
- `src/nse_client.py` — NSE scraping and PDF text extraction.
- `src/summarizer.py` — Gemini summary generation.
- `src/ui.py` — charts, tabs, tables, download output.
- `Dockerfile` — container build file.
- `render.yaml` — Render deployment config.
- `.streamlit/config.toml` — Streamlit theme and server settings.

## Execution flow

### 1. `app.py`
This file starts the page, shows the sidebar, and waits for the user to click **Build report**.

### 2. `fetch_documents(symbol)`
This function:
- opens the official NSE announcements page,
- opens the official NSE financial results page,
- reads the HTML tables,
- keeps only links from NSE / NSE archive domains,
- filters to the last 120 days,
- ranks the best documents first.

### 3. `build_analysis_context(docs)`
This function downloads the top documents and extracts text from PDFs so the model can read them.

### 4. `summarize_documents(symbol, ctx)`
This sends the extracted text to the Gemini API.
The model returns a structured research note with:
- executive summary,
- financial snapshot,
- strategy commentary,
- corporate actions,
- positives,
- risks,
- watchlist,
- source mapping.

### 5. `render_summary(summary)`
This shows the final answer in tabs so it looks like a clean analyst dashboard.

## Line-by-line guide for the main file

### `app.py`
- `st.set_page_config(...)` sets the browser tab title and page layout.
- `symbol = st.text_input(...)` gets the NSE ticker from the user.
- `build = st.button(...)` starts the search.
- `docs = fetch_documents(symbol)` gets the official NSE documents.
- `bar_chart, cat_chart = documents_chart(docs)` builds the charts.
- `ctx = build_analysis_context(docs)` extracts text for the model.
- `summary = summarize_documents(symbol, ctx)` asks Gemini to generate the report.
- `st.download_button(...)` lets the user save the final summary.

### `src/nse_client.py`
- `safe_get(...)` does web requests with retry behavior.
- `extract_rows_from_html(...)` finds tables and links.
- `rows_to_docs(...)` converts rows into clean document objects.
- `fetch_documents(...)` combines announcements and results, then sorts them.
- `extract_pdf_text_from_url(...)` reads PDF text from NSE links.

### `src/summarizer.py`
- `SYSTEM_PROMPT` tells the model to act like a senior analyst.
- `client.responses.parse(...)` asks for structured output.
- `ResearchSummary` defines the exact shape of the answer.

## How to run it locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## How to run it in Docker

```bash
docker build -t nse-analyst-pro .
docker run -p 8501:8501 --env-file .env nse-analyst-pro
```

## Important note

This app uses only official NSE and NSE archive links, but NSE pages sometimes change their HTML or block automated requests. If that happens, the fetching code may need a small refresh.
