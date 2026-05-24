"""FastAPI surface. Two main endpoints: /search (NL) and /similar-to/{deal_id}.

Latency budget per /search call:
    ~80ms understand · 30ms embed · 60ms SQL · 120ms rerank · 50ms format
    ~340ms p50, well under 1s p95.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException

from comps.core.config import settings
from comps.core.logging import configure, get
from comps.core.models import DealResult, ParsedQuery
from comps.db import queries
from comps.db.pool import close_pool, get_pool
from comps.ingest.embed import embed_query
from comps.search.rerank import Candidate, rerank
from comps.search.retrieve import dedupe_by_deal, hybrid_search
from comps.search.understand import understand

log = get(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure()
    pool = get_pool()
    await pool.open()
    log.info("api ready")
    yield
    await close_pool()


app = FastAPI(title="comps", lifespan=lifespan)


def _deal_year(deal: dict[str, Any]) -> int | None:
    a = deal.get("announced_on")
    if a is None:
        return None
    try:
        return int(a.year)
    except AttributeError:
        return None


def _to_result(deal_id: int, score: float, deal: dict[str, Any], why: str = "") -> DealResult:
    return DealResult(
        deal_id=deal_id,
        target=deal.get("target_name") or "",
        buyer=deal.get("buyer_name"),
        year=_deal_year(deal),
        sector_gics=deal.get("sector_gics"),
        region=deal.get("region"),
        revenue=_float(deal.get("revenue_usd")),
        ev_usd=_float(deal.get("ev_usd")),
        ev_revenue_mult=_float(deal.get("ev_revenue_mult")),
        ev_ebitda_mult=_float(deal.get("ev_ebitda_mult")),
        thesis=deal.get("thesis"),
        score=score,
        why=why,
    )


def _float(v: Any) -> float | None:
    if v is None:
        return None
    return float(v)


async def _search_core(nl_query: str, limit: int) -> list[DealResult]:
    parsed: ParsedQuery = await asyncio.to_thread(understand, nl_query)
    q_emb = await asyncio.to_thread(embed_query, parsed.free_text)

    rows = await hybrid_search(q_emb, parsed.free_text, parsed.filters)
    rows = dedupe_by_deal(rows)
    if not rows:
        return []

    deals = await queries.fetch_deals([r.deal_id for r in rows])

    # Build rerank candidates (fetch top-chunk text in parallel).
    async def make_candidate(r):
        top = await queries.fetch_top_chunk_for_deal(r.deal_id)
        return Candidate(
            deal_id=r.deal_id,
            score=r.score,
            deal=deals.get(r.deal_id, {}),
            top_chunk_text=top,
        )

    candidates = await asyncio.gather(*[make_candidate(r) for r in rows])
    candidates = [c for c in candidates if c.deal]

    reranked = await asyncio.to_thread(rerank, nl_query, candidates, limit)
    return [_to_result(c.deal_id, c.score, c.deal) for c in reranked]


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/search")
async def search(q: str, limit: int = 10) -> list[DealResult]:
    if not q.strip():
        raise HTTPException(400, "empty query")
    return await _search_core(q, limit)


@app.get("/similar-to/{deal_id}")
async def similar_to(deal_id: int, limit: int = 10) -> list[DealResult]:
    """Use the deal's own thesis text as the query."""
    deal = await queries.fetch_deal(deal_id)
    if not deal:
        raise HTTPException(404, f"deal {deal_id} not found")
    seed_text = deal.get("thesis") or deal.get("target_name") or ""
    if not seed_text:
        raise HTTPException(422, f"deal {deal_id} has no text to seed similarity")
    results = await _search_core(seed_text, limit + 1)
    # Drop the seed deal itself.
    return [r for r in results if r.deal_id != deal_id][:limit]


@app.get("/deals/{deal_id}")
async def get_deal(deal_id: int) -> dict[str, Any]:
    deal = await queries.fetch_deal(deal_id)
    if not deal:
        raise HTTPException(404, f"deal {deal_id} not found")
    # Stringify dates/decimals for the JSON layer.
    return {
        k: (str(v) if not isinstance(v, (int, float, str, bool, type(None), dict, list)) else v)
        for k, v in deal.items()
    }


def run() -> None:
    cfg = settings()
    configure()
    uvicorn.run(
        "comps.search.service:app",
        host=cfg.comps_api_host,
        port=cfg.comps_api_port,
        reload=False,
    )


if __name__ == "__main__":
    run()
