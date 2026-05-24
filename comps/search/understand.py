"""NL query -> (free_text for embedding) + (typed filters for SQL).

The big hard-coded rule: numeric points become bands. $30M ARR -> [25M, 35M].
LLMs are bad at choosing tolerance themselves; the prompt picks ±~15%.
"""

from __future__ import annotations

import json

from openai import OpenAI

from comps.core.config import settings
from comps.core.logging import get
from comps.core.models import ParsedQuery

log = get(__name__)


UNDERSTAND_PROMPT = """Parse a natural-language search for financial deal comps.

Return a JSON object with two fields:

  "free_text": the semantic core of the query, suitable for embedding-based
               retrieval. Remove numeric ranges, dates, geographies — those
               belong in filters.

  "filters": any of (omit fields the user did not specify):
    revenue_band:    [min_usd, max_usd]     # absolute USD, NOT millions
    ebitda_band:     [min_usd, max_usd]
    year_band:       [yyyy_min, yyyy_max]
    sector_gics:     "string"               # 6-digit GICS code if known
    sub_sector:      "string"
    region:          "NA"|"EU"|"APAC"|"LATAM"|"MEA"
    country:         ISO-3166-1 alpha-2
    deal_type:       "LBO"|"M&A"|"minority"|"IPO"
    buyer_type:      "PE"|"strategic"|"VC"|"SPAC"

Rules:
- Numeric points become bands of roughly ±15%. "$30M ARR" -> [25000000, 35000000].
- Never guess a filter the user didn't clearly state.
- "europe" -> region EU. "germany" -> country DE (+ region EU).
- "PE buyout" -> deal_type LBO, buyer_type PE.
- "ipo" / "S-1" -> deal_type IPO.
- "M&A" or "acquisition by strategic" -> deal_type M&A, buyer_type strategic.

Example
  Input:  "comps for a $30M ARR vertical SaaS PE buyout in europe, 2021-2024"
  Output: {
    "free_text": "vertical SaaS recurring revenue buyout",
    "filters": {
      "revenue_band": [25000000, 35000000],
      "deal_type": "LBO",
      "buyer_type": "PE",
      "region": "EU",
      "year_band": [2021, 2024]
    }
  }

Return ONLY the JSON object, no prose.
"""


def _client() -> OpenAI:
    cfg = settings()
    return OpenAI(api_key=cfg.llm_api_key or "dummy", base_url=cfg.llm_base_url)


def understand(query: str) -> ParsedQuery:
    cfg = settings()
    resp = _client().chat.completions.create(
        model=cfg.llm_model,
        max_tokens=400,
        messages=[
            {"role": "system", "content": UNDERSTAND_PROMPT},
            {"role": "user", "content": query},
        ],
        response_format={"type": "json_object"},
    )
    text = (resp.choices[0].message.content or "").strip().strip("`")
    if text.startswith("json"):
        text = text[4:].lstrip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        log.warning("understand: model returned non-JSON, falling back to raw query")
        return ParsedQuery(free_text=query, filters={})

    return ParsedQuery(
        free_text=data.get("free_text", query),
        filters=data.get("filters", {}) or {},
    )
