"""LLM structured extraction. One call per deal.

Strictness on two things:
    1. Refuse-on-uncertainty — null beats a hallucinated number.
    2. Unit normalization in the prompt, not after — the model sees the
       surrounding context that disambiguates "$1.2".
"""

from __future__ import annotations

from anthropic import Anthropic

from comps.core.config import settings
from comps.core.logging import get
from comps.core.models import DealFields

log = get(__name__)


EXTRACT_PROMPT = """You are extracting structured fields from a financial document.

Rules:
- Return only fields you can support with explicit text from the document.
- Leave fields null when uncertain — do not guess.
- Normalize all currency to absolute USD (a $1.2B deal -> 1200000000).
- For percentages, use decimal (15% -> 0.15).
- Sector: use 6-digit GICS sub-industry codes where possible.
- Thesis: 2-4 sentences max, plain prose, in the buyer's framing if stated.
- Region: NA, EU, APAC, LATAM, or MEA. Map countries to regions yourself.
- Dates: ISO YYYY-MM-DD, never partial.
- If document is silent on a field, the field is null. Do not infer from
  general knowledge about the companies.
"""


_TOOL_SCHEMA = {
    "name": "record_deal",
    "description": "Record extracted deal fields.",
    "input_schema": DealFields.model_json_schema(),
}


def _client() -> Anthropic:
    return Anthropic(api_key=settings().anthropic_api_key or None)


def extract(text: str) -> DealFields:
    """Single LLM call -> DealFields. Truncates input at config limit.

    Caller is responsible for caching on sha256(source_text) — re-ingest
    should be free.
    """
    cfg = settings()
    truncated = text[: cfg.ingest_max_extract_chars]
    msg = _client().messages.create(
        model=cfg.anthropic_model,
        max_tokens=2000,
        system=[
            {
                "type": "text",
                "text": EXTRACT_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": truncated}],
        tools=[_TOOL_SCHEMA],
        tool_choice={"type": "tool", "name": "record_deal"},
    )

    for block in msg.content:
        if getattr(block, "type", None) == "tool_use" and block.name == "record_deal":
            return DealFields.model_validate(block.input)

    raise RuntimeError("model did not return a record_deal tool call")
