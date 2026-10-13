"""Analyses leads in bulk, one at a time, through the same service the API uses.

    python -m app.cli.analyze --pending   leads never analysed, pending, or failed
    python -m app.cli.analyze --all       every lead (re-runs Gemini, costs quota)

Used after seeding a database. Calls are paced to stay within free-tier request limits.
"""

import argparse
import asyncio
from datetime import UTC, datetime
from uuid import UUID

from app.ai.analyzer import GeminiAnalyzer
from app.ai.fake import FakeAnalyzer
from app.config import load_settings
from app.db.pool import create_pool
from app.logging import configure_logging
from app.runtime import run
from app.services.analysis import analyze_lead

PACING_SECONDS = 4.0


async def main(everything: bool) -> None:
    settings = load_settings()
    configure_logging("WARNING")
    analyzer = FakeAnalyzer() if settings.gemini_fake else GeminiAnalyzer(settings)
    pool = create_pool(
        settings.database_url.get_secret_value(), schema=settings.database_schema, max_size=2
    )
    await pool.open(wait=True, timeout=30)
    try:
        async with pool.connection() as conn:
            where = "" if everything else "WHERE analysis_status IN ('never', 'pending', 'failed')"
            cur = await conn.execute(f"SELECT id, name FROM leads {where} ORDER BY created_at")  # noqa: S608 (fixed clause)
            leads = [(UUID(str(row[0])), str(row[1])) for row in await cur.fetchall()]
        print(f"Analysing {len(leads)} lead(s)...")
        tally: dict[str, int] = {}
        for index, (lead_id, name) in enumerate(leads):
            if index:
                await asyncio.sleep(PACING_SECONDS)
            outcome = await analyze_lead(
                pool,
                lead_id,
                analyzer=analyzer,
                settings=settings,
                now=lambda: datetime.now(UTC),
                force=everything,
            )
            tally[outcome] = tally.get(outcome, 0) + 1
            print(f"  {outcome:<10} {name}")
        print("Done:", ", ".join(f"{k}={v}" for k, v in sorted(tally.items())))
    finally:
        await pool.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--pending", action="store_true")
    group.add_argument("--all", action="store_true")
    run(main(parser.parse_args().all))
