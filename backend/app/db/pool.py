import re

from psycopg import AsyncConnection, sql
from psycopg_pool import AsyncConnectionPool

_NEON_POOLER_HOST = re.compile(r"(@ep-[a-z0-9-]+?)-pooler(\.)")


def direct_neon_url(url: str) -> str:
    """Neon's pooled endpoint is PgBouncer in transaction mode, which drops session settings such
    as search_path between transactions; its direct endpoint is the same host without -pooler."""
    return _NEON_POOLER_HOST.sub(r"\1\2", url)


def create_pool(url: str, *, schema: str | None = None, max_size: int = 5) -> AsyncConnectionPool:
    """Pool sized for free-tier connection limits; opened by the caller (app lifespan or tests)."""

    async def configure(conn: AsyncConnection) -> None:
        if schema is not None:
            await conn.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(schema)))
            await conn.commit()

    return AsyncConnectionPool(
        url,
        min_size=1,
        max_size=max_size,
        open=False,
        timeout=15,
        # prepare_threshold=None keeps working if DATABASE_URL points at a transaction pooler,
        # which cannot hold server-side prepared statements across transactions.
        kwargs={"prepare_threshold": None, "connect_timeout": 10},
        configure=configure,
        check=AsyncConnectionPool.check_connection,
    )


async def connect(url: str, schema: str | None = None) -> AsyncConnection:
    """Single connection for CLIs; with a schema it is created if missing and made current."""
    conn = await AsyncConnection.connect(url, prepare_threshold=None, connect_timeout=15)
    if schema is not None:
        await conn.execute(sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(sql.Identifier(schema)))
        await conn.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(schema)))
        await conn.commit()
    return conn
