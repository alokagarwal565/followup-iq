"""Seeds the fictional demo data. Safe to re-run: rows are keyed by fixed ids and never deleted.

python -m app.cli.seed                 insert any missing demo rows
python -m app.cli.seed --rebase-demo   shift demo dates forward so the queue looks current
"""

import argparse
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from psycopg import AsyncConnection

from app.db.pool import connect
from app.db.queries import drafts as draft_q
from app.domain.phone import phone_digits
from app.domain.rules import business_today
from app.logging import configure_logging, get_logger
from app.runtime import run
from app.seed_data import (
    SEED_LEADS,
    SeedLead,
    seed_conversation_id,
    seed_lead_id,
    seed_message_id,
)

log = get_logger("cli.seed")

# Excel-only leads have no chat timestamp; a mid-morning call time keeps their dates unambiguous.
_EXCEL_CONTACT_TIME = time(11, 0)


@dataclass(frozen=True)
class SeedReport:
    leads_inserted: int
    messages_inserted: int


def _at(day: date, hhmm: str | time, tz: ZoneInfo) -> datetime:
    clock = hhmm if isinstance(hhmm, time) else time.fromisoformat(hhmm)
    return datetime.combine(day, clock, tzinfo=tz).astimezone(UTC)


def _last_contact(lead: SeedLead, today: date, tz: ZoneInfo) -> datetime | None:
    if lead.messages:
        return max(_at(today - timedelta(days=m.days_ago), m.time, tz) for m in lead.messages)
    if lead.last_contact_days_ago is not None:
        return _at(today - timedelta(days=lead.last_contact_days_ago), _EXCEL_CONTACT_TIME, tz)
    return None


async def seed(conn: AsyncConnection, *, now: datetime, tz: ZoneInfo) -> SeedReport:
    today = business_today(tz, now)
    leads_inserted = messages_inserted = 0
    async with conn.transaction():
        for lead in SEED_LEADS:
            lead_id = seed_lead_id(lead.key)
            created_at = now - timedelta(days=lead.created_days_ago)
            # Bare ON CONFLICT also skips a demo row whose phone a user has since added by hand.
            cur = await conn.execute(
                """
                INSERT INTO leads (id, name, company, phone, phone_digits, source, assigned_rep,
                                   last_contact_at, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT DO NOTHING
                RETURNING id
                """,
                (
                    lead_id,
                    lead.name,
                    lead.company,
                    lead.phone,
                    phone_digits(lead.phone),
                    lead.source,
                    lead.rep,
                    _last_contact(lead, today, tz),
                    created_at,
                    created_at,
                ),
            )
            if await cur.fetchone() is None:
                continue
            leads_inserted += 1
            await draft_q.create(conn, lead_id)
            if not lead.messages:
                continue
            sent_times = [
                _at(today - timedelta(days=m.days_ago), m.time, tz) for m in lead.messages
            ]
            conversation_id = seed_conversation_id(lead.key)
            await conn.execute(
                "INSERT INTO conversations (id, lead_id, created_at) VALUES (%s, %s, %s)",
                (conversation_id, lead_id, min(sent_times)),
            )
            for index, (message, sent_at) in enumerate(zip(lead.messages, sent_times, strict=True)):
                await conn.execute(
                    """
                    INSERT INTO messages (id, conversation_id, sender_type, body, sent_at,
                                          origin, created_at)
                    VALUES (%s, %s, %s, %s, %s, 'seed', %s)
                    """,
                    (
                        seed_message_id(lead.key, index),
                        conversation_id,
                        message.sender,
                        message.body,
                        sent_at,
                        sent_at,
                    ),
                )
                messages_inserted += 1
    log.info("seed_complete", leads_inserted=leads_inserted, messages_inserted=messages_inserted)
    return SeedReport(leads_inserted=leads_inserted, messages_inserted=messages_inserted)


async def rebase_demo(conn: AsyncConnection, *, now: datetime, tz: ZoneInfo) -> int:
    """Moves every demo timestamp and date forward by the whole days elapsed since seeding.

    Demo data ages between seeding and review; without this the queue would show only overdue
    leads. User-created leads are never touched. Returns the number of days shifted.
    """
    anchor = SEED_LEADS[0]
    cur = await conn.execute(
        "SELECT created_at FROM leads WHERE id = %s", (seed_lead_id(anchor.key),)
    )
    row = await cur.fetchone()
    if row is None:
        return 0
    seeded_on = (row[0] + timedelta(days=anchor.created_days_ago)).astimezone(tz).date()
    days = int((business_today(tz, now) - seeded_on).days)
    if days <= 0:
        return 0

    ids = [seed_lead_id(lead.key) for lead in SEED_LEADS]
    shift = timedelta(days=days)
    async with conn.transaction():
        await conn.execute(
            """
            UPDATE leads SET
              created_at = created_at + %(shift)s,
              last_contact_at = last_contact_at + %(shift)s,
              analysis_requested_at = analysis_requested_at + %(shift)s,
              analysis_updated_at = analysis_updated_at + %(shift)s,
              next_follow_up_date = next_follow_up_date + %(days)s
            WHERE id = ANY(%(ids)s)
            """,
            {"shift": shift, "days": days, "ids": ids},
        )
        await conn.execute(
            """
            UPDATE messages m
            SET sent_at = m.sent_at + %(shift)s, created_at = m.created_at + %(shift)s
            FROM conversations c
            WHERE c.id = m.conversation_id AND c.lead_id = ANY(%(ids)s)
            """,
            {"shift": shift, "ids": ids},
        )
        await conn.execute(
            "UPDATE conversations SET created_at = created_at + %(shift)s "
            "WHERE lead_id = ANY(%(ids)s)",
            {"shift": shift, "ids": ids},
        )
        await conn.execute(
            "UPDATE drafts SET sent_at = sent_at + %(shift)s WHERE lead_id = ANY(%(ids)s)",
            {"shift": shift, "ids": ids},
        )
    log.info("demo_rebased", days=days)
    return days


async def _main(rebase: bool) -> None:
    from app.config import load_settings

    settings = load_settings()
    configure_logging(settings.log_level)
    async with await connect(
        settings.database_url.get_secret_value(), settings.database_schema
    ) as conn:
        now = datetime.now(UTC)
        if rebase:
            await rebase_demo(conn, now=now, tz=settings.tz)
        else:
            await seed(conn, now=now, tz=settings.tz)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rebase-demo", action="store_true", help="shift demo dates to today")
    run(_main(parser.parse_args().rebase_demo))
