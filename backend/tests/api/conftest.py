from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import httpx
import pytest_asyncio
from fastapi import BackgroundTasks

from app.config import Settings
from app.main import create_app

NOW = datetime(2026, 10, 12, 6, 0, tzinfo=UTC)  # 11:30 IST on Monday 12 Oct


@dataclass
class RecordingScheduler:
    """Stands in for the analysis service so API tests assert scheduling, not Gemini behaviour."""

    calls: list[tuple[UUID, bool]] = field(default_factory=list)

    def __call__(self, background: BackgroundTasks, lead_id: UUID, *, force: bool = False) -> None:
        self.calls.append((lead_id, force))


@dataclass
class Api:
    client: httpx.AsyncClient
    scheduler: RecordingScheduler
    settings: Settings


def make_settings(**overrides: Any) -> Settings:
    base: dict[str, Any] = {
        "database_url": "postgresql://unused:unused@localhost:1/unused",
        "env": "test",
        "cors_origins": "http://localhost:3000",
        "rate_limit_writes_per_min": 1000,
        "rate_limit_analyze_per_min": 1000,
        # Explicit values beat the process environment, so a developer's own Gemini key can't
        # leak into tests and change their outcome.
        "gemini_api_key": None,
        "gemini_api_key_2": None,
        "gemini_api_key_3": None,
        "gemini_api_key_fallbacks": None,
        "gemini_fake": False,
    }
    base.update(overrides)
    return Settings(**base)


async def make_api(pool: Any, **settings_overrides: Any) -> tuple[Api, httpx.AsyncClient]:
    settings = make_settings(**settings_overrides)
    scheduler = RecordingScheduler()
    app = create_app(settings, pool=pool, scheduler=scheduler, clock=lambda: NOW)
    client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")
    return Api(client=client, scheduler=scheduler, settings=settings), client


@pytest_asyncio.fixture(loop_scope="session")
async def api(pool: Any, clean_db: None) -> AsyncIterator[Api]:
    instance, client = await make_api(pool)
    async with client:
        yield instance


def lead_payload(**overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "name": "Rahul Mehta",
        "company": "Shree Snacks Pvt Ltd",
        "phone": "+91 90000 01001",
        "source": "IndiaMART",
        "assigned_rep": "Priya Sharma",
    }
    body.update(overrides)
    return body
