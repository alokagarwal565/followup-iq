from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from datetime import date, datetime
from typing import Annotated, Protocol
from uuid import UUID

from fastapi import BackgroundTasks, Depends, Request
from psycopg import AsyncConnection
from psycopg_pool import AsyncConnectionPool

from app.config import Settings
from app.domain.rules import business_today


class AnalysisScheduler(Protocol):
    def __call__(
        self, background: BackgroundTasks, lead_id: UUID, *, force: bool = False
    ) -> None: ...


@dataclass(frozen=True)
class Clock:
    now: datetime
    today: date


def get_settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def get_pool(request: Request) -> AsyncConnectionPool:
    pool: AsyncConnectionPool = request.app.state.pool
    return pool


async def get_conn(
    pool: Annotated[AsyncConnectionPool, Depends(get_pool)],
) -> AsyncIterator[AsyncConnection]:
    async with pool.connection() as conn:
        yield conn


def get_clock(request: Request) -> Clock:
    clock: Callable[[], datetime] = request.app.state.clock
    now = clock()
    return Clock(now=now, today=business_today(request.app.state.settings.tz, now))


def get_scheduler(request: Request) -> AnalysisScheduler:
    scheduler: AnalysisScheduler = request.app.state.scheduler
    return scheduler


Conn = Annotated[AsyncConnection, Depends(get_conn)]
Now = Annotated[Clock, Depends(get_clock)]
Scheduler = Annotated[AnalysisScheduler, Depends(get_scheduler)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
