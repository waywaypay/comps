"""Hybrid retrieval. One SQL query: filters CTE + BM25 CTE + vector CTE + RRF fuse.

No Python round-trip between BM25 and vector. The CTEs run once per request;
the planner can parallelize them.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from comps.core.config import settings
from comps.db.pool import transaction

_HYBRID_SQL = """
with filtered as (
    select id from deals
    where (%(rev_min)s::numeric is null or revenue_usd between %(rev_min)s and %(rev_max)s)
      and (%(eb_min)s::numeric  is null or ebitda_usd  between %(eb_min)s  and %(eb_max)s)
      and (%(sector)s::text     is null or sector_gics = %(sector)s)
      and (%(region)s::text     is null or region      = %(region)s)
      and (%(country)s::text    is null or country     = %(country)s)
      and (%(year_min)s::int    is null
           or (announced_on is not null
               and extract(year from announced_on) between %(year_min)s and %(year_max)s))
      and (%(buyer)s::text      is null or buyer_type = %(buyer)s)
      and (%(deal)s::text       is null or deal_type  = %(deal)s)
),
bm25 as (
    select c.id, c.deal_id,
           row_number() over (order by ts_rank_cd(c.tsv, q) desc) as rnk
    from chunks c
    join filtered f on f.id = c.deal_id,
         plainto_tsquery('english', %(qtext)s) q
    where c.tsv @@ q
    order by ts_rank_cd(c.tsv, q) desc
    limit %(cand)s
),
vec as (
    select c.id, c.deal_id,
           row_number() over (order by c.embedding <=> %(qemb)s) as rnk
    from chunks c
    join filtered f on f.id = c.deal_id
    order by c.embedding <=> %(qemb)s
    limit %(cand)s
),
fused as (
    select coalesce(b.id, v.id)              as chunk_id,
           coalesce(b.deal_id, v.deal_id)    as deal_id,
           (case when b.rnk is null then 0 else 1.0 / (%(k)s + b.rnk) end) +
           (case when v.rnk is null then 0 else 1.0 / (%(k)s + v.rnk) end) as score
    from bm25 b
    full outer join vec v on b.id = v.id
)
select chunk_id, deal_id, score
from fused
order by score desc
limit %(fused_limit)s
"""


@dataclass
class HybridRow:
    chunk_id: int
    deal_id: int
    score: float


def _band(filters: dict[str, Any], key: str) -> tuple[Any, Any]:
    v = filters.get(key)
    if not v:
        return (None, None)
    if isinstance(v, (list, tuple)) and len(v) == 2:
        return (v[0], v[1])
    return (None, None)


async def hybrid_search(
    query_embedding: list[float],
    query_text: str,
    filters: dict[str, Any],
    limit: int | None = None,
) -> list[HybridRow]:
    cfg = settings()
    rev_min, rev_max = _band(filters, "revenue_band")
    eb_min, eb_max = _band(filters, "ebitda_band")
    year_min, year_max = _band(filters, "year_band")

    params = {
        "qemb": query_embedding,
        "qtext": query_text,
        "rev_min": rev_min,
        "rev_max": rev_max,
        "eb_min": eb_min,
        "eb_max": eb_max,
        "sector": filters.get("sector_gics"),
        "region": filters.get("region"),
        "country": filters.get("country"),
        "year_min": year_min,
        "year_max": year_max,
        "buyer": filters.get("buyer_type"),
        "deal": filters.get("deal_type"),
        "cand": cfg.search_candidate_limit,
        "k": cfg.search_rrf_k,
        "fused_limit": limit or cfg.search_fused_limit,
    }

    from pgvector.psycopg import register_vector_async

    async with transaction() as conn:
        await register_vector_async(conn)
        async with conn.cursor() as cur:
            await cur.execute(_HYBRID_SQL, params)
            rows = await cur.fetchall()

    return [HybridRow(chunk_id=int(r[0]), deal_id=int(r[1]), score=float(r[2])) for r in rows]


def dedupe_by_deal(rows: list[HybridRow]) -> list[HybridRow]:
    """One chunk per deal, best score wins. Preserves rank order of first occurrence."""
    seen: dict[int, HybridRow] = {}
    order: list[int] = []
    for r in rows:
        if r.deal_id not in seen:
            seen[r.deal_id] = r
            order.append(r.deal_id)
        elif r.score > seen[r.deal_id].score:
            seen[r.deal_id] = r
    return [seen[d] for d in order]
