"""DB access for ingest + search. Plain SQL, typed boundaries."""

from __future__ import annotations

import json
from typing import Any

from psycopg.rows import dict_row

from comps.core.models import Chunk, DealFields
from comps.db.pool import transaction


async def _register_vector(conn) -> None:
    from pgvector.psycopg import register_vector_async

    await register_vector_async(conn)


async def upsert_source(uri: str, kind: str, sha256: str) -> int:
    async with transaction() as conn:
        await _register_vector(conn)
        async with conn.cursor() as cur:
            await cur.execute(
                """
                insert into sources (uri, kind, sha256)
                values (%s, %s, %s)
                on conflict (sha256) do update set uri = excluded.uri
                returning id
                """,
                (uri, kind, sha256),
            )
            row = await cur.fetchone()
            assert row is not None
            return int(row[0])


async def insert_deal(source_id: int, fields: DealFields) -> int:
    async with transaction() as conn, conn.cursor() as cur:
        await cur.execute(
            """
                insert into deals (
                    source_id, target_name, target_ticker, buyer_name, buyer_type,
                    deal_type, sector_gics, sub_sector, country, region,
                    announced_on, closed_on, revenue_usd, ebitda_usd, ebitda_margin,
                    ev_usd, ev_revenue_mult, ev_ebitda_mult, growth_yoy, thesis
                ) values (
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s
                ) returning id
                """,
            (
                source_id,
                fields.target_name,
                fields.target_ticker,
                fields.buyer_name,
                fields.buyer_type,
                fields.deal_type,
                fields.sector_gics,
                fields.sub_sector,
                fields.country,
                fields.region,
                fields.announced_on,
                fields.closed_on,
                fields.revenue_usd,
                fields.ebitda_usd,
                fields.ebitda_margin,
                fields.ev_usd,
                fields.ev_revenue_mult,
                fields.ev_ebitda_mult,
                fields.growth_yoy,
                fields.thesis,
            ),
        )
        row = await cur.fetchone()
        assert row is not None
        return int(row[0])


async def bulk_insert_chunks(
    deal_id: int,
    source_id: int,
    chunks: list[Chunk],
    vectors: list[list[float]],
) -> None:
    if not chunks:
        return
    assert len(chunks) == len(vectors), "chunk/vector length mismatch"
    async with transaction() as conn:
        await _register_vector(conn)
        async with conn.cursor() as cur:
            await cur.executemany(
                """
                insert into chunks (deal_id, source_id, section, page, ord, text, tokens, embedding)
                values (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                [
                    (
                        deal_id,
                        source_id,
                        c.section,
                        c.page,
                        c.ord,
                        c.text,
                        c.tokens,
                        v,
                    )
                    for c, v in zip(chunks, vectors, strict=True)
                ],
            )


async def fetch_deal(deal_id: int) -> dict[str, Any] | None:
    async with transaction() as conn, conn.cursor(row_factory=dict_row) as cur:
        await cur.execute("select * from deals where id = %s", (deal_id,))
        return await cur.fetchone()


async def fetch_deals(deal_ids: list[int]) -> dict[int, dict[str, Any]]:
    if not deal_ids:
        return {}
    async with transaction() as conn, conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(
            "select * from deals where id = any(%s)",
            (deal_ids,),
        )
        rows = await cur.fetchall()
        return {int(r["id"]): r for r in rows}


async def fetch_top_chunk_for_deal(deal_id: int) -> str | None:
    async with transaction() as conn, conn.cursor() as cur:
        await cur.execute(
            """
                select text from chunks
                where deal_id = %s
                order by case section
                    when 'thesis' then 0
                    when 'mdna' then 1
                    when 'financials' then 2
                    else 3
                end, ord
                limit 1
                """,
            (deal_id,),
        )
        row = await cur.fetchone()
        return row[0] if row else None


async def load_eval_queries() -> list[dict[str, Any]]:
    async with transaction() as conn, conn.cursor(row_factory=dict_row) as cur:
        await cur.execute("select id, query, filters from eval_queries order by id")
        return list(await cur.fetchall())


async def load_judgments(query_id: int) -> dict[int, int]:
    async with transaction() as conn, conn.cursor() as cur:
        await cur.execute(
            "select deal_id, grade from eval_judgments where query_id = %s",
            (query_id,),
        )
        return {int(d): int(g) for d, g in await cur.fetchall()}


async def insert_eval_query(query: str, filters: dict[str, Any]) -> int:
    async with transaction() as conn, conn.cursor() as cur:
        await cur.execute(
            "insert into eval_queries (query, filters) values (%s, %s) returning id",
            (query, json.dumps(filters)),
        )
        row = await cur.fetchone()
        assert row is not None
        return int(row[0])


async def insert_judgment(query_id: int, deal_id: int, grade: int) -> None:
    async with transaction() as conn, conn.cursor() as cur:
        await cur.execute(
            """
                insert into eval_judgments (query_id, deal_id, grade)
                values (%s, %s, %s)
                on conflict (query_id, deal_id) do update set grade = excluded.grade
                """,
            (query_id, deal_id, grade),
        )
