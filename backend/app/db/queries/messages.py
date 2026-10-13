from dataclasses import fields
from datetime import datetime
from uuid import UUID

from psycopg import AsyncConnection, sql
from psycopg.rows import class_row

from app.db.records import MessageRecord

_COLUMNS = sql.SQL(", ").join(sql.SQL("m.") + sql.Identifier(f.name) for f in fields(MessageRecord))


async def ensure_conversation(conn: AsyncConnection, lead_id: UUID) -> UUID:
    """The lead's latest conversation, created on first use. New chats append to it."""
    cur = await conn.execute(
        "SELECT id FROM conversations WHERE lead_id = %s ORDER BY created_at DESC LIMIT 1",
        (lead_id,),
    )
    row = await cur.fetchone()
    if row:
        return UUID(str(row[0]))
    cur = await conn.execute(
        "INSERT INTO conversations (lead_id) VALUES (%s) RETURNING id", (lead_id,)
    )
    created = await cur.fetchone()
    assert created is not None
    return UUID(str(created[0]))


async def insert(
    conn: AsyncConnection,
    conversation_id: UUID,
    sender_type: str,
    body: str,
    sent_at: datetime,
    *,
    origin: str = "logged",
    request_id: UUID | None = None,
    message_id: UUID | None = None,
) -> UUID:
    cur = await conn.execute(
        """
        INSERT INTO messages (id, conversation_id, sender_type, body, sent_at, origin,
                              client_request_id)
        VALUES (COALESCE(%s, gen_random_uuid()), %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO NOTHING
        RETURNING id
        """,
        (message_id, conversation_id, sender_type, body, sent_at, origin, request_id),
    )
    row = await cur.fetchone()
    return UUID(str(row[0])) if row else message_id  # type: ignore[return-value]


async def for_lead(conn: AsyncConnection, lead_id: UUID) -> list[MessageRecord]:
    query = sql.SQL(
        "SELECT {} FROM messages m JOIN conversations c ON c.id = m.conversation_id "
        "WHERE c.lead_id = %s ORDER BY m.sent_at, m.created_at, m.id"
    ).format(_COLUMNS)
    async with conn.cursor(row_factory=class_row(MessageRecord)) as cur:
        await cur.execute(query, (lead_id,))
        return await cur.fetchall()


async def lead_for_request(conn: AsyncConnection, request_id: UUID) -> UUID | None:
    cur = await conn.execute(
        "SELECT c.lead_id FROM messages m JOIN conversations c ON c.id = m.conversation_id "
        "WHERE m.client_request_id = %s LIMIT 1",
        (request_id,),
    )
    row = await cur.fetchone()
    return UUID(str(row[0])) if row else None


async def delete(conn: AsyncConnection, message_id: UUID) -> None:
    await conn.execute("DELETE FROM messages WHERE id = %s", (message_id,))


async def lock_request(conn: AsyncConnection, request_id: UUID) -> None:
    # Transaction-scoped: concurrent submissions of the same request queue here, so the
    # replay check that follows cannot race.
    await conn.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (str(request_id),))
