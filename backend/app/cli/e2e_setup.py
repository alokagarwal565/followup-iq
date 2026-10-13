"""Resets a throwaway schema for end-to-end tests: drop, migrate, seed, analyse with the fake AI.

    DATABASE_SCHEMA=e2e_frontend GEMINI_FAKE=1 python -m app.cli.e2e_setup

Refuses to run unless DATABASE_SCHEMA starts with "e2e" and the fake analyzer is enabled, so it
can never wipe application data or spend Gemini quota.
"""

from datetime import UTC, datetime

from psycopg import sql

from app.ai.fake import FakeAnalyzer
from app.cli.seed import seed
from app.config import load_settings
from app.db.migrate import migrate
from app.db.pool import connect, create_pool
from app.runtime import run
from app.services.analysis import analyze_lead


async def main() -> None:
    settings = load_settings()
    schema = settings.database_schema
    if not schema or not schema.startswith("e2e"):
        raise SystemExit("Refusing to reset: DATABASE_SCHEMA must start with 'e2e'.")
    if not settings.gemini_fake:
        raise SystemExit("Refusing to reset: set GEMINI_FAKE=1 so E2E never calls Gemini.")
    url = settings.database_url.get_secret_value()

    async with await connect(url) as conn:
        await conn.execute(
            sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(sql.Identifier(schema))
        )
        await conn.commit()
    async with await connect(url, schema) as conn:
        await migrate(conn)
        await seed(conn, now=datetime.now(UTC), tz=settings.tz)
        await conn.commit()

    pool = create_pool(url, schema=schema, max_size=2)
    await pool.open(wait=True, timeout=30)
    try:
        async with pool.connection() as conn:
            cur = await conn.execute("SELECT id FROM leads")
            ids = [row[0] for row in await cur.fetchall()]
        for lead_id in ids:
            await analyze_lead(
                pool,
                lead_id,
                analyzer=FakeAnalyzer(),
                settings=settings,
                now=lambda: datetime.now(UTC),
            )
    finally:
        await pool.close()
    print(f"E2E schema {schema} ready with {len(ids)} analysed leads.")


if __name__ == "__main__":
    run(main())
