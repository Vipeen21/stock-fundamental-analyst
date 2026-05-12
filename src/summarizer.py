from __future__ import annotations

import json
import os

from dotenv import load_dotenv
from google import genai
from google.genai import types

from .models import ResearchSummary


SYSTEM_PROMPT = """
You are a senior sell-side equity research analyst at a top-tier investment firm.

Write a professional, balanced, institution-grade summary using only the supplied NSE documents.
Focus on what changed in the last 4 months. Mention implications for:
- revenue / order intake
- margins
- capex / capacity
- balance sheet
- mergers / demergers / acquisitions / sell-offs
- management commentary
- risks and watchpoints

Rules:
- do not invent facts or numbers
- do not use company IR pages or external sources
- be concise, factual, and analyst-like
- if something is unclear, say it is unclear
- return output in the exact schema requested
"""


load_dotenv()


def _client() -> genai.Client:
    api_key = os.getenv("GEMINI_API_KEY", "").strip().strip('"')
    if not api_key or api_key == "paste_your_gemini_api_key_here":
        raise RuntimeError("GEMINI_API_KEY is missing. Add it to .env or your deployment secrets.")
    return genai.Client(api_key=api_key)


def summarize_documents(symbol: str, doc_context: list[dict]) -> ResearchSummary:
    client = _client()
    model = os.getenv("GEMINI_MODEL", "gemini-3-flash-preview")

    payload = {
        "symbol": symbol,
        "lookback_window_days": 120,
        "instructions": "Summarize only the supplied NSE official documents.",
        "documents": doc_context,
    }

    response = client.models.generate_content(
        model=model,
        contents=json.dumps(payload, ensure_ascii=False),
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            response_mime_type="application/json",
            response_schema=ResearchSummary,
        ),
    )
    text = (response.text or "").strip()
    if not text:
        raise RuntimeError("Gemini returned an empty summary response.")
    return ResearchSummary.model_validate(json.loads(text))
