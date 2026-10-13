from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.ai.analyzer import Analyzer, GeminiAnalyzer
from app.ai.fake import FakeAnalyzer
from app.api.deps import AnalysisScheduler
from app.api.errors import install_error_handlers
from app.api.middleware import BodySizeLimitMiddleware, RequestIdMiddleware
from app.api.ratelimit import RateLimitMiddleware
from app.api.routes import health, leads, meta
from app.config import Settings, load_settings
from app.db.pool import create_pool
from app.logging import configure_logging, get_logger
from app.services.analysis import make_scheduler

log = get_logger("main")

_CREATE_POOL: Any = object()


def create_app(
    settings: Settings,
    *,
    pool: Any = _CREATE_POOL,
    scheduler: AnalysisScheduler | None = None,
    clock: Callable[[], datetime] | None = None,
) -> FastAPI:
    """Builds the app. Tests inject the pool, scheduler and clock; production creates them."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        owns_pool = pool is _CREATE_POOL
        if owns_pool:
            app.state.pool = create_pool(
                settings.database_url.get_secret_value(), schema=settings.database_schema
            )
            # wait=False: the API (and /health) must come up even while the database wakes up.
            await app.state.pool.open(wait=False)
        if not settings.ai_configured:
            log.warning("ai_unconfigured", detail="no Gemini keys; analyses use the rules fallback")
        try:
            yield
        finally:
            if owns_pool:
                await app.state.pool.close()

    app = FastAPI(title="FollowUpIQ API", version=meta.API_VERSION, lifespan=lifespan)
    app.state.settings = settings
    app.state.pool = None if pool is _CREATE_POOL else pool
    app.state.clock = clock or (lambda: datetime.now(UTC))
    if scheduler is None:
        analyzer: Analyzer = FakeAnalyzer() if settings.gemini_fake else GeminiAnalyzer(settings)
        scheduler = make_scheduler(lambda: app.state.pool, analyzer, settings, app.state.clock)
    app.state.scheduler = scheduler

    install_error_handlers(app)
    app.add_middleware(
        RateLimitMiddleware,
        writes_per_min=settings.rate_limit_writes_per_min,
        analyze_per_min=settings.rate_limit_analyze_per_min,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_origin_regex=settings.cors_origin_regex,
        allow_methods=["GET", "POST", "PUT", "PATCH"],
        allow_headers=["content-type", "x-request-id"],
        expose_headers=["x-request-id"],
    )
    app.add_middleware(BodySizeLimitMiddleware, max_bytes=settings.max_body_bytes)
    # Added last so it runs first: every response, even CORS and size rejections, carries an id.
    app.add_middleware(RequestIdMiddleware)

    app.include_router(health.router)
    app.include_router(meta.router)
    app.include_router(leads.router)
    return app


def build_app() -> FastAPI:
    settings = load_settings()
    configure_logging(settings.log_level)
    return create_app(settings)
