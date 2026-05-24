"""arq-orchestrated ingest pipeline: parse -> chunk -> extract -> embed -> index.

Each stage is a job. Failures are isolated and re-runnable. Re-ingest of an
already-seen sha256 short-circuits at the source-insert (on conflict do
update).
"""

from __future__ import annotations

import asyncio

from arq import cron
from arq.connections import RedisSettings
from psycopg.errors import UniqueViolation

from comps.core.config import settings
from comps.core.logging import configure, get
from comps.db import queries
from comps.ingest import chunk as chunk_mod
from comps.ingest import embed as embed_mod
from comps.ingest import extract as extract_mod
from comps.ingest import parse as parse_mod

log = get(__name__)


async def ingest_one(ctx: dict, source_uri: str, kind: str = "other") -> dict:
    """End-to-end ingest of a single document. Returns ids for traceability."""
    log.info("ingesting %s", source_uri)
    doc = parse_mod.parse(source_uri)
    effective_kind = kind if kind != "other" else doc.kind

    try:
        source_id = await queries.upsert_source(source_uri, effective_kind, doc.sha256)
    except UniqueViolation:
        # Race: another worker grabbed the same sha. Re-fetch by sha.
        log.info("source %s already present (sha collision)", source_uri)
        raise

    cfg = settings()
    fields = extract_mod.extract(doc.markdown[: cfg.ingest_max_extract_chars])
    deal_id = await queries.insert_deal(source_id, fields)

    chunks = chunk_mod.chunk(doc)
    vectors = embed_mod.embed_chunks(chunks)
    await queries.bulk_insert_chunks(deal_id, source_id, chunks, vectors)

    log.info("ingested %s -> deal %d (%d chunks)", source_uri, deal_id, len(chunks))
    return {"source_id": source_id, "deal_id": deal_id, "chunks": len(chunks)}


async def ingest_many(ctx: dict, source_uris: list[str], kind: str = "other") -> list[dict]:
    """Sequential batch ingest. Caller wants order preserved for reporting."""
    out: list[dict] = []
    for uri in source_uris:
        try:
            out.append(await ingest_one(ctx, uri, kind))
        except Exception as e:
            log.exception("ingest failed for %s: %s", uri, e)
            out.append({"source_uri": uri, "error": str(e)})
    return out


async def startup(ctx: dict) -> None:
    configure()
    log.info("worker started")


async def shutdown(ctx: dict) -> None:
    from comps.db.pool import close_pool

    await close_pool()


class WorkerSettings:
    functions = [ingest_one, ingest_many]
    on_startup = startup
    on_shutdown = shutdown
    cron_jobs: list = []  # placeholder if scheduled re-embeds are added
    redis_settings = RedisSettings.from_dsn(settings().redis_url)
    max_jobs = 4
    job_timeout = 600


def run_worker() -> None:
    """Console script entrypoint: arq comps.ingest.pipeline.WorkerSettings."""
    from arq.worker import run_worker as _run

    _run(WorkerSettings)


async def enqueue(source_uris: list[str], kind: str = "other") -> None:
    """Helper for the CLI to fan out ingestion via Redis."""
    from arq import create_pool

    pool = await create_pool(WorkerSettings.redis_settings)
    try:
        for uri in source_uris:
            await pool.enqueue_job("ingest_one", uri, kind)
    finally:
        await pool.close()


def main() -> None:
    asyncio.run(ingest_one({}, "example.pdf"))


# Placate type-checkers about the unused cron import for future cron jobs.
_ = cron
