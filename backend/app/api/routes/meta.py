import asyncio

from fastapi import APIRouter

from app.api.deps import Conn, Now, SettingsDep
from app.api.schemas import MetaOut, ReadyOut
from app.domain.constants import REPS, SOURCES
from app.errors import AppError

router = APIRouter(prefix="/api/v1", tags=["meta"])

API_VERSION = "0.1.0"


class DatabaseUnavailable(AppError):
    status_code = 503
    code = "db_unavailable"


@router.get("/meta", response_model=MetaOut)
async def meta(now: Now, settings: SettingsDep) -> MetaOut:
    # The server's business-timezone "today" is the UI's source of truth, not the browser clock.
    return MetaOut(
        today=now.today,
        business_tz=settings.business_tz,
        reps=list(REPS),
        sources=list(SOURCES),
        version=API_VERSION,
    )


@router.get("/health/ready", response_model=ReadyOut)
async def ready(conn: Conn, settings: SettingsDep) -> ReadyOut:
    try:
        async with asyncio.timeout(2):
            await conn.execute("SELECT 1")
    except Exception as exc:
        raise DatabaseUnavailable("Database is not reachable") from exc
    return ReadyOut(
        status="ok", db="ok", ai="configured" if settings.ai_configured else "unconfigured"
    )
