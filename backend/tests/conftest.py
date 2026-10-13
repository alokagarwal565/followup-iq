"""Shared fixtures.

DB-backed tests use an isolated Postgres schema: each pytest session creates its own
"test_<random>" schema on TEST_DATABASE_URL, migrates it, and drops it afterwards, so runs never
touch application data. Never run two pytest processes against the same test database at once.
"""

import asyncio
import secrets
import selectors
import sys
from collections.abc import AsyncIterator, Callable, Mapping
from pathlib import Path

import psycopg
import pytest
import pytest_asyncio
from psycopg_pool import AsyncConnectionPool
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.config import BACKEND_ENV_FILE
from app.db.migrate import MIGRATIONS_DIR, migrate
from app.db.pool import create_pool, direct_neon_url


class _TestDbSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_ENV_FILE, extra="ignore")
    test_database_url: SecretStr | None = None


def _test_database_url() -> str | None:
    value = _TestDbSettings().test_database_url
    return value.get_secret_value() if value else None


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def db_schema() -> AsyncIterator[tuple[str, str]]:
    url = _test_database_url()
    if not url:
        pytest.skip("TEST_DATABASE_URL is not set in backend/.env; DB tests need a test database")
    # Schema-scoped search_path is session state, which a transaction pooler would not preserve.
    url = direct_neon_url(url)
    schema = f"test_{secrets.token_hex(6)}"
    admin = await _connect_with_retry(url)
    try:
        await admin.execute(f'CREATE SCHEMA "{schema}"')
        yield url, schema
    finally:
        await admin.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
        await admin.close()


async def _connect_with_retry(url: str) -> psycopg.AsyncConnection:
    # Serverless Postgres (Neon) can drop the first connection while compute wakes up.
    try:
        return await psycopg.AsyncConnection.connect(url, autocommit=True, connect_timeout=15)
    except psycopg.OperationalError:
        return await psycopg.AsyncConnection.connect(url, autocommit=True, connect_timeout=30)


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def pool(db_schema: tuple[str, str]) -> AsyncIterator[AsyncConnectionPool]:
    url, schema = db_schema
    db_pool = create_pool(url, schema=schema, max_size=4)
    await db_pool.open(wait=True, timeout=30)
    async with db_pool.connection() as conn:
        await migrate(conn, MIGRATIONS_DIR)
    try:
        yield db_pool
    finally:
        await db_pool.close()


@pytest_asyncio.fixture(loop_scope="session")
async def clean_db(pool: AsyncConnectionPool) -> AsyncIterator[None]:
    # Safe by construction: the pool's search_path is this session's throwaway schema.
    async with pool.connection() as conn:
        await conn.execute("TRUNCATE leads CASCADE")
    yield


def migrations_dir() -> Path:
    return MIGRATIONS_DIR


def pytest_asyncio_loop_factories(
    config: pytest.Config, item: pytest.Item
) -> Mapping[str, Callable[[], asyncio.AbstractEventLoop]]:
    # psycopg async mode can't run on Windows' default Proactor loop; Linux (Render) is fine.
    if sys.platform == "win32":
        return {"selector": lambda: asyncio.SelectorEventLoop(selectors.SelectSelector())}
    return {"default": asyncio.new_event_loop}
