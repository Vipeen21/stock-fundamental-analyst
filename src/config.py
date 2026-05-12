from dataclasses import dataclass

NSE_HOME = "https://www.nseindia.com/"
ANNOUNCEMENTS_URL = "https://www.nseindia.com/companies-listing/corporate-filings-announcements"
RESULTS_URL = "https://www.nseindia.com/companies-listing/corporate-filings-financial-results"

LOOKBACK_DAYS = 120
MAX_DOCUMENTS_FOR_SUMMARY = 8
MAX_PDF_PAGES = 25
MAX_CHARS_PER_DOCUMENT = 14000

ALLOWED_HOSTS = {
    "nseindia.com",
    "www.nseindia.com",
    "nsearchives.nseindia.com",
}

KEYWORDS = [
    "financial results",
    "investor presentation",
    "transcript",
    "earnings call",
    "conference call",
    "new order",
    "order",
    "capex",
    "capacity expansion",
    "merger",
    "demerger",
    "acquisition",
    "sell-off",
    "divestment",
    "disinvestment",
    "sale of stake",
    "strategic update",
    "business update",
]
