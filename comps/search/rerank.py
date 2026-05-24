"""Cross-encoder rerank. Snippet = name + year + thesis + best chunk text.

The reranker sees a coherent paragraph, not a fragment.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import voyageai

from comps.core.config import settings


@dataclass
class Candidate:
    deal_id: int
    score: float
    deal: dict[str, Any]
    top_chunk_text: str | None

    def snippet(self) -> str:
        d = self.deal
        target = d.get("target_name") or ""
        year = ""
        a = d.get("announced_on")
        if a is not None:
            try:
                year = f" ({a.year})"
            except AttributeError:
                year = f" ({str(a)[:4]})"
        thesis = d.get("thesis") or ""
        chunk = self.top_chunk_text or ""
        return f"{target}{year} — {thesis}\n\n{chunk}".strip()


def _client() -> voyageai.Client:
    return voyageai.Client(api_key=settings().voyage_api_key or None)


def rerank(query: str, candidates: list[Candidate], top_k: int | None = None) -> list[Candidate]:
    cfg = settings()
    if not candidates:
        return []
    k = top_k or cfg.search_rerank_topk
    docs = [c.snippet() for c in candidates]
    r = _client().rerank(
        query=query,
        documents=docs,
        model=cfg.voyage_rerank_model,
        top_k=min(k, len(candidates)),
    )
    return [candidates[res.index] for res in r.results]
