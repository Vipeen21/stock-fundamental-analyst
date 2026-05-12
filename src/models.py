from datetime import datetime
from pydantic import BaseModel, Field


class DocItem(BaseModel):
    title: str
    date: datetime | None = None
    category: str
    url: str
    source_page: str
    snippet: str = ""


class SourceTakeaway(BaseModel):
    doc_id: str
    takeaway: str


class ResearchSummary(BaseModel):
    company: str = Field(..., description="Company ticker or name")
    period_covered: str
    executive_summary: str
    financial_snapshot: list[str]
    management_and_strategy: list[str]
    corporate_actions_and_updates: list[str]
    positives: list[str]
    risks: list[str]
    watchlist_next_90_days: list[str]
    source_map: list[SourceTakeaway]
