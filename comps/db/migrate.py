"""Tiny forward-only migration runner. Each .sql file in migrations/ runs once.

Tracked in a comps_migrations table. Keep migrations idempotent where possible
so re-runs after partial failures stay tractable.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import psycopg

from comps.core.config import settings
from comps.core.logging import configure, get

log = get(__name__)


MIGRATIONS_DIR = Path(__file__).resolve().parent.parent.parent / "migrations"


async def _apply(conn: psycopg.AsyncConnection, name: str, sql: str) -> None:
    log.info("applying %s", name)
    async with conn.cursor() as cur:
        await cur.execute(sql)
        await cur.execute(
            "insert into comps_migrations (name) values (%s)",
            (name,),
        )


async def run() -> None:
    configure()
    conninfo = settings().database_url
    async with await psycopg.AsyncConnection.connect(conninfo) as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                create table if not exists comps_migrations (
                    name       text primary key,
                    applied_at timestamptz not null default now()
                )
                """
            )
            await cur.execute("select name from comps_migrations")
            applied = {row[0] for row in await cur.fetchall()}

        files = sorted(MIGRATIONS_DIR.glob("*.sql"))
        if not files:
            log.warning("no migrations found in %s", MIGRATIONS_DIR)

        for f in files:
            if f.name in applied:
                continue
            sql = f.read_text()
            async with conn.transaction():
                await _apply(conn, f.name, sql)

        await conn.commit()
        log.info("migrations up to date (%d applied total)", len(files))


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
