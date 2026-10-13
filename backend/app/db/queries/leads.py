from dataclasses import dataclass, fields
from datetime import datetime
from typing import Any
from uuid import UUID

from psycopg import AsyncConnection, sql
from psycopg.rows import class_row
from psycopg.types.json import Jsonb

from app.db.records import LeadRecord

_COLUMNS = sql.SQL(", ").join(sql.Identifier(f.name) for f in fields(LeadRecord))

# Columns services may write after insert; anything else is a programming error, not user input.
_UPDATABLE = frozenset(
    {
        "name",
        "company",
        "phone",
        "phone_digits",
        "source",
        "assigned_rep",
        "last_contact_at",
        "do_not_contact",
        "classification",
        "classification_reason",
        "next_follow_up_date",
        "follow_up_reason",
        "evidence",
        "signals",
        "analysis_status",
        "analysis_source",
        "analysis_model",
        "analysis_error",
        "analysis_requested_at",
        "analysis_updated_at",
        "analysis_fingerprint",
    }
)
_JSONB = frozenset({"evidence", "signals"})


@dataclass(frozen=True)
class NewLeadRow:
    name: str
    company: str
    phone: str
    phone_digits: str
    source: str
    assigned_rep: str
    last_contact_at: datetime | None


def _escape_like(text: str) -> str:
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


async def insert(
    conn: AsyncConnection,
    row: NewLeadRow,
    *,
    lead_id: UUID | None = None,
    created_at: datetime | None = None,
) -> UUID:
    # created_at comes from the application clock when given, so date rules and tests agree on
    # "today"; the database clock is only the fallback.
    cur = await conn.execute(
        """
        INSERT INTO leads (id, name, company, phone, phone_digits, source, assigned_rep,
                           last_contact_at, created_at, updated_at)
        VALUES (COALESCE(%s, gen_random_uuid()), %s, %s, %s, %s, %s, %s, %s,
                COALESCE(%s, now()), COALESCE(%s, now()))
        RETURNING id
        """,
        (
            lead_id,
            row.name,
            row.company,
            row.phone,
            row.phone_digits,
            row.source,
            row.assigned_rep,
            row.last_contact_at,
            created_at,
            created_at,
        ),
    )
    result = await cur.fetchone()
    assert result is not None
    return UUID(str(result[0]))


async def get(
    conn: AsyncConnection, lead_id: UUID, *, for_update: bool = False
) -> LeadRecord | None:
    query = sql.SQL("SELECT {} FROM leads WHERE id = %s").format(_COLUMNS)
    if for_update:
        query = query + sql.SQL(" FOR UPDATE")
    async with conn.cursor(row_factory=class_row(LeadRecord)) as cur:
        await cur.execute(query, (lead_id,))
        return await cur.fetchone()


async def find_by_phone_digits(conn: AsyncConnection, digits: str) -> UUID | None:
    cur = await conn.execute("SELECT id FROM leads WHERE phone_digits = %s", (digits,))
    row = await cur.fetchone()
    return UUID(str(row[0])) if row else None


async def list_leads(
    conn: AsyncConnection,
    *,
    rep: str | None = None,
    classification: str | None = None,
    q: str | None = None,
) -> list[LeadRecord]:
    """Filtered leads in no particular order; queue order is applied by the domain rules."""
    clauses: list[sql.Composable] = []
    params: list[Any] = []
    if rep:
        clauses.append(sql.SQL("assigned_rep = %s"))
        params.append(rep)
    if classification:
        clauses.append(sql.SQL("classification = %s"))
        params.append(classification)
    if q and q.strip():
        pattern = f"%{_escape_like(q.strip())}%"
        digits = "".join(ch for ch in q if ch.isdigit())
        search = [
            sql.SQL("name ILIKE %s ESCAPE '\\'"),
            sql.SQL("company ILIKE %s ESCAPE '\\'"),
        ]
        params += [pattern, pattern]
        if digits:
            search.append(sql.SQL("phone_digits LIKE %s"))
            params.append(f"%{digits}%")
        clauses.append(sql.SQL("(") + sql.SQL(" OR ").join(search) + sql.SQL(")"))
    where = sql.SQL(" WHERE ") + sql.SQL(" AND ").join(clauses) if clauses else sql.SQL("")
    query = sql.SQL("SELECT {} FROM leads").format(_COLUMNS) + where
    async with conn.cursor(row_factory=class_row(LeadRecord)) as cur:
        await cur.execute(query, params)
        return await cur.fetchall()


async def update(conn: AsyncConnection, lead_id: UUID, **values: Any) -> None:
    unknown = set(values) - _UPDATABLE
    if unknown:
        raise ValueError(f"Not updatable: {sorted(unknown)}")
    if not values:
        return
    assignments = sql.SQL(", ").join(
        sql.SQL("{} = %s").format(sql.Identifier(column)) for column in values
    )
    params = [Jsonb(v) if k in _JSONB and v is not None else v for k, v in values.items()]
    await conn.execute(
        sql.SQL("UPDATE leads SET {} WHERE id = %s").format(assignments), [*params, lead_id]
    )
