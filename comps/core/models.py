"""Pydantic models shared by ingest, search, and CLI.

Two extraction-time invariants enforced here:
    1. Currency normalized to USD millions (callers must not pass raw strings).
    2. Percentages stored as decimals (15% -> 0.15).
"""

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

BuyerType = Literal["PE", "strategic", "VC", "SPAC"]
DealType = Literal["LBO", "M&A", "minority", "IPO"]
Region = Literal["NA", "EU", "APAC", "LATAM", "MEA"]
Section = Literal["thesis", "mdna", "risks", "financials", "other"]


class DealFields(BaseModel):
    """LLM-extracted fields for a single deal. Null beats a guess."""

    target_name: str
    target_ticker: str | None = None
    buyer_name: str | None = None
    buyer_type: BuyerType | None = Field(
        default=None, description="PE, strategic, VC, SPAC, or null"
    )
    deal_type: DealType | None = None
    sector_gics: str | None = Field(default=None, description="6-digit GICS sub-industry code")
    sub_sector: str | None = None
    country: str | None = Field(default=None, description="ISO-3166-1 alpha-2")
    region: Region | None = None
    announced_on: date | None = None
    closed_on: date | None = None
    revenue_usd: float | None = Field(default=None, description="Revenue in absolute USD")
    ebitda_usd: float | None = None
    ebitda_margin: float | None = Field(default=None, description="Decimal, e.g. 0.22 for 22%")
    ev_usd: float | None = None
    ev_revenue_mult: float | None = None
    ev_ebitda_mult: float | None = None
    growth_yoy: float | None = Field(default=None, description="Decimal, e.g. 0.15 for 15%")
    thesis: str = Field(description="2-4 sentence deal rationale, plain prose")


class Chunk(BaseModel):
    """A text chunk slotted into a section, before embedding."""

    section: Section
    ord: int
    text: str
    page: int | None = None
    tokens: int = 0


class ParsedQuery(BaseModel):
    """Output of NL-query understanding."""

    free_text: str
    filters: dict = Field(default_factory=dict)


class FilterSet(BaseModel):
    """Typed view of the filter dict; tolerates partial fills."""

    revenue_band: tuple[float, float] | None = None
    ebitda_band: tuple[float, float] | None = None
    year_band: tuple[int, int] | None = None
    sector_gics: str | None = None
    sub_sector: str | None = None
    region: Region | None = None
    country: str | None = None
    deal_type: DealType | None = None
    buyer_type: BuyerType | None = None


class DealResult(BaseModel):
    """One row in a search response."""

    deal_id: int
    target: str
    buyer: str | None
    year: int | None
    sector_gics: str | None
    region: str | None
    revenue: float | None
    ev_usd: float | None
    ev_revenue_mult: float | None
    ev_ebitda_mult: float | None
    thesis: str | None
    score: float
    why: str = ""
