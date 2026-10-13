"""Mechanical schema gate: proves the migration follows the DB conventions, not just review."""

import psycopg
import pytest
from psycopg_pool import AsyncConnectionPool

from app.db.migrate import MIGRATIONS_DIR, migrate

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _rows(pool: AsyncConnectionPool, sql: str) -> list[tuple]:
    async with pool.connection() as conn:
        cur = await conn.execute(sql)
        return await cur.fetchall()


async def test_every_foreign_key_column_leads_an_index(pool):
    fks = await _rows(
        pool,
        """
        SELECT con.conrelid::regclass::text, att.attname
        FROM pg_constraint con
        JOIN pg_attribute att ON att.attrelid = con.conrelid AND att.attnum = con.conkey[1]
        WHERE con.contype = 'f' AND con.connamespace = current_schema()::regnamespace
        """,
    )
    assert fks, "expected foreign keys in the schema"
    for table, column in fks:
        leading = await _rows(
            pool,
            f"""
            SELECT 1 FROM pg_index i
            JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = i.indkey[0]
            WHERE i.indrelid = '{table}'::regclass AND a.attname = '{column}'
            """,
        )
        assert leading, f"{table}.{column} has no index with it as the leading column"


async def test_tables_with_updated_at_have_a_working_trigger(pool):
    tables = await _rows(
        pool,
        """
        SELECT table_name FROM information_schema.columns
        WHERE table_schema = current_schema() AND column_name = 'updated_at'
        """,
    )
    assert {t for (t,) in tables} == {"leads", "drafts"}

    # Raw SQL on purpose: an ORM-level check would pass even without a trigger.
    async with pool.connection() as conn:
        await conn.execute(
            """
            INSERT INTO leads (id, name, company, phone, phone_digits, source, assigned_rep,
                               updated_at)
            VALUES ('00000000-0000-0000-0000-0000000000aa', 'T', 'T Co', '+91 90000 00001',
                    '919000000001', 'Website', 'Priya Sharma', now() - interval '1 day')
            """
        )
        await conn.execute(
            "UPDATE leads SET name = 'T2' WHERE id = '00000000-0000-0000-0000-0000000000aa'"
        )
        cur = await conn.execute(
            "SELECT updated_at > now() - interval '1 minute' FROM leads "
            "WHERE id = '00000000-0000-0000-0000-0000000000aa'"
        )
        assert (await cur.fetchone()) == (True,)
        await conn.execute("DELETE FROM leads WHERE id = '00000000-0000-0000-0000-0000000000aa'")


async def test_primary_keys_default_to_gen_random_uuid(pool):
    defaults = await _rows(
        pool,
        """
        SELECT table_name, column_default FROM information_schema.columns
        WHERE table_schema = current_schema() AND column_name = 'id'
        """,
    )
    assert {t for t, _ in defaults} == {"leads", "conversations", "messages"}
    for table, default in defaults:
        assert default == "gen_random_uuid()", table


async def test_rerunning_migrations_is_a_no_op(pool):
    async with pool.connection() as conn:
        assert await migrate(conn, MIGRATIONS_DIR) == []


async def test_check_constraint_rejects_unknown_source(pool):
    async with pool.connection() as conn:
        with pytest.raises(psycopg.errors.CheckViolation):
            async with conn.transaction():
                await conn.execute(
                    """
                    INSERT INTO leads (name, company, phone, phone_digits, source, assigned_rep)
                    VALUES ('T', 'T Co', '+91 90000 00002', '919000000002', 'Fax', 'Priya Sharma')
                    """
                )


async def test_row_level_security_is_enabled_everywhere(pool):
    rows = await _rows(
        pool,
        """
        SELECT relname, relrowsecurity FROM pg_class
        WHERE relnamespace = current_schema()::regnamespace AND relkind = 'r'
          AND relname <> 'schema_migrations'
        """,
    )
    assert rows and all(enabled for _, enabled in rows)
