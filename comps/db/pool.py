"""Connection pool. One pool per process; share across requests."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from psycopg import AsyncConnection
from psycopg_pool import AsyncConnectionPool

from comps.core.config import settings

_pool: AsyncConnectionPool | None = None


def get_pool() -> AsyncConnectionPool:
    global _pool
    if _pool is None:
        _pool = AsyncConnectionPool(
            conninfo=settings().database_url,
            min_size=1,
            max_size=10,
            kwargs={"autocommit": False},
            open=False,
        )
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


@asynccontextmanager
async def transaction() -> AsyncIterator[AsyncConnection]:
    pool = get_pool()
    if pool.closed:
        await pool.open()
    async with pool.connection() as conn, conn.transaction():
        yield conn
