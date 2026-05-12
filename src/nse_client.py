from __future__ import annotations

import io
import re
from datetime import datetime, timedelta
from typing import Iterable
from urllib.parse import urljoin, urlparse

import pandas as pd
import requests
from bs4 import BeautifulSoup
from dateutil import parser as date_parser
from pypdf import PdfReader

from .config import (
    ALLOWED_HOSTS,
    ANNOUNCEMENTS_URL,
    KEYWORDS,
    LOOKBACK_DAYS,
    MAX_CHARS_PER_DOCUMENT,
    MAX_DOCUMENTS_FOR_SUMMARY,
    MAX_PDF_PAGES,
    NSE_HOME,
    RESULTS_URL,
)
from .models import DocItem


def _build_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/147.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Connection": "keep-alive",
            "Referer": NSE_HOME,
        }
    )
    return session


SESSION = _build_session()


def bootstrap_nse_session() -> None:
    try:
        SESSION.get(NSE_HOME, timeout=20)
    except Exception:
        pass


def safe_get(url: str, params: dict | None = None) -> requests.Response:
    bootstrap_nse_session()
    response = SESSION.get(url, params=params, timeout=30)
    if response.status_code in (401, 403):
        bootstrap_nse_session()
        response = SESSION.get(url, params=params, timeout=30)
    response.raise_for_status()
    return response


def allowed_url(url: str) -> bool:
    host = urlparse(url).netloc.lower()
    return host in ALLOWED_HOSTS


def normalize_url(href: str) -> str:
    return urljoin(NSE_HOME, href)


