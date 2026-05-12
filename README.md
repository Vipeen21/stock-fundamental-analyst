# Stock Filing Analyst Pro

A production-style Streamlit app that:
- takes an NSE ticker,
- fetches only official NSE filings and archive links,
- reads financial results, investor presentations, transcripts, and updates,
- summarizes the last four months in a professional research style,
- shows charts, tabs, and original download links.

## Why this version is better

- cleaner folder structure
- Docker support
- deployment config
- better error handling
- structured Gemini summaries
- charts and tabs for readability

## Run locally

```bash
pip install -r requirements.txt
export GEMINI_API_KEY="your_key"
streamlit run app.py
```

## Docker

```bash
docker build -t stock-analyst-pro .
docker run -p 8501:8501 --env-file .env nse-analyst-pro
```

## Deployment

Use the included `render.yaml` or adapt the same start command for another host.

## Safety

Keep the API key in environment variables or secret storage. Do not hardcode it in the app.
