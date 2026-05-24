"""LLM structured extraction. One call per deal.

Talks to any OpenAI-compatible endpoint (Venice, OpenAI, vLLM, etc.). The
model is configured via LLM_MODEL — for Venice-routed Claude this is e.g.
"claude-sonnet-4-6".

Strictness on two things:
    1. Refuse-on-uncertainty — null beats a hallucinated number.
    2. Unit normalization in the prompt, not after — the model sees the
       surrounding context that disambiguates "$1.2".
"""

from __future__ import annotations

import json

from openai import OpenAI

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

You MUST call the record_deal function with your extracted values.
"""


_TOOL = {
    "type": "function",
    "function": {
        "name": "record_deal",
        "description": "Record extracted deal fields.",
        "parameters": DealFields.model_json_schema(),
    },
}


def _client() -> OpenAI:
    cfg = settings()
    return OpenAI(api_key=cfg.llm_api_key or "dummy", base_url=cfg.llm_base_url)


def extract(text: str) -> DealFields:
    """Single LLM call -> DealFields. Truncates input at config limit.

    Caller is responsible for caching on sha256(source_text) — re-ingest
    should be free.
    """
    cfg = settings()
    truncated = text[: cfg.ingest_max_extract_chars]
    resp = _client().chat.completions.create(
        model=cfg.llm_model,
        max_tokens=2000,
        messages=[
            {"role": "system", "content": EXTRACT_PROMPT},
            {"role": "user", "content": truncated},
        ],
        tools=[_TOOL],
        tool_choice={"type": "function", "function": {"name": "record_deal"}},
    )

    msg = resp.choices[0].message
    if not msg.tool_calls:
        raise RuntimeError("model did not return a record_deal tool call")

    call = msg.tool_calls[0]
    args = call.function.arguments
    payload = json.loads(args) if isinstance(args, str) else args
    return DealFields.model_validate(payload)
