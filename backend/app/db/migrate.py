"""Forward-only SQL migrations: each file in migrations/ runs once, in name order, in its own
transaction, and is recorded in schema_migrations. Run with `python -m app.db.migrate`."""

import asyncio
from pathlib import Path

from psycopg import AsyncConnection

from app.db.pool import connect
from app.logging import configure_logging, get_logger
from app.runtime import run

MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "migrations"

log = get_logger("db.migrate")


async def migrate(conn: AsyncConnection, migrations_dir: Path = MIGRATIONS_DIR) -> list[str]:
    async with conn.transaction():
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
              filename    text PRIMARY KEY,
              applied_at  timestamptz NOT NULL DEFAULT now()
            )
            """
        )
        # Serialises concurrent runs (e.g. two deploys) so a file is never applied twice.
        await conn.execute("SELECT pg_advisory_xact_lock(hashtext('followupiq_migrations'))")
        cur = await conn.execute("SELECT filename FROM schema_migrations")
        applied = {row[0] for row in await cur.fetchall()}

    newly_applied: list[str] = []
    for name, script in await asyncio.to_thread(_pending_scripts, migrations_dir, applied):
        async with conn.transaction():
            # No parameters, so psycopg sends the whole file as one multi-statement script.
            await conn.execute(script)
            await conn.execute("INSERT INTO schema_migrations (filename) VALUES (%s)", (name,))
        log.info("migration_applied", filename=name)
        newly_applied.append(name)
    return newly_applied


def _pending_scripts(migrations_dir: Path, applied: set[str]) -> list[tuple[str, str]]:
    return [
        (path.name, path.read_text(encoding="utf-8"))
        for path in sorted(migrations_dir.glob("*.sql"))
        if path.name not in applied
    ]


async def _main() -> None:
    from app.config import load_settings

    settings = load_settings()
    configure_logging(settings.log_level)
    async with await connect(
        settings.database_url.get_secret_value(), settings.database_schema
    ) as conn:
        applied = await migrate(conn)
    log.info("migrations_complete", applied=len(applied))


if __name__ == "__main__":
    run(_main())