def parse_date(value) -> datetime | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return None
    for fmt in ("%d%m%Y%H%M%S", "%Y-%m-%d %H:%M:%S", "%d-%b-%Y %H:%M:%S", "%d-%b-%Y %H:%M"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            pass
    try:
        return date_parser.parse(text, fuzzy=True, dayfirst=True)
    except Exception:
        return None


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def is_relevant_text(text: str) -> bool:
    t = (text or "").lower()
    return any(k in t for k in KEYWORDS)


def pick_best_link(links: list[str]) -> str:
    if not links:
        return ""
    pdf_links = [u for u in links if u.lower().endswith(".pdf")]
    if pdf_links:
        return pdf_links[0]
    archive_links = [u for u in links if "nsearchives.nseindia.com" in u]
    if archive_links:
        return archive_links[0]
    return links[0]


def extract_rows_from_html(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    rows = []

    for table in soup.find_all("table"):
        headers = [th.get_text(" ", strip=True) for th in table.find_all("th")]
        if not headers:
            continue

        for tr in table.find_all("tr"):
            tds = tr.find_all("td")
            if not tds:
                continue

            cells = [td.get_text(" ", strip=True) for td in tds]
            links = []
            for a in tr.find_all("a", href=True):
                href = normalize_url(a["href"])
                if allowed_url(href):
                    links.append(href)

            rows.append(
                {
                    "headers": headers,
                    "cells": cells,
                    "links": links,
                    "raw_text": tr.get_text(" ", strip=True),
                }
            )

    return rows


def rows_to_docs(rows: list[dict], source_page: str, page_kind: str) -> list[DocItem]:
    docs: list[DocItem] = []
    cutoff = datetime.now() - timedelta(days=LOOKBACK_DAYS)

    for row in rows:
        headers = [h.lower().strip() for h in row["headers"]]
        cells = row["cells"]
        mapping = {h: (cells[i] if i < len(cells) else "") for i, h in enumerate(headers)}

        title = (
            mapping.get("subject")
            or mapping.get("details")
            or mapping.get("announcement")
            or mapping.get("company name")
            or row["raw_text"]
        )

        date_text = (
            mapping.get("broadcast date/time")
            or mapping.get("date")
            or mapping.get("period ended")
            or mapping.get("for quarter ending")
            or ""
        )
        dt = parse_date(date_text)

        if dt and dt < cutoff:
            continue

        combined = f"{title} {row['raw_text']}"
        relevant = is_relevant_text(combined) or page_kind == "financial_results"
        if not relevant:
            continue

        url = pick_best_link(row["links"])
        if not url:
            continue

        text = combined.lower()
        category = page_kind
        if "transcript" in text:
            category = "transcript"
        elif "investor presentation" in text or "presentation" in text:
            category = "investor_presentation"
        elif "financial results" in text:
            category = "financial_results"
        elif any(k in text for k in ["merger", "demerger", "acquisition", "sell-off", "divestment", "disinvestment"]):
            category = "corporate_action"
        elif any(k in text for k in ["order", "capex", "capacity expansion", "business update"]):
            category = "business_update"

        docs.append(
            DocItem(
                title=str(title).strip(),
                date=dt,
                category=category,
                url=url,
                source_page=source_page,
                snippet=row["raw_text"][:500],
            )
        )

    return docs


def _page_kind_for_url(url: str) -> str:
    if "financial-results" in url:
        return "financial_results"
    if "announcements" in url:
        return "announcement"
    return "other"


def scrape_nse_page(symbol: str, url: str) -> list[DocItem]:
    response = safe_get(url, params={"symbol": symbol, "tabIndex": "equity"})
    rows = extract_rows_from_html(response.text)
    return rows_to_docs(rows, source_page=url, page_kind=_page_kind_for_url(url))


def _json_get(path: str, params: dict) -> list[dict]:
    response = safe_get(normalize_url(path), params=params)
    data = response.json()
    return data if isinstance(data, list) else []


def fetch_announcement_docs(symbol: str) -> list[DocItem]:
    rows = _json_get("/api/corporate-announcements", {"index": "equities", "symbol": symbol})
    docs: list[DocItem] = []

    for row in rows:
        title = normalize_whitespace(str(row.get("desc") or row.get("attchmntText") or "Announcement"))
        text = normalize_whitespace(f"{title} {row.get('attchmntText') or ''}")
        if not is_relevant_text(text):
            continue

        url = str(row.get("attchmntFile") or "").strip()
        if not url or not allowed_url(url):
            continue

        lowered = text.lower()
        category = "announcement"
        if "transcript" in lowered or "earnings call" in lowered or "conference call" in lowered:
            category = "transcript"
        elif "investor presentation" in lowered or "presentation" in lowered:
            category = "investor_presentation"
        elif "financial results" in lowered:
            category = "financial_results"
        elif any(k in lowered for k in ["merger", "demerger", "acquisition", "sell-off", "divestment", "disinvestment"]):
            category = "corporate_action"
        elif any(k in lowered for k in ["order", "capex", "capacity expansion", "business update", "updates"]):
            category = "business_update"

        docs.append(
            DocItem(
                title=title,
                date=parse_date(row.get("sort_date") or row.get("an_dt") or row.get("dt")),
                category=category,
                url=url,
                source_page=ANNOUNCEMENTS_URL,
                snippet=text[:500],
            )
        )

    return docs


def fetch_financial_result_docs(symbol: str) -> list[DocItem]:
    rows = _json_get(
        "/api/corporates-financial-results",
        {"index": "equities", "symbol": symbol, "period": "Quarterly"},
    )
    docs: list[DocItem] = []

    for row in rows:
        title = normalize_whitespace(
            " ".join(
                str(part)
                for part in [
                    row.get("companyName"),
                    row.get("relatingTo"),
                    row.get("period"),
                    row.get("financialYear"),
                    "Financial Results",
                ]
                if part
            )
        )
        url = str(row.get("resultDetailedDataLink") or row.get("xbrl") or "").strip()
        if not url or not allowed_url(url):
            continue

        snippet = normalize_whitespace(
            f"{row.get('audited') or ''} {row.get('consolidated') or ''} "
            f"{row.get('fromDate') or ''} to {row.get('toDate') or ''}"
        )
        docs.append(
            DocItem(
                title=title,
                date=parse_date(row.get("broadCastDate") or row.get("filingDate") or row.get("toDate")),
                category="financial_results",
                url=url,
                source_page=RESULTS_URL,
                snippet=snippet[:500],
            )
        )

    return docs


def dedupe_docs(docs: list[DocItem]) -> list[DocItem]:
    seen: set[tuple[str, str, str]] = set()
    out: list[DocItem] = []
    for d in docs:
        key = (
            d.title.lower().strip(),
            d.url.strip(),
            d.date.date().isoformat() if d.date else "no-date",
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(d)
    return out


def score_doc(doc: DocItem) -> int:
    text = f"{doc.title} {doc.snippet}".lower()
    score = 0
    if doc.date:
        score += 20
        days_old = max((datetime.now() - doc.date).days, 0)
        score += max(30 - min(days_old, 30), 0)

    if "financial results" in text:
        score += 50
    if "investor presentation" in text or "presentation" in text:
        score += 40
    if "transcript" in text or "earnings call" in text or "conference call" in text:
        score += 45
    if any(k in text for k in ["new order", "order", "capex", "merger", "demerger", "acquisition", "divestment", "disinvestment"]):
        score += 35
    return score


def fetch_documents(symbol: str) -> list[DocItem]:
    symbol = symbol.upper().strip()
    docs = []
    docs.extend(fetch_announcement_docs(symbol))
    docs.extend(fetch_financial_result_docs(symbol))

    if not docs:
        docs.extend(scrape_nse_page(symbol, ANNOUNCEMENTS_URL))
        docs.extend(scrape_nse_page(symbol, RESULTS_URL))

    docs = dedupe_docs(docs)
    cutoff = datetime.now() - timedelta(days=LOOKBACK_DAYS)
    docs = [d for d in docs if d.date is None or d.date >= cutoff]
    docs = sorted(docs, key=lambda d: (d.date or datetime.min, score_doc(d)), reverse=True)
    return docs


def extract_pdf_text_from_url(url: str) -> str:
    response = safe_get(url)
    content_type = response.headers.get("content-type", "").lower()

    if "pdf" in content_type or url.lower().endswith(".pdf"):
        reader = PdfReader(io.BytesIO(response.content))
        texts = []
        for page in reader.pages[:MAX_PDF_PAGES]:
            try:
                texts.append(page.extract_text() or "")
            except Exception:
                texts.append("")
        return normalize_whitespace("\n".join(texts))[:MAX_CHARS_PER_DOCUMENT]

    soup = BeautifulSoup(response.text, "html.parser")
    return normalize_whitespace(soup.get_text(" ", strip=True))[:MAX_CHARS_PER_DOCUMENT]


def build_analysis_context(docs: list[DocItem], max_docs: int = MAX_DOCUMENTS_FOR_SUMMARY) -> list[dict]:
    selected = docs[:max_docs]
    context: list[dict] = []
    for idx, doc in enumerate(selected, start=1):
        try:
            text = extract_pdf_text_from_url(doc.url)
        except Exception as e:
            text = f"[Could not extract text: {e}]"

        context.append(
            {
                "doc_id": f"DOC_{idx}",
                "title": doc.title,
                "date": doc.date.isoformat() if doc.date else None,
                "category": doc.category,
                "url": doc.url,
                "source_page": doc.source_page,
                "text": text,
            }
        )
    return context


def docs_to_dataframe(docs: list[DocItem]) -> pd.DataFrame:
    rows = []
    for d in docs:
        rows.append(
            {
                "title": d.title,
                "date": d.date,
                "category": d.category,
                "url": d.url,
                "source_page": d.source_page,
                "snippet": d.snippet,
            }
        )
    return pd.DataFrame(rows)
