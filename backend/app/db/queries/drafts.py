from dataclasses import fields
from typing import Any
from uuid import UUID

from psycopg import AsyncConnection, sql
from psycopg.rows import class_row
from psycopg.types.json import Jsonb

from app.db.records import DraftRecord

_COLUMNS = sql.SQL(", ").join(sql.Identifier(f.name) for f in fields(DraftRecord))
_UPDATABLE = frozenset({"body", "suggested_body", "status", "sent_at", "undo_snapshot"})


async def create(conn: AsyncConnection, lead_id: UUID) -> None:
    await conn.execute(
        "INSERT INTO drafts (lead_id) VALUES (%s) ON CONFLICT (lead_id) DO NOTHING", (lead_id,)
    )


async def get(
    conn: AsyncConnection, lead_id: UUID, *, for_update: bool = False
) -> DraftRecord | None:
    query = sql.SQL("SELECT {} FROM drafts WHERE lead_id = %s").format(_COLUMNS)
    if for_update:
        query = query + sql.SQL(" FOR UPDATE")
    async with conn.cursor(row_factory=class_row(DraftRecord)) as cur:
        await cur.execute(query, (lead_id,))
        return await cur.fetchone()


async def update(conn: AsyncConnection, lead_id: UUID, **values: Any) -> int:
    """Writes the given columns and bumps `version`, which is what rep edits are checked against."""
    unknown = set(values) - _UPDATABLE
    if unknown:
        raise ValueError(f"Not updatable: {sorted(unknown)}")
    assignments: list[sql.Composable] = [
        sql.SQL("{} = %s").format(sql.Identifier(c)) for c in values
    ]
    assignments.append(sql.SQL("version = version + 1"))
    params = [Jsonb(v) if k == "undo_snapshot" and v is not None else v for k, v in values.items()]
    cur = await conn.execute(
        sql.SQL("UPDATE drafts SET {} WHERE lead_id = %s RETURNING version").format(
            sql.SQL(", ").join(assignments)
        ),
        [*params, lead_id],
    )
    row = await cur.fetchone()
    assert row is not None
    return int(row[0])
